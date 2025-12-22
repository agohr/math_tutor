import gradio as gr
import openai
import argparse
import os
import base64
import tempfile
import atexit
import json
import re
import asyncio
import numpy as np
import sys

from dotenv import load_dotenv
import time
from tqdm import tqdm

import evaluator
import token_usage
from token_usage import tracked_chat_completion, async_cached_tracked_chat_completion, username, session_costs

load_dotenv()

# Set the OpenAI API Key
openai.api_key = os.getenv("OPENAI_API_KEY")
client_openai = openai.Client()

models_openai = {"text": "gpt-5.2", "vision": "gpt-4o", "precheck": "gpt-4.1-mini"}
# Overrides the text model in models_openai in the format stage: model
directives_model = {"question": "gpt-4.1-mini", "solution": "gpt-4.1-mini"}
# Overrides the temperature passed as an argument
directives_temperature = {"question": 0.0, "solution": 0.0}

# Reasoning models whitelist - these models have special handling requirements
REASONING_MODELS = {
    "gpt-5", "gpt-5-mini", "gpt-5-nano", "o4-mini"
}

WARNING_ACKNOWLEDGED = False


def is_reasoning_model(model_name):
    """Check if a model is a reasoning model that requires special handling."""
    if not model_name:
        return False
    
    # Check exact matches first
    if model_name in REASONING_MODELS:
        return True
    
    # Check for partial matches (handles versioned models like gpt-5-2025-04-14)
    return any(reasoning_model in model_name.lower() 
              for reasoning_model in REASONING_MODELS)


def prepare_reasoning_model_parameters(**kwargs):
    """Prepare parameters for reasoning model API calls."""
    # Remove parameters that reasoning models don't support
    reasoning_params = kwargs.copy()
    
    # Reasoning models typically don't support:
    # - Custom temperature 
    # - Custom seed
    if "temperature" in reasoning_params:
        print("Note: Removing temperature parameter for reasoning model compatibility")
        del reasoning_params["temperature"]
    
    # Some reasoning models don't support seed parameter
    if "seed" in reasoning_params:
        print("Note: Removing seed parameter for reasoning model compatibility")
        del reasoning_params["seed"]
    
    # Handle model-specific parameters
    model_name = reasoning_params.get("model", "")
    
    # Remove problematic parameters for all reasoning models
    if "max_tokens" in reasoning_params:
        del reasoning_params["max_tokens"]
    
    if "verbosity" in reasoning_params:
        del reasoning_params["verbosity"]
    
    # Add GPT-5 specific parameters with defaults if not specified
    if model_name.startswith("gpt-5"):
        # Set reasoning_effort to "medium" if not specified (GPT-5 default)
        if "reasoning_effort" not in reasoning_params:
            reasoning_params["reasoning_effort"] = "medium"
    
    return reasoning_params


