"""
This script re-runs the grading step twice on all combinations of
feedback model and grading model, for a total of three grades.

The statistics are then recomputed using their stratified Bootstrap
estimators.
"""

import numpy as np
import pathlib
import json
import evaluator

"""
For example, if the runs were
Run 1: [1, 4, 9]
Run 2: [2, 5, 8]
then [1, 5, 8] is a valid stratified Boostrap sample but not [1, 4, 5]
"""

# Configuration files
configs=(
    "annotated_submission.json",
    "grading_only_question_answer.json",
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

# Model names for output directories and files
model_names=(
    "gpt-4o-2024-08-06",
    "gpt-4.1-2025-04-14",
    "gpt-4.1-mini-2025-04-14",
    "gpt-4.1-nano",
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    "o4-mini"
)

base_test_path = pathlib.Path("tests", "test", "output")
regrading_path = pathlib.Path("tests", "test", "repeat_grading")
output_file_name = pathlib.Path("results", "aggregate_statistics.json")
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

def main():
    last_grading_prompt = None
    configs_to_test = {pathlib.Path(c).stem for c in configs}

    for model, model_name in zip(models, model_names):
        model_dir = base_test_path / model
        latest_runs = get_latest_runs(model_dir, configs_to_test)
        model_all_grades = np.zeros(6, dtype=int)

        for config_name, path in latest_runs.items():
            with open(model_dir / path, "r") as f:
                initial_run_dict = json.load(f)

            assert initial_run_dict["model_used"] == model  # the model matches

            grading_prompt = initial_run_dict["config"]["directives"]["regraded"]
            assert (grading_prompt == last_grading_prompt or last_grading_prompt
                    is None)  # all models must be graded with the same prompt!

            test_cases = initial_run_dict["test"]
            rating = [test_case["rating"] for test_case in test_cases]
            initial_regraded = [evaluator.parse_grade(test_case["regraded"])
                                for test_case in test_cases]

            # Check if regrading has been done
            # regrading_path / model / config_name (.json)
            # TODO: Rerun regrading

            model_all_grades += np.bincount(initial_regraded, minlength=6)

        print(model_all_grades[1:], model)

if __name__ == '__main__':
    main()
