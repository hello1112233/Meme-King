# Safety Rules

## Live Trading Gates

Real trading requires ALL of the following:

1. `ENABLE_LIVE_TRADING=true` in `config/live_trading.env`
2. `ENABLE_REAL_WALLET=true`
3. `ENABLE_TRANSACTION_SEND=true`
4. `WALLET_KEYPAIR_PATH` points to an existing JSON keypair file
5. `validate_live_trading_config()` returns empty error list
6. Kill switch `can_trade()` returns `True`
7. OOS validation passes (`oos_validation.json` says `oos_pass: true`)
8. Dry-run executor runs cleanly for 7+ consecutive days

## Kill Switch Reasons That Block Trading

- `live_trading_disabled`
- `transaction_send_disabled`
- `missing_wallet`
- `config_invalid`
- `oos_failed`
- `daily_loss_limit`
- `max_open_positions`
- `missing_source`
- `source_degraded`
- `manual_halt`

## Risk Limits (Hard Caps)

| Limit | Default | Max Allowed |
|-------|---------|-------------|
| MAX_POSITION_SOL | 0.01 | 1.0 |
| MAX_DAILY_LOSS_SOL | 0.05 | 1.0 |
| DEFAULT_SLIPPAGE_BPS | 1500 | 5000 |
| MAX_SLIPPAGE_BPS | 3000 | 5000 |
| MAX_OPEN_POSITIONS | 1 | — |

## Secret Handling

- NEVER commit `config/live_trading.env`
- NEVER commit wallet keypair files
- NEVER commit Telegram session files
- NEVER print private keys in logs
- `.gitignore` blocks all of the above

## Pre-Commit Safety Check

Run:
```bash
bash scripts/pre_commit_safety_check.sh
```

This blocks commits if secrets or unsafe flags are detected.