class Settings:
    model_seed = 128  # arbitrary fixed seed

    default_directives = {
        "question": "Extract the question from the assignment data: {input}",
        "solution": "Write an exemplary solution to the question extracted from the assignment data: {question}",
        "optimized_solution": "We have the following question/solution pair: \n\n{question}\n\n{solution}. Rewrite the solution for clarity and conciseness.",
        "output": "Here is an assignment handed in by a student: \n\n{input}. Give concise but helpful feedback on the correctness and completeness of the student's work. Use the following exemplary solution as guidance when evaluating the student's work: \n\n{optimized_solution}\n\nIf the exemplary solution uses a better approach than the one used by the student, give them a helpful hint in this direction as part of your feedback, without revealing that solution in full."
    }

    default_config = {
        "image_instructions": "Convert the mathematical text in this image accurately to latex. If there is no text visible, describe the image. If text is accompanied by visual elements like drawings, describe these and highlight how (if so) they what additional information relevant to the text they provide. Your goal here should be to produce a textual representation of the image that enables someone without vision to work with all of the information contained in the image.",
        "context_instructions": "The following data contains a solution to a homework assignment submitted by a student. Our task will be to give detailed feedback on the correctness of the student's work.\n\n",
        "precheck_instructions": "Sometimes a user will mistakenly press the enter key to start a new paragraph in the gradio interface of the submission server. In that case, the submission will be incomplete. Check whether it looks like this happened here:\n\n{assignment_data}\n\n Common signs for this are that only a statement of the problem has been submitted, or that the argument stops at a point when it shouldn't but when it would be natural to start a new paragraph. Only answer this question strictly with 'yes' or 'no', since it will be used to automatically reject the submission as incomplete or to accept it for further processing.",
        "assistant_identity": "You are a mathematics teaching assistant.",
        "directives": {}
    }

    def __init__(self):
        parser = argparse.ArgumentParser(description='Math Autocorrector')
        parser.add_argument('--temperature', type=float, default=0.0, help='Temperature for response generation.')
        parser.add_argument('--config', type=str, default='best_three/systematic5.0.json', help='Path to config file.')
        parser.add_argument('--problem_dir', type=str, default=None, help='Path to problem directory for running in batch mode.')
        parser.add_argument('--run_async', action='store_true', help='[This parameter currently has no effect] Do you want to send multiple requests to the API at the same time?')
        parser.add_argument('--no_cache', action='store_false', help='Use the cache to store results, and retrieve results from the cache when identical requests would be sent.')
        parser.add_argument('--model', type=str, default=None, help='Override the model used for all API calls (e.g., gpt-4.1, gpt-4o-2024-08-06).')
        # parser.add_argument('--generate_grade', action='store_true', help='Do you want to generate a grade based off feedback?')
        # parser.add_argument('--generate_solution', action='store_true', help='Do you want to generate a solution to a question?')
        # parser.add_argument('--generate_feedback', action='store_true', help='Do you want to generate feedback to a solution to a question?')
        args = parser.parse_args()

        # async_mode currently has no effect, as we always run batch mode in async
        self.async_mode = args.run_async or (args.problem_dir is not None)
        self.temperature = args.temperature
        self.config_path = args.config
        self.enable_cache = args.no_cache
        self.model_override = args.model
        print('Cache in use:', self.enable_cache)
        if self.model_override:
            print(f'Model override: {self.model_override}')

        if args.problem_dir is not None:
            self.problem_dir = os.path.join('tests', args.problem_dir)
        else:
            self.problem_dir = None

        self.config = {'directives': {}}

    def set_config_to_default(self):
        self.config = self.default_config

    @property
    def problem_files(self):
        for file in os.listdir(self.problem_dir):
            if file.endswith(".json"):
                yield os.path.join(self.problem_dir, file)

    @property
    def directives(self):
        if directives := self.config["directives"]:
            return directives
        else:
            print("Warning: Directives not specified, using default directives")
            return self.default_directives

    @property
    def variables(self):
        return self.config.get("variables", dict())

    @property
    def parameters(self) -> dict:
        return self.config.get("parameters", dict())

    def get_directive_parameters(self, directive):
        default_parameters = {
            "model": directives_model.get(directive, models_openai["text"]),
            "temperature": directives_temperature.get(directive, 0.0)
        }
        new_default_parameters = default_parameters | self.parameters.get("default", dict())
        directive_parameters = new_default_parameters | self.parameters.get(directive, dict())
        final_parameters = directive_parameters | self.parameters.get("override", dict())
        
        # Apply command line model override if specified
        if self.model_override:
            final_parameters["model"] = self.model_override
        
        # Handle reasoning models that don't support standard parameters
        if is_reasoning_model(final_parameters["model"]):
            final_parameters = prepare_reasoning_model_parameters(**final_parameters)
            
        return final_parameters


settings = Settings()

temp_files = []

