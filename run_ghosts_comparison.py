#!/usr/bin/env python3
"""
Python script to run regrading with multiple models and configurations, then evaluate results.
This script analyzes the data in tests/ghosts_9jan directory.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Configuration files
CONFIGS = [
    "baseline.json",
    "baseline_concise.json",
    "best_three/ms_w_example_final.json",
    "best_three/systematic5.0.json",
    "best_three/use_markscheme_no_example3.0.json",
]

# Model settings
MODELS = [
    "gpt-4o-2024-08-06",
    "gpt-4.1-2025-04-14",
    "gpt-4.1-mini-2025-04-14",
    "gpt-4.1-nano",
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    "o4-mini",
]

# Problem directory
PROBLEM_DIR = "ghosts_9jan"


def show_help():
    """Display help message."""
    print("Usage: python run_ghosts_comparison.py [OPTIONS]")
    print()
    print("Options:")
    print("  --track-costs    Enable cost tracking and reporting (requires confirmation)")
    print("  --max-workers N  Maximum number of parallel workers (default: 4)")
    print("  -h, --help       Show this help message")
    print()


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run regrading comparison on ghosts_9jan dataset",
        add_help=False
    )
    parser.add_argument("--track-costs", action="store_true", 
                       help="Enable cost tracking and reporting")
    parser.add_argument("--max-workers", type=int, default=4,
                       help="Maximum number of parallel workers")
    parser.add_argument("-h", "--help", action="store_true",
                       help="Show help message")
    
    args = parser.parse_args()
    
    if args.help:
        show_help()
        sys.exit(0)
    
    return args


def confirm_cost_tracking():
    """Ask user to confirm cost tracking."""
    print()
    print("=" * 73)
    print("COST TRACKING ENABLED")
    print("=" * 73)
    print("This will track and display API costs based on published pricing rates")
    print("as of the time this research artifact was created.")
    print()
    print("NOTE: These costs are estimates based on pricing at time of publication")
    print("and may not reflect current API pricing. This is a research artifact and")
    print("cost tracking is provided for reproducibility purposes only.")
    print()
    response = input("Do you want to proceed with cost tracking? (y/N): ")
    print("=" * 73)
    print()
    
    return response.strip().lower() in ['y', 'yes']


def run_single_combination(config, model, config_name, model_name, track_costs):
    """
    Run a single model/config combination.
    
    Returns:
        tuple: (success, config_name, model_name, cost)
    """
    print(f"Starting: Config={config_name}, Model={model_name}")
    
    # Clear usage tracking if cost tracking is enabled
    if track_costs:
        try:
            subprocess.run(
                ["python", "extract_cost.py", "--clear"],
                capture_output=True,
                check=False
            )
        except Exception:
            pass
    
    # Build command
    cmd = [
        "python", "math_tutor.py",
        "--problem_dir", PROBLEM_DIR,
        "--config", config,
        "--no_cache"
    ]
    
    if model:
        cmd.extend(["--model", model])
    
    # Check if output already exists
    model_output_dir = Path("tests") / PROBLEM_DIR / "output" / model_name
    if model_output_dir.exists():
        existing_files = list(model_output_dir.glob(f"*{config_name}*.json"))
        if existing_files:
            print(f"Skipping: Config={config_name}, Model={model_name} (output already exists)")
            return (True, config_name, model_name, 0.0, True)  # skipped
    
    # Run the regrading with "y" piped to stdin for confirmation
    try:
        result = subprocess.run(
            cmd,
            input="y\n",
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            cost = 0.0
            if track_costs:
                try:
                    cost_result = subprocess.run(
                        ["python", "extract_cost.py"],
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    if cost_result.returncode == 0:
                        cost = float(cost_result.stdout.strip() or "0.0")
                except Exception:
                    cost = 0.0
            
            if track_costs:
                print(f"✓ Completed: {config_name} with {model_name} (Cost: ${cost:.6f})")
            else:
                print(f"✓ Completed: {config_name} with {model_name}")
            
            return (True, config_name, model_name, cost, False)
        else:
            print(f"✗ Failed: {config_name} with {model_name}")
            print(f"  Error: {result.stderr[:200]}")
            return (False, config_name, model_name, 0.0, False)
            
    except Exception as e:
        print(f"✗ Failed: {config_name} with {model_name}")
        print(f"  Exception: {str(e)}")
        return (False, config_name, model_name, 0.0, False)


def evaluate_single_model(model_name):
    """
    Evaluate results for a single model.
    
    Returns:
        tuple: (success, model_name, stats_dict)
    """
    print(f"Starting evaluation for: {model_name}")
    
    model_output_dir = Path("tests") / PROBLEM_DIR / "output" / model_name
    
    if not model_output_dir.exists() or not list(model_output_dir.glob("*.json")):
        print(f"No output files found for model: {model_name}")
        return (False, model_name, None)
    
    eval_output_file = Path("results") / "ghosts_evaluations" / f"{model_name}_comparison.json"
    eval_output_file.parent.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        "python", "evaluator.py",
        "--input_directory", str(model_output_dir),
        "--output_file", str(eval_output_file),
        "--no_bootstrap"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        if result.returncode == 0:
            print(f"✓ Evaluation completed for {model_name}")
            
            # Extract and display correlation values
            if eval_output_file.exists():
                stats = extract_aggregate_stats(eval_output_file)
                if stats:
                    print(f"  Results for {model_name}:")
                    print(f"    Pearson correlation: {stats['correlation']:.4f}")
                    print(f"    Kendall tau: {stats['kendall_tau']:.4f}")
                    print(f"    Spearman rank: {stats['spearman']:.4f}")
                    print(f"    Percent agreement: {stats['percent_agreement']:.2f}%")
                    print(f"    Percent close match (±1): {stats['percent_close_match']:.2f}%")
                    print(f"    Saved to: {eval_output_file}")
                    return (True, model_name, stats)
            
            return (True, model_name, None)
        else:
            print(f"✗ Evaluation failed for {model_name}")
            return (False, model_name, None)
            
    except Exception as e:
        print(f"✗ Evaluation failed for {model_name}: {str(e)}")
        return (False, model_name, None)


def extract_aggregate_stats(json_file):
    """Extract aggregate statistics from evaluator.py output."""
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        if not data:
            return None
        
        # Collect statistics from all files
        correlations = []
        kendall_taus = []
        spearmans = []
        agreements = []
        close_matches = []
        
        for file_path, stats in data.items():
            if 'correlation' in stats:
                correlations.append(stats['correlation'])
            if 'kendall_tau' in stats:
                kendall_taus.append(stats['kendall_tau'])
            if 'spearman' in stats:
                spearmans.append(stats['spearman'])
            if 'percent_agreement' in stats:
                agreements.append(stats['percent_agreement'])
            if 'percent_close_match' in stats:
                close_matches.append(stats['percent_close_match'])
        
        def mean(lst):
            return sum(lst) / len(lst) if lst else 0
        
        return {
            'correlation': mean(correlations),
            'kendall_tau': mean(kendall_taus),
            'spearman': mean(spearmans),
            'percent_agreement': mean(agreements),
            'percent_close_match': mean(close_matches)
        }
    except Exception:
        return None


def main():
    """Main execution function."""
    args = parse_arguments()
    
    # Handle cost tracking confirmation
    track_costs = args.track_costs
    if track_costs:
        if not confirm_cost_tracking():
            print("Cost tracking disabled. Continuing without cost tracking...")
            track_costs = False
    
    print("Starting ghosts_9jan comparison script...")
    print("=" * 40)
    
    # Create results directories
    Path("results/ghosts_comparison").mkdir(parents=True, exist_ok=True)
    Path("results/ghosts_evaluations").mkdir(parents=True, exist_ok=True)
    
    # Initialize cost tracking
    cost_data = []
    
    print()
    print("Running regrading tasks in parallel...")
    print("=" * 40)
    
    # Generate all combinations
    combinations = []
    for config in CONFIGS:
        config_name = Path(config).stem
        for model in MODELS:
            combinations.append((config, model, config_name, model))
    
    # Run combinations in parallel
    completed_count = 0
    failed_count = 0
    skipped_count = 0
    
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {
            executor.submit(
                run_single_combination, 
                config, model, config_name, model_name, track_costs
            ): (config_name, model_name)
            for config, model, config_name, model_name in combinations
        }
        
        for future in as_completed(futures):
            success, config_name, model_name, cost, skipped = future.result()
            
            if skipped:
                skipped_count += 1
            elif success:
                completed_count += 1
                if track_costs:
                    cost_data.append((config_name, model_name, cost))
            else:
                failed_count += 1
    
    print()
    print("Regrading tasks completed!")
    print("=" * 26)
    print(f"✓ Successful: {completed_count}")
    print(f"✗ Failed: {failed_count}")
    print(f"⊘ Skipped: {skipped_count} (output already exists)")
    print(f"Total: {len(combinations)} combinations")
    
    # Display cost summary if enabled
    if track_costs and cost_data:
        print()
        print("Cost Summary by Model/Config Combination:")
        print("=" * 40)
        print(f"{'Config':<26} | {'Model':<26} | {'Cost (USD)'}")
        print("-" * 27 + "|" + "-" * 28 + "|" + "-" * 12)
        
        total_cost = 0.0
        for config, model, cost in cost_data:
            print(f"{config:<26} | {model:<26} | ${cost:.6f}")
            total_cost += cost
        
        print("-" * 27 + "|" + "-" * 28 + "|" + "-" * 12)
        print(f"{'TOTAL':<26} | {'':<26} | ${total_cost:.6f}")
        print()
    
    # Wait for file system
    time.sleep(3)
    
    print()
    print("Running evaluations...")
    print("=" * 20)
    
    # Check if output directory exists
    output_dir = Path("tests") / PROBLEM_DIR / "output"
    if not output_dir.exists() or not list(output_dir.glob("**/*.json")):
        print(f"Warning: No output files found in {output_dir}")
        print("Evaluation cannot proceed.")
        sys.exit(1)
    
    # Run evaluations in parallel
    print("Evaluating results for each model in parallel...")
    eval_completed = 0
    eval_failed = 0
    
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {
            executor.submit(evaluate_single_model, model): model
            for model in MODELS
        }
        
        for future in as_completed(futures):
            success, model_name, stats = future.result()
            if success:
                eval_completed += 1
            else:
                eval_failed += 1
    
    print()
    print("Individual model evaluations completed!")
    print("=" * 38)
    print(f"✓ Successful: {eval_completed}")
    print(f"✗ Failed: {eval_failed}")
    
    # Run combined evaluation across all models
    print()
    print("Running combined evaluation across all models...")
    print("=" * 46)
    
    combined_output = Path("results/ghosts_evaluations/all_models_combined.json")
    cmd = [
        "python", "evaluator.py",
        "--input_directory", str(output_dir),
        "--output_file", str(combined_output),
        "--no_bootstrap"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✓ Combined evaluation completed successfully")
        print(f"Results saved to: {combined_output}")
    else:
        print("✗ Combined evaluation failed")
    
    # Save cost data if enabled
    if track_costs and cost_data:
        timestamp = time.strftime('%Y-%m-%d_%H-%M-%S')
        cost_file = Path("results/ghosts_comparison") / f"costs_{timestamp}.csv"
        with open(cost_file, 'w') as f:
            for config, model, cost in cost_data:
                f.write(f"{config},{model},{cost:.6f}\n")
        print(f"Cost data saved to: {cost_file}")
    
    print()
    print("=" * 40)
    print("Script completed!")
    print("=" * 40)
    print()
    print("Generated files:")
    print(f"- Output results: tests/{PROBLEM_DIR}/output/ (organized by model)")
    print("- Individual model evaluations: results/ghosts_evaluations/{model_name}_comparison.json")
    print("- Combined evaluation: results/ghosts_evaluations/all_models_combined.json")
    if track_costs:
        print("- Cost breakdown: results/ghosts_comparison/costs_*.csv")
    print()
    print("To view individual output files by model:")
    print(f"  find tests/{PROBLEM_DIR}/output -name '*.json' -type f")
    print()
    print("To view evaluation results:")
    print("  ls -la results/ghosts_evaluations/")


if __name__ == "__main__":
    main()
