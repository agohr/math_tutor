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

Batch processing mode, or more precisely batch processing mode run by specificshell scripts (see below), is used for the bulk of the evaluation work in our paper.

## Configuration

Adjust the program's behavior via the config file, setting parameters like instructions for the various processing steps, and task directives. Different configurations can be used for different tasks and can be specified via the `--config` command line parameter at startup as indicated in the previous section. This can drastically change behaviour, e.g. it would be possible to change the program from a evaluator to a problem solver just by changing the configuration file. Various pre-set configuration files are provided in the `configs` directory.

## Evaluation Scripts

Two shell scripts are provided for running comprehensive evaluations across multiple models and configurations:

### run_advanced_test_comparison.sh

Runs evaluations on the advanced test dataset with multiple models and configurations in parallel.

```bash
# Run without cost tracking (default)
./run_advanced_test_comparison.sh

# Run with cost tracking (requires confirmation)
./run_advanced_test_comparison.sh --track-costs

# Show help
./run_advanced_test_comparison.sh --help
```

### run_regrading_comparison.sh

Runs evaluations on the main test dataset with regrading across multiple models and configurations.

```bash
# Run without cost tracking (default)
./run_regrading_comparison.sh

# Run with cost tracking (requires confirmation)
./run_regrading_comparison.sh --track-costs

# Show help
./run_regrading_comparison.sh --help
```

### Cost Tracking (Optional)

Cost tracking is an **optional feature** that estimates API costs based on published pricing rates at the time this research artifact was created. 

⚠️ **Important**: These costs are estimates only. Actual costs may vary as API providers update their pricing. Cost tracking requires explicit opt-in with the `--track-costs` flag and interactive confirmation. We do not plan to update the cost data in token_usage.py to reflect current pricing, so future users will have to modify the cost data to reflect current pricing. We also do not plan to update this data to include new models.

For detailed information about cost tracking, see [COST_TRACKING_README.md](COST_TRACKING_README.md).

## Cleanup

<!--The program automatically removes any temporary files created during operation.-->
The program creates temporary files under the cache and usage subdirectories,
which may be freely deleted.