def convert_grade(grade):
    # Check if the grade is an integer within the 0-5 range
    try:
        grade_int = int(grade)
        if 0 <= grade_int <= 5:
            return grade_int
    except ValueError:
        pass
    
    # Check if the grade is a string fraction of the form "x/5"
    if isinstance(grade, str) and grade.endswith('/5'):
        try:
            numerator = int(grade.split('/')[0])
            if 0 <= numerator <= 5:
                return numerator
        except ValueError:
            pass
    
    # If the input is not valid, raise an error
    raise ValueError(f"Invalid grade format: {grade}. Please provide an integer (0-5) or a fraction of the form 'x/5'.")

def extract_json(text):
    '''This function takes a string and tries to find a block of json code to return in it. It assumes that json code starts with ```json and ends with ```.'''
    json_code = re.search(r"```json(.*?)```", text, re.DOTALL)
    if json_code is not None:
        return json_code.group(1)
    else:
        return text

def str_to_int(s):
    '''This function will take a string and return the integer value of the string.'''
    try:
        return int(s)
    except:
        for i, c in enumerate(s):
            if c.isdigit():
                return int(s[i])
    return 0

def create_temp_file_with_text(text):
    global temp_files
    with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.txt',
                                     encoding='utf-8') as temp_file:
        temp_file.write(text)
        temp_files.append(temp_file.name)
        return temp_file.name

def cleanup_temp_files():
    global temp_files
    for file_path in temp_files:
        try:
            os.remove(file_path)
        except OSError:
            pass  # Handle any error if the file was already removed or cannot be removed

# Function to encode the image
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def transcribe_image(image, temperature=0.0):
    '''This function will take an image and return latex of the text.'''

    # Encode the image
    encoded_image = encode_image(image)
    prompt = settings.config["image_instructions"]

    response = tracked_chat_completion(
        client_openai, 'image',
        model=models_openai["vision"],
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_image}"}}
                ]
            }
        ],
        temperature=temperature,
        max_tokens=1000,
    )
    return response.choices[0].message.content


def process_directives(assignment_data, directives, temperature=0.0, variables=None):
    '''This function takes the assignment data and applies a sequence of directives to it. The sequence of directives is given as a json-encoded dictionary, where the key is the name of the output of a directive and the directives are fstrings that can take in variables already defined.'''
    assignment_data = {"prompt": assignment_data[0], "output": assignment_data[1]}
    return asyncio.run(async_process_directives(openai.AsyncOpenAI(), assignment_data, directives, temperature, variables))

