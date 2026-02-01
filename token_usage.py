"""Tracks token usage locally when TOKEN_USAGE_USERNAME is set in .env."""

import os
import csv
import pathlib
import asyncio
from dotenv import load_dotenv
from hashlib import sha256
import json
import base64


load_dotenv()

username = os.getenv("TOKEN_USAGE_USERNAME", default=None)

# Load cost data from external JSON file
def load_cost_per_token():
    """Load model cost data from model_costs.json."""
    cost_file = pathlib.Path(__file__).parent / "model_costs.json"
    with open(cost_file, 'r') as f:
        return json.load(f)

cost_per_token = load_cost_per_token()

session_costs = [0]
cache_reads = [0]

# Lock used for asynchronous processing
record_lock = asyncio.Lock()
cache_lock = asyncio.Lock()


def reset_counter():
    session_costs.insert(0, 0)


async def async_cached_tracked_chat_completion(client, label, *args, enable_cache=True, **kwargs):
    if not enable_cache:
        response = await async_tracked_chat_completion(client, label, *args, **kwargs)
        return response.choices[0].message.content

    async with cache_lock:
        dictionary = {}
        # merge dictionaries together, overwriting clashing keys
        for file in os.listdir('cache'):
            complete_file_path = os.path.join('cache', file)
            if os.path.isfile(complete_file_path):
                with open(complete_file_path, 'r') as f:
                    dictionary |= json.load(f)

    key = base64.b64encode(sha256(bytes(str(kwargs), encoding='utf-8')).digest()).decode('utf-8')
    if key in dictionary:
        cache_reads[0] += 1
        return dictionary[key]
    else:
        response = await async_tracked_chat_completion(client, label, *args, **kwargs)
        response = response.choices[0].message.content
        async with cache_lock:
            my_cache = os.path.join('cache', f'cache_dictionary-{username}.json')
            if not os.path.exists(my_cache):
                with open(my_cache, 'w') as f:
                    f.write('{}')

            with open(my_cache, 'r+') as f:
                dictionary = json.load(f)
                dictionary[key] = response
                f.seek(0)  # seek to start to overwrite file
                json.dump(dictionary, f, indent=2)
                f.truncate()

        return response

async def record(usage, label, model):
    # Extract reasoning tokens if available (for reasoning models like o1, o3, GPT-5, o4-mini)
    reasoning_tokens = 0
    if hasattr(usage, 'completion_tokens_details') and usage.completion_tokens_details is not None:
        reasoning_tokens = getattr(usage.completion_tokens_details, 'reasoning_tokens', 0) or 0
    
    # Calculate cost including reasoning tokens (which are billed at output token rate)
    cost = (usage.prompt_tokens * cost_per_token[model][0]
            + (usage.completion_tokens + reasoning_tokens) * cost_per_token[model][1])
    session_costs[0] += cost

    columns = (
        label, model, f"{cost:10f}",
        usage.prompt_tokens, usage.completion_tokens, reasoning_tokens, usage.total_tokens
    )

    path_to_usage_dir = pathlib.Path.cwd() / "usage"
    if not path_to_usage_dir.is_dir():
        os.mkdir(pathlib.Path.cwd() / "usage")

    try:
        async with record_lock:
            with open(path_to_usage_dir / f"usage-{username}.csv", "a+") as f:
                f.write("\t".join(map(str, columns)) + "\n")
    except FileNotFoundError as err:
        print(f"Warning: FileNotFoundError({err}) when writing to tracker.")


def is_reasoning_model_local(model_name):
    """Local copy of reasoning model detection to avoid circular imports."""
    if not model_name:
        return False
    
    reasoning_models = {
        "gpt-5", "gpt-5-mini", "gpt-5-nano", "o4-mini"
    }
    
    # Check exact matches first
    if model_name in reasoning_models:
        return True
    
    # Check for partial matches
    return any(reasoning_model in model_name.lower() 
              for reasoning_model in reasoning_models)


def prepare_reasoning_parameters(**kwargs):
    """Prepare parameters for reasoning model API calls."""
    reasoning_params = kwargs.copy()
    
    if "temperature" in reasoning_params:
        del reasoning_params["temperature"]
    
    if "seed" in reasoning_params:
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


def tracked_chat_completion(client, label, *args, **kwargs):
    """Return a chat completion using the OpenAI API with the given parameters.
    When TOKEN_USAGE_USERNAME is set in .env, tracks usage in a .csv.

    Signature matches client_openai.chat.completions.create, except for
    the first and second positional arguments which are:
        client: the OpenAI client instance to use
        label: the string to record alongside the usage
    """
    
    # Handle reasoning models differently
    model_name = kwargs.get("model", "unknown")
    if is_reasoning_model_local(model_name):
        kwargs = prepare_reasoning_parameters(**kwargs)

    response = client.chat.completions.create(*args, **kwargs)
    if username is not None:
        asyncio.run(record(response.usage, label, model_name))
    return response


async def async_tracked_chat_completion(async_client, label, *args, **kwargs):
    """Async version of tracked_chat_completion. See tracked_chat_completion
    for description and signature."""

    # Handle reasoning models differently
    model_name = kwargs.get("model", "unknown")
    if is_reasoning_model_local(model_name):
        kwargs = prepare_reasoning_parameters(**kwargs)

    #response = await cache(async_client, args, kwargs)
    response = await async_client.chat.completions.create(*args, **kwargs)
    if username is not None:
        await record(response.usage, label, model_name)
    return response


if __name__ == "__main__":
    total = 0
    total_tok = [0, 0, 0, 0]  # [input, output, reasoning, total]

    path_to_usage_dir = pathlib.Path.cwd() / "usage"
    with open(path_to_usage_dir / f"usage-{username}.csv", "r") as f:
        spamreader = csv.reader(f, delimiter='\t', quotechar='|')
        for row in spamreader:
            total += float(row[2])
            total_tok[0] += int(row[3])  # prompt_tokens
            total_tok[1] += int(row[4])  # completion_tokens
            # Handle both old format (6 columns) and new format (7 columns)
            if len(row) >= 7:
                total_tok[2] += int(row[5])  # reasoning_tokens
                total_tok[3] += int(row[6])  # total_tokens
            else:
                # Old format: reasoning_tokens not tracked
                total_tok[3] += int(row[5])  # total_tokens

    print(f'The total usage for {username} is ${total:2f},')
    print(f'which breaks down into {total_tok} (input, output, reasoning, total) tokens.')
