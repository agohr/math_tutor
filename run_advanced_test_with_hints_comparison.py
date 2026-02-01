#!/usr/bin/env python3
"""
Python script to run regrading with multiple models and configurations on advanced test cases with hints.
This script analyzes the data in tests/advanced_test_with_hints directory.
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
# Uncomment to reproduce the tests in the paper
# CONFIGS = [
#     "annotated_submission.json",
#     "grading_only_question_answer.json",
#     "baseline.json",
#     "baseline_concise.json",
#     "best_three/ms_w_example_final.json",
#     "best_three/systematic5.0.json",
#     "best_three/use_markscheme_no_example3.0.json",
# ]

# Running evaluation with multiple configs
CONFIGS = [
    "baseline.json",
    "baseline_concise.json",
    "best_three/systematic5.0.json",
    "best_three/use_markscheme_no_example3.0.json",
    "best_three/ms_w_example_final.json",
]

# Model settings
# Uncomment to reproduce the tests in the paper
# MODELS = [
#     "gpt-4o-2024-08-06",
#     "gpt-4.1-2025-04-14",
#     "gpt-4.1-mini-2025-04-14",
#     "gpt-4.1-nano",
#     "gpt-5",
#     "gpt-5-mini",
#     "gpt-5-nano",
#     "o4-mini",
# ]

# Running a reduced evaluation with just gpt-5.2
MODELS = [
    "gpt-5.2",
    "gpt-4.1-2025-04-14",
    "gpt-5-mini"
]

# Problem directory
PROBLEM_DIR = "advanced_test_with_hints"


def show_help():
    """Display help message."""
    print("Usage: python run_advanced_test_with_hints_comparison.py [OPTIONS]")
    print()
    print("Options:")
    print("  --max-workers N  Maximum number of parallel workers (default: 4)")
    print("  -h, --help       Show this help message")
    print()


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run regrading comparison on advanced_test_with_hints dataset",
        add_help=False
    )
    parser.add_argument("--max-workers", type=int, default=4,
                       help="Maximum number of parallel workers")
    parser.add_argument("-h", "--help", action="store_true",
                       help="Show help message")
    
    args = parser.parse_args()
    
    if args.help:
        show_help()
        sys.exit(0)
    
    return args


def run_single_combination(config, model, config_name, model_name):
    """
    Run a single model/config combination.
    
    Returns:
        tuple: (success, config_name, model_name, skipped)
    """
    print(f"Starting: Config={config_name}, Model={model_name}")
    
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
            return (True, config_name, model_name, True)  # skipped
    
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
            print(f"✓ Completed: {config_name} with {model_name}")
            return (True, config_name, model_name, False)
        else:
            print(f"✗ Failed: {config_name} with {model_name}")
            # Save full error output to file for debugging
            error_log_file = f"error_log_{config_name}_{model_name}.txt"
            with open(error_log_file, 'w') as f:
                f.write(f"Command: {' '.join(cmd)}\n")
                f.write(f"\n{'='*60}\n")
                f.write("STDOUT:\n")
                f.write(f"{'='*60}\n")
                f.write(result.stdout)
                f.write(f"\n{'='*60}\n")
                f.write("STDERR:\n")
                f.write(f"{'='*60}\n")
                f.write(result.stderr)
            print(f"  Full error saved to: {error_log_file}")
            print(f"  Error preview: {result.stderr[:200]}")
            return (False, config_name, model_name, False)
            
    except Exception as e:
        print(f"✗ Failed: {config_name} with {model_name}")
        print(f"  Exception: {str(e)}")
        return (False, config_name, model_name, False)


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
    
    eval_output_file = Path("results") / "advanced_test_with_hints_evaluations" / f"{model_name}_comparison.json"
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
    
    print("Starting advanced test cases with hints comparison script...")
    print("=" * 49)
    
    # Create results directories
    Path("results/advanced_test_with_hints_comparison").mkdir(parents=True, exist_ok=True)
    Path("results/advanced_test_with_hints_evaluations").mkdir(parents=True, exist_ok=True)
    
    print()
    print("Running regrading tasks in parallel...")
    print("=" * 38)
    
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
                config, model, config_name, model_name
            ): (config_name, model_name)
            for config, model, config_name, model_name in combinations
        }
        
        for future in as_completed(futures):
            success, config_name, model_name, skipped = future.result()
            
            if skipped:
                skipped_count += 1
            elif success:
                completed_count += 1
            else:
                failed_count += 1
    
    print()
    print("Regrading tasks completed!")
    print("=" * 26)
    print(f"✓ Successful: {completed_count}")
    print(f"✗ Failed: {failed_count}")
    print(f"⊘ Skipped: {skipped_count} (output already exists)")
    print(f"Total: {len(combinations)} combinations")
    
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
    
    combined_output = Path("results/advanced_test_with_hints_evaluations/all_models_combined.json")
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
    
    print()
    print("=" * 40)
    print("Script completed!")
    print("=" * 40)
    print()
    print("Generated files:")
    print(f"- Output results: tests/{PROBLEM_DIR}/output/ (organized by model)")
    print("- Individual model evaluations: results/advanced_test_with_hints_evaluations/{{model_name}}_comparison.json")
    print("- Combined evaluation: results/advanced_test_with_hints_evaluations/all_models_combined.json")
    print()
    print("To view individual output files by model:")
    print(f"  find tests/{PROBLEM_DIR}/output -name '*.json' -type f")
    print()
    print("To view evaluation results:")
    print("  ls -la results/advanced_test_with_hints_evaluations/")


if __name__ == "__main__":
    main()