async def async_process_directives(async_client, assignment_data, directives, temperature=0.0, variables=None):
    '''This function takes the assignment data and applies a sequence of directives to it. The sequence of directives is given as a json-encoded dictionary, where the key is the name of the output of a directive and the directives are fstrings that can take in variables already defined.'''
    global WARNING_ACKNOWLEDGED

    keys = directives.keys()
    assert keys  # require directives dictionary to be non-empty

    # check which keys from the directives directory are None
    # These are required input variables
    required_keys = [key for key in keys if directives[key] is None]

    # if required_keys are empty, then this is a legacy directives file that does not declare inputs
    # in this case, we set required_keys to be all keys in the assignment_data
    # and print out a legacy warning and wait for the user to acknowledge the warning
    if not required_keys:
        required_keys = assignment_data.keys()
        print("Warning: This directives file does not declare input variables. Please update the directives file to include input variables.")

        if not WARNING_ACKNOWLEDGED:
            try:
                input("Press Enter to acknowledge the warning and continue.")
            except EOFError:
                print("Running in non-interactive mode, continuing automatically.")
            WARNING_ACKNOWLEDGED = True

    # Check if the required keys are in the assignment_data
    for key in required_keys:
        if key not in assignment_data:
            raise ValueError(f"Key {key} is missing in the assignment_data. Please ensure that all required keys are present.")
    
    # create a copy of the assignment data that has only the expected input keys
    # This means that the assignment data should now only contain the keys that are required by the directives
    filtered_assignment = {key: assignment_data[key] for key in assignment_data if key in required_keys}
    
    # Remove keys from the directives dictionary that are None
    keys = [key for key in keys if directives[key] is not None]
    directives = {key: directives[key] for key in keys}

    # create a state dictionary
    # add values specified in the input file to state dictionary, where directives take priority
    state = filtered_assignment | directives.copy()

    # ensure that there is no overlap between directives and variables
    if set(directives.keys()).intersection(set(variables.keys())):
        raise ValueError(f"There is an overlap between {directives = } and {variables = }. Please ensure keys are unique.")
    # add additional variables from the config to state dictionary - these will not be processed as directives
    # this is a union of disjoint sets
    state_with_variables = state.copy() | variables
    state_with_variables = state_with_variables

    # iterate through directives __in order__!
    response = "Not defined. This is an error and should be reported. E1"
    for key in keys:
        parameters = settings.get_directive_parameters(directive=key)
        raw_prompt = directives[key]
        try:
            # to allow (silently ignore) latex content that we expect to find,
            # e.g. \item{0/5 marks}, we
            format_defaults = {f'{m}/5 marks': f'{m}/5 marks' for m in range(6)}
            prompt = raw_prompt.format(**(format_defaults | state_with_variables))
        except KeyError as e:
            print(f"Warning: Prompt contains unescaped curly braces (caught KeyError: {e}). "
                  "Attempting fallback method:")
            prompt = raw_prompt
            for k, v in state_with_variables.items():
                k_bracket = '{' + k + '}'
                if k_bracket in prompt:
                    v_str = str(v)
                    v_shortened = (v_str[:60] + '...') if len(v_str) > 63 else v_str
                    print(f"- Replaced {k_bracket} = {v_shortened}")
                    prompt = prompt.replace(k_bracket, v_str)

        print(f"Step: {key} | Temperature: {temperature} | Model: {parameters['model']}")
        prompt_start = repr(prompt)[:140]
        print((prompt_start[:67] + '...') if len(prompt) > 70 else prompt_start)

        # Build parameters for async call
        call_params = {
            "model": parameters["model"],
            "messages": [{"role": "user", "content": prompt}],
            "seed": settings.model_seed,
            "max_tokens": 4000,
        }
        
        # Add temperature only if present (reasoning models don't have it)
        if "temperature" in parameters:
            call_params["temperature"] = parameters["temperature"]
        
        response = await async_cached_tracked_chat_completion(
            async_client, key, enable_cache=settings.enable_cache,
            **call_params
        )
        # response = raw_response.choices[0].message.content
        state[key] = response
        state_with_variables[key] = response

    # json_state = json.dumps(state)
    return response, assignment_data | state

async def gather_async_directives_tasks(async_client, data, *args, **kwargs):
    """Processing the return value of this function with asyncio.run is equivalent to:
        [process_directives(assignment_data, ...) for assignment_data in data]
    """
    return await asyncio.gather(
        *(async_process_directives(async_client, assignment_data, *args, **kwargs)
        for assignment_data in data)
    )

def get_assignment_data(text, image=None, knowledge=None, temperature=0.0):
    # context_instructions is only prepended to the first/prompt directive
    assignment_data = settings.config["context_instructions"]

    if image is None:
        assignment_data += text
    else:
        latex_code = transcribe_image(image, temperature)
        assignment_data += f"Reading a submitted image yields the following result:\n\n {latex_code}\n"
        # considered including assignment_data += "No additional images received." in the else case
        # this has been removed as we no longer expect images to be processed
        if len(text) > 0:
            assignment_data += f"Manually entered data on the assignment/solution: {text}\n"

    if knowledge is not None:
        assignment_data += f"Additional information:\n{knowledge}"

    return assignment_data

def run_precheck(assignment_data, temperature=0.0):
    submission_check = tracked_chat_completion(
        client_openai, 'precheck',
        model=models_openai["precheck"],
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text",
                     "text": settings.config["precheck_instructions"].format(
                         assignment_data=assignment_data
                         )}
                ]
            }
        ],
        max_tokens=1,
        temperature=temperature
    )
    response = submission_check.choices[0].message.content
    return response

