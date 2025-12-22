# Advanced Test Cases

This directory contains a small set of advanced test cases designed to evaluate specific aspects of the grading system's capabilities.

## Dataset Overview

The `advanced_test.json` file contains 5 carefully designed test cases:

1. **Elementary proof with disjunction** - Tests ability to recognize elegant elementary solutions
2. **Use of overly strong machinery** - Tests ability to identify when solutions use inappropriate advanced tools for the course level
3. **Advanced cryptography (incorrect solution)** - Tests ability to identify fundamental misunderstandings in specialized topics
4. **Multi-lingual support (German)** - Tests ability to grade correct solutions in languages other than English
5. **Unconventional probability riddle** - Tests ability to identify subtle modeling errors in applied mathematics

## Running the Comparison

To run the same analysis as the main regrading comparison on these advanced test cases:

```bash
./run_advanced_test_comparison.sh
```

This script will:
- Run all configured models (gpt-4o, gpt-4.1, gpt-4.1-mini, gpt-4.1-nano, gpt-5, gpt-5-mini, gpt-5-nano, o4-mini)
- Use all configured grading prompts
- Generate outputs in `tests/advanced_test/output/`
- Compute evaluation metrics and save to `results/advanced_test_evaluations/`
- Track costs in `results/advanced_test_comparison/`

## Output Structure

```
tests/advanced_test/
├── advanced_test.json          # The test dataset
├── output/                      # Model outputs
│   ├── gpt-4o-2024-08-06/      
│   ├── gpt-4.1-2025-04-14/
│   └── ...
└── README.md                    # This file

results/
├── advanced_test_evaluations/   # Evaluation results
│   ├── gpt-4o-2024-08-06_comparison.json
│   ├── all_models_combined.json
│   └── ...
└── advanced_test_comparison/    # Cost tracking
    └── costs_*.csv
```

## Expected Behavior

These test cases are designed to challenge the grading system in specific ways:

- **High-quality solutions (rating 5)**: Should receive full marks consistently
- **Inappropriate methodology (rating 2-3)**: Tests whether graders can distinguish between "correct but inappropriate" solutions
- **Fundamental errors (rating 1-2)**: Tests whether graders can identify deep conceptual misunderstandings
- **Multi-lingual (rating 5)**: Tests language-independence of grading

## Comparison with Main Dataset

Unlike the main test dataset (`tests/test/test.json`) which contains ~50 questions covering a broad curriculum, this advanced test set:
- Is much smaller (5 questions)
- Focuses on edge cases and specific capabilities
- Tests higher-level evaluation skills
- Includes more specialized domains (cryptography)
- Includes non-English content

Use this dataset to supplement the main evaluation, not replace it.

