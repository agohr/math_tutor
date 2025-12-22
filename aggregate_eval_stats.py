#!/usr/bin/env python3
"""
Helper script to aggregate evaluation statistics from per-file results.
Computes weighted average of correlation metrics across all files for a model.
"""
import json
import sys

def aggregate_stats(json_file):
    """
    Aggregate statistics from evaluator.py output which has per-file structure.
    Returns aggregated statistics across all files (simple average).
    """
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

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python aggregate_eval_stats.py <json_file> <stat_name>")
        sys.exit(1)
    
    json_file = sys.argv[1]
    stat_name = sys.argv[2]
    
    stats = aggregate_stats(json_file)
    
    if stats and stat_name in stats:
        value = stats[stat_name]
        if stat_name in ['percent_agreement', 'percent_close_match']:
            print(f"{round(value, 2)}%")
        else:
            print(round(value, 4))
    else:
        print("")

