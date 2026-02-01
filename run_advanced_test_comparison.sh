#!/bin/bash

# Shell script to run regrading with multiple models and configurations on advanced test cases
# This script runs the same analysis as the main comparison but on the advanced_test_cases dataset

# Parse command line arguments
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help       Show this help message"
    echo ""
    exit 0
}

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            ;;
    esac
done

echo "Starting advanced test cases comparison script..."
echo "================================================="

# Configuration files
# uncomment to reproduce the tests in the paper
# configs=(
#    "annotated_submission.json"
#    "grading_only_question_answer.json"
#    "baseline.json"
#    "baseline_concise.json"
#    "best_three/ms_w_example_final.json"
#    "best_three/systematic5.0.json"
#    "best_three/use_markscheme_no_example3.0.json"
# )

# running a reduced evaluation with just best_three/systematic5.0.json
configs=(
    "best_three/systematic5.0.json"
)

# Model settings (empty string means use config default)
# uncomment to reproduce the tests in the paper
# models=(
#    "gpt-4o-2024-08-06"              # Use gpt-4o
#    "gpt-4.1-2025-04-14"       # Override with gpt-4.1
#    "gpt-4.1-mini-2025-04-14"  # Override with gpt-4.1-mini
#    "gpt-4.1-nano" # This was gpt-4.1-nano-2025-04-14
#    "gpt-5"
#    "gpt-5-mini"
#    "gpt-5-nano"
#    "o4-mini"
# )

# running a reduced evaluation with just gpt-5.2
models=(
    "gpt-5.2"
)

# Model names for output directories and files
# uncomment to reproduce the tests in the paper
# model_names=(
#    "gpt-4o-2024-08-06"
#    "gpt-4.1-2025-04-14"
#    "gpt-4.1-mini-2025-04-14"
#    "gpt-4.1-nano"
#    "gpt-5"
#    "gpt-5-mini"
#    "gpt-5-nano"
#    "o4-mini"
# )

# running a reduced evaluation with just gpt-5.2
model_names=(
    "gpt-5.2"
)

# Create results directories for advanced test cases
mkdir -p results/advanced_test_comparison
mkdir -p results/advanced_test_evaluations

echo "Running regrading tasks in parallel..."
echo "======================================"

# Function to run a single model/config combination
run_combination() {
    local config="$1"
    local model="$2"
    local config_name="$3"
    local model_name="$4"
    
    echo "Starting: Config=$config_name, Model=$model_name (PID=$$)"
    
    # Build command with cache disabled - using advanced_test as problem_dir
    local cmd="python math_tutor.py --problem_dir advanced_test --config $config --no_cache"
    if [ -n "$model" ]; then
        cmd="$cmd --model $model"
    fi
    
    # Run the regrading (with confirmation prompt handling) and capture output
    local log_file="temp_log_advanced_${config_name}_${model_name}.log"
    
    if echo "y" | $cmd > "$log_file" 2>&1; then
        echo "✓ Completed: $config_name with $model_name"
        rm -f "$log_file"  # Clean up log on success
        return 0
    else
        echo "✗ Failed: $config_name with $model_name (see $log_file for details)"
        return 1
    fi
}

# Export the function so it's available to background processes
export -f run_combination

# Start all combinations in parallel
pids=()
skipped_count=0
for i in "${!configs[@]}"; do
    config="${configs[$i]}"
    config_name=$(basename "$config" .json)
    
    for j in "${!models[@]}"; do
        model="${models[$j]}"
        model_name="${model_names[$j]}"
        
        # Check if output already exists for this specific config+model combination
        model_output_dir="tests/advanced_test/output/$model_name"
        if [ -d "$model_output_dir" ] && [ -n "$(find "$model_output_dir" -name "*${config_name}*.json" -type f 2>/dev/null)" ]; then
            echo "Skipping: Config=$config_name, Model=$model_name (output already exists)"
            ((skipped_count++))
            continue
        fi
        
        echo "Launching: Config=$config_name, Model=$model_name"
        
        # Run in background and store PID
        run_combination "$config" "$model" "$config_name" "$model_name" &
        pids+=($!)
    done
done

echo ""
echo "All ${#pids[@]} combinations launched. Waiting for completion..."
echo "================================================================"

# Wait for all background processes and track results
failed_count=0
completed_count=0

for pid in "${pids[@]}"; do
    if wait $pid; then
        ((completed_count++))
    else
        ((failed_count++))
    fi
done

