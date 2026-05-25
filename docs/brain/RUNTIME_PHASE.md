# Runtime Phase

## Current Phase: Live Paper Collection Only

Meme King is in **live paper collection mode**. No real trading. No transaction sending.

## Why This Phase?

The Hermes trade skill shows 100% historical winrate, but OOS validation fails because the dataset spans only **1 calendar day**. A 100% winrate on 1 day is statistically meaningless.

## Goal

Collect live signals continuously for **7–14 days** to achieve:
- `day_coverage >= 7` (OOS threshold)
- Temporal diversity across multiple market regimes
- Honest validation of skill edge

## What To Do Now

1. Wire real ingestors (Telegram, Helius, Jupiter, PumpPortal, DexScreener, GMGN)
2. Run `bash scripts/run_live_paper_runtime.sh` continuously
3. Monitor `artifacts/live_paper/live_daily_summary.json`
4. Re-run OOS validation after day 7

## What NOT To Do Now

- Do not enable `ENABLE_LIVE_TRADING`
- Do not enable `ENABLE_TRANSACTION_SEND`
- Do not add leverage, margin, or multi-chain support
- Do not add LLM inference to the hot path
- Do not scale position sizes
- Do not overbuild infrastructure

## Success Criteria

OOS validation shows:
- `oos_pass: true`
- `day_coverage >= 7`
- All other thresholds still pass

Only then does the project advance to dry-run expansion and eventual micro live testing.