def process_input(question, solution, temperature=0.0, precheck=True, image=None, knowledge=None, mark=None):
    '''This function will take completed assignments from the user interface (text and/or image) and return the feedback/grades to the user.
    question: str
    solution: str'''

    assignment_data = (get_assignment_data(question, image, knowledge, temperature), solution)

    # Check if the submitted data looks like the user has mistakenly pressed the enter key in the gradio interface when they only wanted to start a new paragraph
    if precheck and run_precheck('\n'.join(assignment_data), temperature).lower() == "yes":
        return "Submission seems incomplete. Please resubmit. Maybe you pressed `Enter` to start a new paragraph. A new paragraph is started by `Enter+Shift`.", "", None, ""

    feedback, thoughts = process_directives(assignment_data, settings.directives, temperature, variables={"mark": mark})
    
    # Extract llm_feedback from thoughts dictionary if available
    displayed_output = thoughts.get("llm_feedback", feedback)
    
    temp_file_text = f"Input: {assignment_data}\n\nImage: {image}\n\nKnowledge: {knowledge}\n\nTemperature: {temperature}\n\nThoughts: {thoughts}\n\n Feedback: {feedback}"
    try:
        download_data = create_temp_file_with_text(temp_file_text)
    except:
        download_data = create_temp_file_with_text("Error: Could not create download file.")

    prompt_cost = session_costs[0]
    token_usage.reset_counter()
    cost_info = f"Prompt: ${prompt_cost:10f}\tSession: ${sum(session_costs):10f}"

    return displayed_output, replace_latex_delimiters(displayed_output), download_data, cost_info

def process_batch_input(data, image=None, knowledge=None, temperature=0.0):
    '''This function will take completed assignments from the batch processing step and return the feedback/grades to the user.
    data: list[of dicts].'''

    if isinstance(data, dict):
        raise NotImplementedError
        # run single
        # assignment_data = get_assignment_data(data["prompt"], image, temperature)
        # final_responses, thoughts = process_directives(assignment_data, settings.directives, temperature, variables=settings.variables)
    else:
        # run in parallel
        assert image is None  # parallel runs do not support image processing
        assert knowledge is None  # parallel runs do not (yet) support context knowledge
        async_client = openai.AsyncOpenAI()

        for test_case in data:
            test_case["prompt"] = get_assignment_data(test_case["prompt"])

        coroutines = gather_async_directives_tasks(
            async_client, data, settings.directives, temperature, settings.variables
        )
        responses = asyncio.run(coroutines)
        # print(responses)
        final_responses = [x[0] for x in responses]
        thoughts = [x[1] for x in responses]

    token_usage.reset_counter()

    return final_responses, thoughts


def replace_latex_delimiters(feedback):
    r"""Replace \( and \) with $, and \[ and \] with $$"""
    feedback = re.sub(r"\\\(|\\\)", "$", feedback)
    feedback = re.sub(r"\\\[|\\\]", "$$", feedback)
    return feedback


def batch_workflow():
    """
    Run problem sets in the directory given by settings.problem_dir through the tutor
    Returns {"config": {...}, "tests": [...]}
    """
    results = []
    for problem_set_file_path in settings.problem_files:
        results.append(get_batch_feedback_on_problem_set(problem_set_file_path))
    return {"config": settings.config, "tests": results}


