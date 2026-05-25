# Paper Trading Sandbox

The Meme King paper trading sandbox is simulation only.

It does not:

- connect a wallet
- read private keys
- submit transactions
- call RPC broadcast APIs
- perform swaps
- execute real buys or sells

## Purpose

The sandbox proves that a trade lifecycle can be modeled without breaking the replay and observatory system. It turns normalized historical Meme King calls into deterministic paper orders, paper fills, paper positions, and paper exits.

## Inputs

- `artifacts/normalized_calls.jsonl`
- `artifacts/channel_scorecard.json` when available

Only replayable calls with a token symbol or mint address are considered. The simulator ignores records that are not replayable or do not identify a token.

## Entry Simulation

Each accepted signal creates a deterministic entry order:

- entry reference price: `1.0`
- quantity: `1.0` paper unit
- order ID: stable hash of signal identity and side
- fill: immediate deterministic paper fill at `1.0`

There is no slippage, quote lookup, wallet balance, route lookup, or transaction.

## Exit Simulation

The simulator builds a deterministic price path from replay fields:

- `historical_max_x` if present
- `outcome_peak` parsed from `raw_text` if present
- `outcome_min` parsed from `raw_text` if present
- confidence-derived fallback when no historical outcome is available

Exit rules are checked in order:

1. stop loss
2. take profit
3. max hold

Default parameters:

- take profit: `1.5x`
- stop loss: `0.7x`
- max hold: `12` simulated steps

## Outputs

```text
artifacts/paper_trading/paper_orders.jsonl
artifacts/paper_trading/paper_positions.jsonl
artifacts/paper_trading/paper_fills.jsonl
artifacts/paper_trading/paper_exits.jsonl
artifacts/paper_trading/paper_summary.json
artifacts/paper_trading/evaluation_summary.json
artifacts/paper_trading/channel_performance.json
artifacts/paper_trading/exit_reason_stats.json
artifacts/paper_trading/strategy_comparison.json
artifacts/paper_trading/index.html
```

## Run

```bash
bash scripts/run_paper_trading.sh
```

Evaluate metrics and render the paper dashboard:

```bash
bash scripts/evaluate_paper_trading.sh
```

Run the paper-only execution gate:

```bash
bash scripts/run_execution_gate.sh
```

The gate uses the balanced profile as the default reference profile and reviews each replay candidate as `APPROVE_FOR_PAPER`, `BLOCK_FOR_RISK`, `WATCH_ONLY`, or `NEEDS_MORE_DATA`. It does not create live orders or execution outbox records.

## Strategy Profiles

Phase 2 compares deterministic paper outcomes across five profiles:

- `conservative`
- `balanced`
- `sniper`
- `graduation_watch`
- `fast_exit`

Each profile defines entry delay, stop loss, take profit, max hold, paper position size, simulated slippage, and minimum confidence. These are simulation parameters only; they do not create live orders.

## Metrics

The evaluator computes:

- winrate
- drawdown
- expectancy
- profit factor
- per-channel performance
- exit reason stats
- top simulated winners
- worst simulated losers

## Compare With Replay Data

Use:

- `artifacts/replay_summary.json` for replayable signal counts
- `artifacts/channel_scorecard.json` for channel-level historical metrics
- `artifacts/paper_trading/paper_summary.json` for simulated lifecycle outcomes

The paper summary is not a live performance claim. It is a deterministic lifecycle test against historical and normalized fields.

## Live Trading Protection

This sandbox protects future live design by forcing the lifecycle to work before any executor exists:

- order creation is deterministic
- fills are explicit artifacts
- positions have open/closed state
- exits have clear reasons
- summaries are repeatable
- no execution fields exist in the model

Any future live executor must remain isolated and prove parity with this paper lifecycle before it can be considered.
