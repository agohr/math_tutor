# Model Costs Configuration

This document describes the model pricing configuration for the math tutor system.

## Configuration File

Model costs are stored in `model_costs.json`. Each model has two values:
- Input token cost (per token)
- Output token cost (per token)

## Current Pricing (as of 2026-02-01)

All prices below are verified against [OpenAI's official pricing page](https://platform.openai.com/docs/pricing) (Standard tier).

| Model | Input (per 1M tokens) | Output (per 1M tokens) | Status |
|-------|----------------------|------------------------|---------|
| gpt-4o | $2.50 | $10.00 | ✓ Verified |
| gpt-4o-2024-08-06 | $2.50 | $10.00 | ✓ Verified |
| gpt-4o-mini | $0.15 | $0.60 | ✓ Verified |
| gpt-3.5-turbo | $0.50 | $1.50 | ✓ Verified |
| gpt-4.1-nano-2025-04-14 | $0.10 | $0.40 | ✓ Verified |
| gpt-4.1-nano | $0.10 | $0.40 | ✓ Verified (alias) |
| gpt-4.1-2025-04-14 | $2.00 | $8.00 | ✓ Verified |
| gpt-4.1 | $2.00 | $8.00 | ✓ Verified (alias) |
| gpt-4.1-mini-2025-04-14 | $0.40 | $1.60 | ✓ Verified |
| gpt-4.1-mini | $0.40 | $1.60 | ✓ Verified (alias) |
| gpt-5 | $1.25 | $10.00 | ✓ Verified |
| gpt-5.2 | $1.75 | $14.00 | ✓ Verified |
| gpt-5-mini | $0.25 | $2.00 | ✓ Verified |
| gpt-5-nano | $0.05 | $0.40 | ✓ Verified |
| o4-mini | $1.10 | $4.40 | ✓ Verified |

## Updating Costs

When OpenAI updates their pricing:

1. Visit [OpenAI's pricing page](https://platform.openai.com/docs/pricing)
2. Update `model_costs.json` with new values
3. Update this README with verification date and status
4. The system will automatically use the new costs on next run

## Implementation

The `token_usage.py` module loads costs from `model_costs.json` at startup. No code changes are needed when prices change - just update the JSON file.

### Important Notes

- All costs are per-token (not per million tokens)
- Reasoning tokens are billed at the output token rate
- The "unknown" model entry is used as a fallback (cost: $0.00)