echo ""
echo "Regrading tasks completed!"
echo "=========================="
echo "✓ Successful: $completed_count"
echo "✗ Failed: $failed_count"
echo "⊘ Skipped: $skipped_count (output already exists)"
echo "Total: $((${#pids[@]} + $skipped_count)) combinations"

# Wait a moment for file system to settle
sleep 3

echo ""
echo "Running evaluations..."
echo "===================="

# Check if output directory exists and has files
if [ ! -d "tests/advanced_test/output" ] || [ -z "$(find tests/advanced_test/output -name '*.json' 2>/dev/null)" ]; then
    echo "Warning: No output files found in tests/advanced_test/output/"
    echo "Evaluation cannot proceed."
    exit 1
fi

# Function to evaluate a single model
evaluate_model() {
    local model_name="$1"
    
    echo "Starting evaluation for: $model_name"
    
    local model_output_dir="tests/advanced_test/output/$model_name"
    if [ -d "$model_output_dir" ] && [ -n "$(find $model_output_dir -name '*.json' 2>/dev/null)" ]; then
        local eval_output_file="results/advanced_test_evaluations/${model_name}_comparison.json"
        
        if python evaluator.py --input_directory "$model_output_dir" --output_file "$eval_output_file" --no_bootstrap >/dev/null 2>&1; then
            echo "✓ Evaluation completed for $model_name"
            
            # Extract and display correlation values for this model using aggregation helper
            if [ -f "$eval_output_file" ]; then
                local pearson=$(python3 aggregate_eval_stats.py "$eval_output_file" "correlation" 2>/dev/null)
                local kendall=$(python3 aggregate_eval_stats.py "$eval_output_file" "kendall_tau" 2>/dev/null)
                local spearman=$(python3 aggregate_eval_stats.py "$eval_output_file" "spearman" 2>/dev/null)
                local percent_agree=$(python3 aggregate_eval_stats.py "$eval_output_file" "percent_agreement" 2>/dev/null)
                local close_match=$(python3 aggregate_eval_stats.py "$eval_output_file" "percent_close_match" 2>/dev/null)
                
                echo "  Results for $model_name:"
                echo "    Pearson correlation: $pearson"
                echo "    Kendall tau: $kendall"
                echo "    Spearman rank: $spearman"
                echo "    Percent agreement: $percent_agree"
                echo "    Percent close match (±1): $close_match"
                echo "    Saved to: $eval_output_file"
            fi
            return 0
        else
            echo "✗ Evaluation failed for $model_name"
            return 1
        fi
    else
        echo "No output files found for model: $model_name"
        return 1
    fi
}

# Export evaluation function
export -f evaluate_model

# Run evaluations in parallel
echo "Evaluating results for each model in parallel..."
eval_pids=()

for model_name in "${model_names[@]}"; do
    echo "Launching evaluation for: $model_name"
    evaluate_model "$model_name" &
    eval_pids+=($!)
done

echo ""
echo "All ${#eval_pids[@]} evaluations launched. Waiting for completion..."
echo "=================================================================="

# Wait for all evaluation processes
eval_failed=0
eval_completed=0

for pid in "${eval_pids[@]}"; do
    if wait $pid; then
        ((eval_completed++))
    else
        ((eval_failed++))
    fi
done

echo ""
echo "Individual model evaluations completed!"
echo "======================================"
echo "✓ Successful: $eval_completed"
echo "✗ Failed: $eval_failed"

# Also run combined evaluation across all models
echo ""
echo "Running combined evaluation across all models..."
echo "=============================================="
python evaluator.py --input_directory tests/advanced_test/output --output_file results/advanced_test_evaluations/all_models_combined.json --no_bootstrap

if [ $? -eq 0 ]; then
    echo "✓ Combined evaluation completed successfully"
    echo "Results saved to: results/advanced_test_evaluations/all_models_combined.json"
else
    echo "✗ Combined evaluation failed"
fi

# Clean up any remaining temporary files
rm -f temp_log_advanced_*.log

echo ""
echo "========================================"
echo "Script completed!"
echo "========================================"
echo ""
echo "Generated files:"
echo "- Output results: tests/advanced_test/output/ (organized by model)"
echo "- Individual model evaluations: results/advanced_test_evaluations/{model_name}_comparison.json"
echo "- Combined evaluation: results/advanced_test_evaluations/all_models_combined.json"
echo ""
echo "To view individual output files by model:"
echo "find tests/advanced_test/output -name '*.json' -type f"
echo ""
echo "To view evaluation results:"
echo "ls -la results/advanced_test_evaluations/"

