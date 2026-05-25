# Project State — Meme King

## What is Meme King?

A deterministic, read-only intelligence observatory for historical Telegram/Twitter signal data. It replays local historical files, extracts allowlisted channel records, runs paper simulations, and trains compact trading rules.

## Current Status

- **Tests:** 83 passed
- **Live paper runtime:** ready (stub ingestors, needs real sources wired)
- **Real trading:** BLOCKED
- **OOS validation:** FAIL (day coverage = 1, needs ≥ 7)
- **Kill switch:** HALTED
- **Dry-run executor:** operational (250 quotes planned)

## Architecture

```
Ingestors → Normalizer → Execution Gate → Hermes Trade Skill → Paper Executor
                                      → Live Paper Runtime  → Dry-Run Executor
```

- **No wallet integration**
- **No private key handling**
- **No RPC sendTransaction**
- **No swap execution**

## Key Artifacts

| Artifact | Status |
|----------|--------|
| `artifacts/hermes_trade_skill/skill_rules.json` | trained |
| `artifacts/hermes_trade_skill/oos_validation.json` | FAIL |
| `artifacts/live_paper/live_daily_summary.json` | mock data only |
| `artifacts/live_trading_setup/setup_readiness.json` | BLOCK_REAL_TRADING |
| `artifacts/execution_gate/gate_summary.json` | operational |

## Immediate Blockers

1. Day coverage < 7 (need continuous live paper collection)
2. ENABLE_LIVE_TRADING = false
3. ENABLE_TRANSACTION_SEND = false
4. Missing API keys (Helius, Jupiter, Telegram, PumpPortal)

## When Will OOS Pass?

After running `scripts/run_live_paper_runtime.sh` continuously for 7–14 days with real ingestors.
