"""
Compute statistics comparing two sequences of integer grades

Place the file(s) created after running and grading into the
input directory (--input_directory, default eval/).

Run evaluator to compute the statistics over the joined data
across ALL data files found. To compute statistics over multiple runs,
use aggregate_bootstrap_regrading.py instead, or call get_statistics directly.
"""

import argparse
import json
import os
import re
import scipy.stats as stats
import scipy.spatial.distance as spatial_distance
import pandas as pd
import numpy as np
import math


# Set to None to skip bootstrap test (slow!); otherwise, 0.95 is standard
# Bootstrap is automatically skipped if get_statistics is being imported
bootstrap_confidence = 0.95
bootstrap_N = 10_000


def parse_arguments():
    parser = argparse.ArgumentParser(description="Analyze and output statistics on grading data.")
    parser.add_argument("--input_directory", type=str, default="eval", help="Directory containing the input files.")
    parser.add_argument("--output_file", type=str, default="eval_output.json", help="File path to save the output JSON data.")
    parser.add_argument("--no_bootstrap", action="store_true", help="Disable bootstrap confidence intervals (faster).")
    return parser.parse_args()

def analyze_file(file_path, key1="rating", key2="regraded"):
    """
    Load and filter data from a JSON file.
    Returns items that have both rating keys and a non-empty prompt.
    Items with missing or empty prompts are excluded from analysis.
    """
    with open(file_path, 'r') as file:
        data = json.load(file)

    try:
        data = data['test']
    except TypeError:
        print('Format warning: This data does not contain a test!')

    return [
        item for item in data
        if key1 in item and key2 in item
        and 'prompt' in item and item['prompt'].strip()
    ]

def get_sentence_transformers_model():
    """Lazy-load the sentence_transformers module."""
    try:
        from sentence_transformers import SentenceTransformer

        t = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        # We want to avoid truncation as meaningful information may not be
        # mentioned until later in the LLM output, so we increase the limit.
        # This may lead to poorer embeddings on long text! Does not affect short text.
        t.max_seq_length = 384
        return t

    except ModuleNotFoundError:
        return None

def transformer_cosine_similarity(base_text, comparison_text, transformer=None):
    assert transformer is not None

    if len(comparison_text) > transformer.get_max_seq_length() * 4:
        print("Warning: text will be truncated as it exceeds transformer token limit: "
              f"{len(comparison_text)} characters")

    distance = spatial_distance.cosine(transformer.encode(base_text),
                                       transformer.encode(comparison_text))
    return 1 - distance  # similarity is 1 - "difference"

def get_similarity_statistics(data, key1="feedback", key2="llm_feedback"):
    transformer = get_sentence_transformers_model()
    if transformer is None:
        return None

    similarity_list = []
    for case in data:
        similarity = transformer_cosine_similarity(case[key1], case[key2], transformer=transformer)
        similarity_list.append(similarity)

    similarity_results = {
        "mean": np.mean(similarity_list),
        "quantiles": np.quantile(similarity_list, (0, 0.25, 0.5, 0.75, 1))
    }
    return similarity_results

def parse_grade(value):
    """Parse grade from various formats like '3', '3/5', '3.0', etc."""
    if isinstance(value, (int, float)):
        return int(value)
    
    value_str = str(value).strip()
    
    # Handle "X/5" format
    if '/' in value_str:
        try:
            numerator = value_str.split('/')[0].strip()
            return int(float(numerator))
        except (ValueError, IndexError):
            pass
    
    # Handle plain numbers (possibly with decimals)
    try:
        return int(float(value_str))
    except ValueError:
        pass
    
    # Try to extract first number from string
    match = re.search(r'\d+', value_str)
    if match:
        return int(match.group())
    
    raise ValueError(f"Could not parse grade from: {repr(value)}")

def get_statistics(data, key1="rating", key2="regraded", enable_boot=False):
    ratings = [parse_grade(item[key1]) for item in data]
    regraded = [parse_grade(item[key2]) for item in data]

    print('ratings ', ratings)
    print('regraded', regraded)

    # Correlation
    correlation = stats.pearsonr(ratings, regraded)[0]
    if enable_boot and bootstrap_confidence is not None:
        print(get_bootstrap(ratings, regraded))

    # Contingency Table
    contingency_table = pd.crosstab(pd.Series(ratings, name=key1),
                                    pd.Series(regraded, name=key2))

    # Kendall Tau measure of similarity
    kendall_tau = stats.kendalltau(ratings, regraded)

    # Spearman Rank
    spearman = stats.spearmanr(ratings, regraded)

    # Mean square error (MSE) and pairwise comparison metrics
    difference = np.array(ratings) - np.array(regraded)
    mean_error = abs(difference).mean()
    mean_difference = difference.mean()
    mean_square_error = np.linalg.norm(difference) / math.sqrt(len(difference))
    percent_agreement = (np.array(ratings) == np.array(regraded)).mean() * 100
    percent_close_match = (abs(np.array(ratings) - np.array(regraded)) <= 1.0).mean() * 100

    # Calculating disagreements and selecting the worst five
    for item in data:
        item["disagreement"] = abs(parse_grade(item[key1]) - parse_grade(item[key2]))
    worst_disagreements = sorted(data, key=lambda x: x["disagreement"], reverse=True)

    complete_results = {
        "mean_grade": np.array(ratings).mean(),
        "mean_llm_grade": np.array(regraded).mean(),
        "percent_agreement": percent_agreement,
        "percent_close_match": percent_close_match,
        "mean_difference": mean_difference,
        "mean_error": mean_error,
        "mean_square_error": mean_square_error,
        "correlation": correlation,
        "kendall_tau": kendall_tau[0],
        "spearman": spearman[0],
        "contingency_table": contingency_table.to_latex(),
        "worst_disagreements": worst_disagreements
    }

    return complete_results

def get_bootstrap(ratings, regraded):
    # Currently uses a simple paired bootstrap
    boot = stats.bootstrap((ratings, regraded),
                           lambda x, y: stats.pearsonr(x, y)[0],
                           n_resamples=bootstrap_N, paired=True)
    correlation_ci = boot.confidence_interval
    correlation_boot = boot.bootstrap_distribution.mean()
    return correlation_ci, correlation_boot


def main():
    args = parse_arguments()
    
    file_results = {}
    # Use os.walk to recursively search through subdirectories
    for root, dirs, files in os.walk(args.input_directory):
        for filename in files:
            if filename.endswith(".json"):
                file_path = os.path.join(root, filename)
                print(f"Analyzing {file_path}")
                file_data = analyze_file(file_path)
                if file_data:  # Only process if we have data
                    file_results[file_path] = get_statistics(file_data, enable_boot=not args.no_bootstrap)

    if args.output_file:
        with open(args.output_file, 'w') as out_file:
            json.dump(file_results, out_file, indent=4, default=str)

    # Print summary for each file
    for file_path, statistics_dict in file_results.items():
        print(f"\n=== Results for {file_path} ===")
        for key, stat_value in statistics_dict.items():
            if key != 'worst_disagreements':
                print(f"{key}: {stat_value}")
    
    print(f'\nSee {args.output_file} for complete output (+ worst disagreements)')
    print(f'Processed {len(file_results)} files with individual statistics')


if __name__ == "__main__":
    main()
