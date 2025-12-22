# Cost Tracking Documentation

## Overview

Cost tracking is an **optional feature** in the evaluation scripts. It estimates API costs based on published pricing rates at the time this research artifact was created. We used the pricing feature for experiment planning; we expect they may be useful for other researchers building on our codebase as well. However, future users will have to modify the cost data in token_usage.py to reflect current pricing.

## Important Notes

⚠️ **These costs are estimates only**
- Costs are based on API pricing at time of publication
- Actual costs may vary as providers update their pricing
- This feature is provided for reproducibility purposes only
- Cost tracking requires explicit opt-in and confirmation

## Usage

### Enabling Cost Tracking

To enable cost tracking, use the `--track-costs` flag:

```bash
# For advanced test comparison
./run_advanced_test_comparison.sh --track-costs

# For regrading comparison
./run_regrading_comparison.sh --track-costs
```

### Confirmation Prompt

When you enable cost tracking, you will see a confirmation prompt:

```
=========================================================================
COST TRACKING ENABLED
=========================================================================
This will track and display API costs based on published pricing rates
as of the time this research artifact was created.

NOTE: These costs are estimates based on pricing at time of publication
and may not reflect current API pricing. This is a research artifact and
cost tracking is provided for reproducibility purposes only.

Do you want to proceed with cost tracking? (y/N):
=========================================================================
```

You must explicitly confirm by typing `y` to proceed with cost tracking.

### Running Without Cost Tracking (Default)

Simply run the scripts without the flag:

```bash
# No cost tracking (default behavior)
./run_advanced_test_comparison.sh
./run_regrading_comparison.sh
```

## What Gets Tracked

When cost tracking is enabled, the scripts will:

1. **Clear usage tracking** before each model/config run
2. **Extract costs** after each run using `extract_cost.py`
3. **Display cost summary** showing per-model and per-config costs
4. **Save cost data** to timestamped CSV files:
   - `results/advanced_test_comparison/costs_YYYY-MM-DD_HH-MM-SS.csv`
   - `results/regrading_comparison/costs_YYYY-MM-DD_HH-MM-SS.csv`

## Cost Calculation

Costs are calculated based on token usage:

```
cost = (input_tokens × input_rate) + ((output_tokens + reasoning_tokens) × output_rate)
```

### Reasoning Tokens

For reasoning models (GPT-5, o4-mini, etc.), the system now properly accounts for:
- **Input tokens**: Standard prompt tokens
- **Output tokens**: Generated response tokens
- **Reasoning tokens**: Internal reasoning tokens (billed at output rate)

## Pricing Rates (As of Publication)

The following rates are hardcoded in `token_usage.py`:

| Model | Input (per million tokens) | Output (per million tokens) |
|-------|---------------------------|----------------------------|
| gpt-4o-2024-08-06 | $2.50 | $10.00 |
| gpt-4.1-2025-04-14 | $2.00 | $8.00 |
| gpt-4.1-mini-2025-04-14 | $0.50 | $1.50 |
| gpt-4.1-nano | $0.10 | $0.40 |
| gpt-5 | $1.25 | $10.00 |
| gpt-5-mini | $0.25 | $2.00 |
| gpt-5-nano | $0.05 | $0.40 |
| o4-mini | $1.10 | $4.40 |

## Output Format

### Console Output

When enabled, you'll see cost information during execution:

```
✓ Completed: baseline with gpt-5 (Cost: $0.123456)
```

And a summary table at the end:

```
Cost Summary by Model/Config Combination:
========================================
Config                     | Model                      | Cost (USD)
---------------------------|----------------------------|------------
baseline                   | gpt-5                      | $0.123456
baseline_concise           | gpt-5-mini                 | $0.045678
...
---------------------------|----------------------------|------------
TOTAL                      |                            | $1.234567
```

### CSV Output

The saved CSV files have this format:

```csv
config_name,model_name,cost
baseline,gpt-5,0.123456
baseline_concise,gpt-5-mini,0.045678
```

## Help

To see available options:

```bash
./run_advanced_test_comparison.sh --help
./run_regrading_comparison.sh --help
```

## Technical Implementation

The cost tracking system consists of:

1. **`token_usage.py`**: Tracks token usage and calculates costs
2. **`extract_cost.py`**: Extracts accumulated costs from usage logs
3. **Shell scripts**: Orchestrate cost tracking across multiple runs

For implementation details, see the source files.

