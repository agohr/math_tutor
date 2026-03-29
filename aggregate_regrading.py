"""
This script re-runs the grading step twice on all combinations of
feedback model and grading model, for a total of three grades.

The statistics are then recomputed using the median.
"""

import numpy as np
import pathlib
import json
import csv
import asyncio

import evaluator
import math_tutor


# Allow multiple processes to be run
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Setup math_tutor
math_tutor.settings.config_path = "grading_only_any_model.json"
math_tutor.settings.enable_cache = False
math_tutor.settings.load_config()

# Configuration files
configs=(
    # "annotated_submission.json",
    # "grading_only_question_answer.json",
    "baseline.json",
    "baseline_concise.json",
    "best_three/ms_w_example_final.json",
    "best_three/systematic5.0.json",
    "best_three/use_markscheme_no_example3.0.json"
)

# Model settings (empty string means use config default)
models=(
    "gpt-4o-2024-08-06",              # Use gpt-4o
    "gpt-4.1-2025-04-14",       # Override with gpt-4.1
    "gpt-4.1-mini-2025-04-14",  # Override with gpt-4.1-mini
    "gpt-4.1-nano", # This was gpt-4.1-nano-2025-04-14
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    "o4-mini"
)

# Model settings (empty string means use config default)
grading_models=(
    #"gpt-4o-2024-08-06",
    # "gpt-4.1-2025-04-14",
    "gpt-4.1-mini-2025-04-14",
    "gpt-4o-mini-2024-07-18",
    "gpt-4.1-nano-2025-04-14",
    # "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    # "o4-mini"
)

base_test_path = pathlib.Path("tests", "test", "output")
regrading_path = pathlib.Path("tests", "test", "repeat_grading")
output_file_name = pathlib.Path("results", "aggregate_statistics.csv")
TIMES_GRADED_PER_RUN = 3


def get_latest_runs(model_dir, configs_to_test):
    """Search for runs, keep latest run with each config"""
    latest_runs = {}
    for file_path in sorted(model_dir.iterdir()):
        name = file_path.name
        if not name.endswith("-test.json"):
            continue

        # Extract the config name by stripping the timestamp (first 15 chars)
        # and the suffix ("-test.json")
        config_name = name[15:].removesuffix("-test.json")

        if config_name in configs_to_test:
            # The latest config will overwrite previous ones
            latest_runs[config_name] = name
    return latest_runs


def get_stats_summary(grader_stats):
    # Helper to extract values and find best/worst
    sorted_stats = sorted(grader_stats.items(), key=lambda x: x[1])
    worst_grader, worst_val = sorted_stats[0]
    best_grader, best_val = sorted_stats[-1]
    values = [v for k, v in sorted_stats]
    # avg is the median of the medians
    avg_val = np.median(values)
    val_range = best_val - worst_val
    return worst_grader, worst_val, best_grader, best_val, avg_val, val_range


def get_graded_cases(regrading_dir, config_name, grading_model, i, original_test_cases, model):
    # Format: {workflow}-{grading model}-{iteration}.json
    file_name = f"{config_name}-{grading_model}-{i}.json"
    file_new = regrading_dir / file_name

    if file_new.exists():
        print(file_new, "already exists", sep=": ")
        with open(file_new, "r") as f:
            new_run_dict = json.load(f)
        return new_run_dict["test"]
    else:
        print(file_new, "generating", sep=": ")
        responses, thoughts = math_tutor.process_batch_input(
            original_test_cases, temperature=0.0
        )
        output_data = {
            "config": config_name,  # this is instead the feedback config
            "model_used": grading_model,
            "feedback_model": model,
            "test": thoughts
        }
        with open(file_new, "w") as f:
            json.dump(output_data, f, indent=4)
        return thoughts


def process_config(model, model_dir, regrading_dir, config_name, path):
    with open(model_dir / path, "r") as f:
        initial_run_dict = json.load(f)

    assert initial_run_dict["model_used"] == model

    # The questions & feedback to be graded
    original_test_cases = initial_run_dict["test"]

    grader_median_taus = {}
    grader_median_corrs = {}
    feedback_mean_len = 0
    graded_cases = None

    for grading_model in grading_models:
        math_tutor.settings.model_override = grading_model
        current_grader_taus = []
        current_grader_corrs = []

        # Run grading iterations
        for i in range(TIMES_GRADED_PER_RUN):
            # NB: Temperature is 0; non-determinism comes from changing seed &
            # inherent non-determinism in the highly parallel modern models
            math_tutor.settings.model_seed = 128 + i
            graded_cases = get_graded_cases(
                regrading_dir, config_name, grading_model, i, original_test_cases, model
            )
            if graded_cases is not None:
                run_stats = evaluator.get_statistics(graded_cases)
                current_grader_taus.append(run_stats['kendall_tau'])
                current_grader_corrs.append(run_stats['correlation'])

        if current_grader_taus:
            print(f"{model} {config_name} {grading_model} summary")
            print(f"  {current_grader_taus=}\n  {current_grader_corrs=}")
            # Store the median metrics for this specific grader
            grader_median_taus[grading_model] = np.median(current_grader_taus)
            grader_median_corrs[grading_model] = np.median(current_grader_corrs)

    # Feedback length is the same across all graders and repeats, just use last
    if graded_cases is not None:
        lengths = [len(item['llm_feedback'].split()) for item in graded_cases]
        feedback_mean_len = np.mean(lengths)

    # Aggregate statistics across graders
    w_p_grad, w_p_val, b_p_grad, b_p_val, avg_p, range_p = get_stats_summary(grader_median_corrs)
    w_k_grad, w_k_val, b_k_grad, b_k_val, avg_k, range_k = get_stats_summary(grader_median_taus)

    result = {
        "workflow": config_name,
        "feedback_model": model,
        "worst_pearson_grader": w_p_grad,
        "worst_pearson_correlation": w_p_val,
        "best_pearson_grader": b_p_grad,
        "best_pearson_correlation": b_p_val,
        "avg_pearson_correlation": avg_p,
        "pearson_range": range_p,
        "worst_kendall_grader": w_k_grad,
        "worst_kendall_tau": w_k_val,
        "best_kendall_grader": b_k_grad,
        "best_kendall_tau": b_k_val,
        "avg_kendall_tau": avg_k,
        "kendall_range": range_k,
        "mean_length": feedback_mean_len,
        "num_graders": len(grader_median_taus.keys())
    }

    for grader in grader_median_taus:
        result[f"_pearson_{grader}"] = grader_median_corrs[grader]
        result[f"_kendall_{grader}"] = grader_median_taus[grader]

    return result


def main():
    csv_rows = []
    configs_to_test = {pathlib.Path(c).stem for c in configs}

    for model in models:
        model_dir = base_test_path / model
        latest_runs = get_latest_runs(model_dir, configs_to_test)

        # Ensure output directory exists: base path/{model}/
        regrading_dir = regrading_path / model
        regrading_dir.mkdir(parents=True, exist_ok=True)

        for config_name, path in latest_runs.items():
            try:
                row = process_config(model, model_dir, regrading_dir, config_name, path)
                csv_rows.append(row)
            except (IndexError, ConnectionError):
                print(f'Missing data - Row skipped: {model} {config_name}')
                csv_rows.append({})

    # Write results to CSV
    fieldnames = csv_rows[0].keys()

    with open(output_file_name, "w", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)


if __name__ == '__main__':
    main()