def get_batch_feedback_on_problem_set(file_path):
    with open(file_path, "rb") as f:
        data = json.load(f)

    try:
        n = len(data)
        print(f"Processing {file_path} | Number of problems found: {n}")
        our_grades = [int(q["rating"]) for q in data]
    except ValueError:
        raise ValueError(f"No files found in problem directory {settings.problem_dir}")

    # pretty-print dictionary as table
    print("{:<8} {:<16}".format('Defaults', 'Model'))
    for k, v in (models_openai | directives_model).items():
        print("{:<8} {:<16}".format(k, v))

    if settings.async_mode:
        input(f"Enter to confirm asynchronous processing of {n} questions (Ctrl-C to interrupt)\n>>> ")

        responses, thoughts = process_batch_input(data, temperature=0.0)

        # Determine the model being used
        model_used = settings.model_override if settings.model_override else "default"
        
        # Create model-specific output directory
        dir_new = os.path.join(settings.problem_dir, "output", model_used)
        os.makedirs(dir_new, exist_ok=True)
        label_config = os.path.basename(settings.config_path).rstrip('.json')
        label_problem_set = os.path.basename(file_path)
        file_new = os.path.join(
            dir_new,
            f"{time.strftime('%y-%m-%dT%H-%M')}-{label_config}-{label_problem_set}"
        )
        print(f"writing to {file_new}")
        output_data = {"config": settings.config, "model_used": model_used, "test": thoughts}
        with open(file_new, "w") as f:
            json.dump(output_data, f, indent=4)
    else:
        raise NotImplementedError

    print("==== STATISTICS =====")

    try:
        grades = [convert_grade(q) for q in responses]
    except ValueError as error:
        print('ValueError:', error)

    """
    if grades:
        try:
            grades = np.array(grades)
            our_grades = np.array(our_grades)
            print(f"Mean grade: {grades.mean()}")
            print(f"Our mean grade: {our_grades.mean()}")
            print(f"Mean difference: {np.abs(grades - our_grades).mean()}")
            print(f"Correlation: {np.corrcoef(grades, our_grades)}")
            print(f"K-T: ({evaluator.stats.kendalltau(grades, our_grades)})")

            similarity = evaluator.get_similarity_statistics(
                thoughts, key1="feedback", key2="llm_feedback"
                )
            if similarity is not None:
                print(f"Similarity: {similarity['mean']} (Quartiles {' : '.join(map(str, similarity['quantiles']))})")
            else:
                print("Similarity not available.")
        except:
            print("Could not generate statistics for comparing human grades with LLM grades")
    else:
        print("Grades not available.")
    """
    return thoughts


def main():
    '''Main function opening the user interface and handing over the input to the process_input function, which implements the backend logic, i.e. the autocorrecting math grader/tutor.'''
    global config_data
    global settings

    atexit.register(cleanup_temp_files)
    config_path = settings.config_path

    if settings.problem_dir is None:  # Interface mode - use defaults
        settings.set_config_to_default()

    try:
        with open(os.path.join('configs', config_path)) as f:
            config_data = json.load(f)
            print("Config file found.")
            for key in config_data:
                settings.config[key] = config_data[key]  # mutates the config in settings.config
                print(f"Setting {key} to {repr(config_data[key])}")
    except Exception as e:
        print("No config file found.")
        raise e

    # Batch mode
    if settings.problem_dir is not None:
        print("Running in batch mode.")
        batch_workflow()
        print("Cache reads:", token_usage.cache_reads[0])
        return

    # Interface mode
    interface_cost_string = f"Tracked ({username})" if username else "Not tracked"

    interface = gr.Interface(
        fn=process_input,
        inputs=[
            gr.Textbox(),
            gr.Textbox(),
            gr.Slider(minimum=0.0, maximum=1.0, step=0.1, value=0.0, label="Temperature"),
            gr.Checkbox(label="Precheck", value=True)
        ],
        additional_inputs = [
            gr.Image(type="filepath"),
            gr.File(label="Background Knowledge"),
        ],
        outputs=[
            gr.Textbox(label="Displayed Output"),
            gr.Markdown(label=".md Display", latex_delimiters=[{ "left": "$", "right": "$", "display": False}]),
            gr.File(label="Download File"),
            gr.Textbox(label=f"Total Cost - {interface_cost_string}")
        ]
    )

    interface.launch(inbrowser=True)


if __name__ == "__main__":
    main()
