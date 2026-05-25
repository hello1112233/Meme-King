# Live Trading Setup

## Purpose

This is **setup scaffolding only**. Real trading is **disabled by default** and remains blocked until every safety check passes.

The scaffolding exists so that when the project is ready for live micro-testing, no rebuild is required. Only configuration flags and API keys need to be added.

## What Is Disabled

| Feature | Default | Why |
|---------|---------|-----|
| Live trading | `false` | Must pass OOS + setup checks first |
| Real wallet | `false` | No private key handling until explicitly enabled |
| Transaction send | `false` | `submit_transaction()` raises RuntimeError |
| RPC broadcast | `false` | No `sendTransaction` calls |

## Configuration

Copy the example environment file:

```bash
cp config/live_trading.example.env config/live_trading.env
```

Edit `config/live_trading.env` with real values. **Never commit the real file.**

Key variables:

- `ENABLE_LIVE_TRADING=false`
- `ENABLE_REAL_WALLET=false`
- `ENABLE_TRANSACTION_SEND=false`
- `WALLET_KEYPAIR_PATH=` (path to a JSON keypair file, NOT the raw key)
- `MAX_POSITION_SOL=0.01`
- `MAX_DAILY_LOSS_SOL=0.05`
- `MAX_OPEN_POSITIONS=1`

## Risk Limits

The validator enforces strict caps:

- `MAX_POSITION_SOL` must be ≤ 1.0 SOL
- `MAX_DAILY_LOSS_SOL` must be ≤ 1.0 SOL
- `DEFAULT_SLIPPAGE_BPS` must be ≤ 5000
- `MAX_SLIPPAGE_BPS` must be ≤ 5000

If any limit is exceeded, `validate_live_trading_config()` returns an error and the kill switch blocks trading.

## Kill Switch

`meme_king.kill_switch.KillSwitch` tracks why trading is halted.

Default reasons that block real trading:

- `live_trading_disabled`
- `transaction_send_disabled`
- `missing_wallet`
- `config_invalid`
- `oos_failed`

To clear a reason, call `kill_switch.release("reason_name")`. Trading only resumes when `kill_switch.can_trade()` returns `True`.

## Dry-Run Executor

`meme_king.dry_run_executor.DryRunExecutor` implements `LiveExecutorInterface` without sending transactions.

It produces:

- `artifacts/live_trading_setup/dry_run_quotes.jsonl`
- `artifacts/live_trading_setup/dry_run_transaction_plans.jsonl`
- `artifacts/live_trading_setup/dry_run_results.jsonl`
- `artifacts/live_trading_setup/dry_run_summary.json`

Run the dry-run executor:

```bash
bash scripts/check_live_trading_setup.sh
```

## Setup Readiness Check

`tools/run_live_trading_setup_check.py` evaluates:

1. Live trading config validity
2. Hermes skill OOS validation status
3. Execution gate health
4. Kill switch state
5. Missing API keys

Output status is one of:

- `BLOCK_REAL_TRADING` — real execution is impossible
- `READY_FOR_DRY_RUN_ONLY` — dry-run works, but live is still blocked
- `READY_FOR_LIVE_PAPER` — all checks pass (still paper-only until `ENABLE_TRANSACTION_SEND=true`)

## Mac Mini Install Notes

No additional heavy dependencies are required for the scaffolding. The dry-run executor uses only Python stdlib.

When you later wire real execution (Jupiter, Helius, PumpPortal), install their SDKs in the virtual environment:

```bash
source .venv/bin/activate
pip install httpx websockets  # lightweight async HTTP/WebSocket
```

## Gate to Real Trading

Before enabling real trading, ALL of the following must be true:

1. OOS validation passes (`oos_validation.json` says `oos_pass: true`)
2. `ENABLE_LIVE_TRADING=true`
3. `ENABLE_REAL_WALLET=true`
4. `ENABLE_TRANSACTION_SEND=true`
5. `WALLET_KEYPAIR_PATH` points to an existing keypair file
6. `validate_live_trading_config()` returns an empty error list
7. Kill switch `can_trade()` returns `True`
8. Dry-run executor runs successfully with no anomalies

Only then should you implement `LiveExecutorInterface._submit_live()` in a real executor subclass.
