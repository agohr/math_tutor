# Math Autocorrector: Accompanying Code and Data for the Paper "Automated Feedback Generation for Undergraduate Mathematics: Development and Evaluation of an AI Teaching Assistant"

## Overview

The present repository contains code and supplementary data for the paper "Automated Feedback Generation for Undergraduate Mathematics: Development and Evaluation of an AI Teaching Assistant".

## Installation

1. **Clone the Repository**: Clone this repository to your local machine.

2. **Python Environment**: Create a Python virtualenv with Python3.10 or higher, and use

   ```bash
   pip install -r requirements.txt
   ```

   to install the requirements.

3. **Activate the Environment**:

   Use the following command to activate the environment:

   ```bash
   pyenv activate <environment-name>
   ```
   if the environment has been set up using pip/pyenv.

4. **Environment Variables**: Use a dotenv file to set `OPENAI_API_KEY` in your environment. You have to bring your own API key.

## Usage

1. **Running the Program**: Start the program by running `math_tutor.py`.

2. **User Interface**: By default, the program launches a Gradio interface in your browser for submitting homework assignments. This interface can be used to test the system on freely chosen individual questions.

3. **Providing Inputs**: 
   - Enter homework text in the textbox.
   - Upload an image of the homework.

4. **Receiving Feedback**: The program processes inputs and displays feedback in the output section.

## Command Line Parameters
### Interface Mode
By default, the program will launch a Gradio interface.

- `--temperature` (float): Sets the temperature for response generation (default: 0.0). This parameter is mainly important if a non-reasoning language model is used, which may be a reasonable choice for tasks which are mathematically relatively easy.
- `--config` (str): Path to the configuration file relative to the `configs` directory. If not specified, `configs/systematic5.0.json` is used, as in the testing reported in the paper, this workflow performed best on the advanced test questions.

   Example Usage:
   ```bash
   python math_tutor.py --temperature 0.5 --config path/to/config.json
   ```

### Batch Mode
To use the program in batch processing mode, use the following argument:

- `--problem_dir` (str): Path to the directory containing a .json file of questions, relative to the `test` directory.

This will make requests to the OpenAI API asynchronously by creating one thread per test case.

Batch processing mode, or more precisely batch processing mode run by specific shell scripts (see below), is used for the bulk of the evaluation work in our paper.

## Configuration

Adjust the program's behavior via the config file, setting parameters like instructions for the various processing steps, and task directives. Different configurations can be used for different tasks and can be specified via the `--config` command line parameter at startup as indicated in the previous section. This can drastically change behaviour, e.g. it would be possible to change the program from a evaluator to a problem solver just by changing the configuration file. Various pre-set configuration files are provided in the `configs` directory.

## Evaluation Scripts

Multiple scripts are provided for running comprehensive evaluations across different test datasets, models, and configurations:

### run_regrading_comparison.sh

Runs evaluations on the main test dataset with regrading across multiple models and configurations.

```bash
# Run
./run_regrading_comparison.sh

# Show help
./run_regrading_comparison.sh --help
```

### run_advanced_test_comparison.sh

Runs evaluations on the advanced test dataset with multiple models and configurations in parallel.

```bash
# Run
./run_advanced_test_comparison.sh

# Show help
./run_advanced_test_comparison.sh --help
```

### run_advanced_test_with_hints_comparison.py

Runs evaluations on the advanced test dataset with hints across multiple models and configurations. Supports parallel execution.

```bash
# Run with default settings
python run_advanced_test_with_hints_comparison.py

# Run with custom number of parallel workers
python run_advanced_test_with_hints_comparison.py --max-workers 8

# Show help
python run_advanced_test_with_hints_comparison.py --help
```

### run_ghosts_comparison.py

Runs evaluations on the ghosts_9jan dataset across multiple models and configurations. Supports parallel execution.

```bash
# Run with default settings
python run_ghosts_comparison.py

# Run with custom number of parallel workers
python run_ghosts_comparison.py --max-workers 8

# Show help
python run_ghosts_comparison.py --help
```

## Processing and Utility Scripts

### evaluator.py

Core evaluation script that computes statistical comparisons between AI-generated grades and ground truth grades. Calculates Pearson correlation, Kendall tau, Spearman rank correlation, percent agreement, and other metrics.

```bash
# Evaluate results from a directory
python evaluator.py --input_directory tests/test/output/gpt-5 --output_file results/gpt-5_eval.json

# Skip bootstrap confidence intervals (faster)
python evaluator.py --input_directory <dir> --output_file <file> --no_bootstrap
```

This script is called automatically by the evaluation comparison scripts, but can also be used independently.

### aggregate_eval_stats.py

Helper script to aggregate evaluation statistics from per-file results. Computes weighted averages of correlation metrics across all files for a model.

```bash
# Extract a specific statistic from evaluation results
python aggregate_eval_stats.py <json_file> <stat_name>

# Example: Get Pearson correlation
python aggregate_eval_stats.py results/evaluations/gpt-5_comparison.json correlation

# Available statistics: correlation, kendall_tau, spearman, percent_agreement, percent_close_match
```

### token_usage.py

Tracks token usage locally when `TOKEN_USAGE_USERNAME` is set in `.env`. Automatically logs API usage to CSV files in the `usage/` directory during program execution.

```bash
# View cumulative token usage statistics
python token_usage.py
```

The script automatically tracks:
- Prompt tokens, completion tokens, and reasoning tokens (for reasoning models)
- Cost per API call based on model pricing
- Session-level cost tracking

## Cleanup

<!--The program automatically removes any temporary files created during operation.-->
The program creates temporary files under the cache and usage subdirectories,
which may be freely deleted.
