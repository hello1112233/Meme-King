# Meme King

Meme King is a deterministic read-only intelligence observatory for historical Telegram/Twitter signal data already saved locally from the old Meme Queen/OpenClaw project.

It is intentionally not a trading system. It contains no wallet integration, private key handling, swap logic, RPC `sendTransaction`, buy/sell execution, or autonomous execution path. It only discovers local historical files, extracts allowlisted channel records, replays them deterministically, and renders portable artifacts.

## Allowed Channels

Only these channels are accepted:

- WhaleSignal Meme Coin
- WaveX Call - Multichain `[T:25176]`
- Twitter `@pumpdotfun` alpha
- GMGN Featured Signals(Lv1) - SOL `[T:3847543]`

All other channels are rejected by `meme_king.channel_registry.ChannelRegistry`.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
```

Alternatively:

```bash
python3 -m pip install -e .
python3 -m pip install -r requirements-dev.txt
```

## Run

```bash
bash scripts/run_meme_king.sh
```

The dashboard is written to `artifacts/index.html`.

## Paper Trading

```bash
bash scripts/run_paper_trading.sh
```

This is simulation only. It creates deterministic paper orders, paper fills, paper positions, and paper exits from replay data. It does not connect wallets, read private keys, submit transactions, call RPC broadcast APIs, perform swaps, or execute real buys/sells.

Evaluate paper trading performance and strategy profiles:

```bash
bash scripts/evaluate_paper_trading.sh
```

The paper dashboard is written to `artifacts/paper_trading/index.html`.

Run the paper-only execution gate:

```bash
bash scripts/run_execution_gate.sh
```

The gate reviews replay signals as `APPROVE_FOR_PAPER`, `BLOCK_FOR_RISK`, `WATCH_ONLY`, or `NEEDS_MORE_DATA`. It is simulation only and does not execute trades.

Train the compact Hermes trade skill:

```bash
bash scripts/train_hermes_trade_skill.sh
```

The skill searches simple entry/exit rules against paper history, targeting 80%+ paper win rate when honestly reachable. It is still paper validation only.

Validate the skill against out-of-sample anti-overfit checks:

```bash
bash scripts/validate_hermes_trade_skill_oos.sh
```

The OOS validator runs time-split, channel-holdout, duplicate-token-collapse, and shuffled-replay tests. It does not execute trades.

Run the live paper ingestion runtime to collect signals continuously:

```bash
bash scripts/run_live_paper_runtime.sh
```

This is a lightweight ingestion + paper replay loop. It collects live signals for 7–14 days to build temporal diversity for OOS validation. It does not execute real trades.

Check live trading setup readiness (scaffolding only; real trading disabled):

```bash
bash scripts/check_live_trading_setup.sh
```

This validates configuration, risk limits, kill switch, and runs the dry-run executor. Real transactions are never sent.

## Validate

```bash
bash scripts/validate_meme_king.sh
```

Validation runs Python bytecode compilation, pytest, the full artifact pipeline, and the paper trading replay.

## Open Dashboard

Open this local file in a browser:

```text
artifacts/index.html
```

## Artifacts

- `artifacts/discovered_sources.json`
- `data/source_exports/*.jsonl`
- `artifacts/normalized_calls.jsonl`
- `artifacts/replay_summary.json`
- `artifacts/channel_rankings.json`
- `artifacts/channel_statistics.json`
- `artifacts/channel_scorecard.json`
- `artifacts/paper_trading/paper_summary.json`
- `artifacts/paper_trading/evaluation_summary.json`
- `artifacts/paper_trading/strategy_comparison.json`
- `artifacts/paper_trading/index.html`
- `artifacts/execution_gate/gate_summary.json`
- `artifacts/execution_gate/index.html`
- `artifacts/hermes_trade_skill/skill_rules.json`
- `artifacts/hermes_trade_skill/backtest_summary.json`
- `artifacts/hermes_trade_skill/oos_validation.json`
- `artifacts/live_paper/live_signals.jsonl`
- `artifacts/live_paper/live_gate_decisions.jsonl`
- `artifacts/live_paper/live_paper_positions.jsonl`
- `artifacts/live_paper/live_daily_summary.json`
- `artifacts/live_trading_setup/setup_readiness.json`
- `artifacts/live_trading_setup/dry_run_summary.json`
- `artifacts/index.html`

## Safety Boundaries

Meme King is research/replay only. The codebase uses local files and SQLite read-only connections. It does not import trading SDKs, hold private keys, or call network RPC endpoints.

SQLite artifacts from the old project are opened with `mode=ro&immutable=1`. If `shadow_trading.db` is discovered, it is treated only as a historical read-only artifact; Meme King does not use any trading or execution behavior from it.
