# Next Steps

## Priority 1: Live Paper Collection (7–14 days)

Wire real ingestors in `tools/run_live_paper_runtime.py`:

1. **Telegram** — Telethon/MTProto for signal channels
2. **Helius RPC** — Solana node access
3. **Jupiter API** — swap routing (for future quote building)
4. **PumpPortal WebSocket** — launch events
5. **Pump.fun API** — graduation events
6. **DexScreener** — token snapshots
7. **GMGN API** — smart money signals

Keep `ENABLE_LIVE_TRADING=false` during this phase.

## Priority 2: OOS Re-validation

After day coverage ≥ 7:

```bash
python3 tools/validate_hermes_trade_skill_oos.py
```

Target: all thresholds pass.

## Priority 3: Dry-Run Expansion

Run `bash scripts/check_live_trading_setup.sh` daily.
Monitor dry-run quote plans for anomalies.

## Priority 4: Micro Live Testing (FUTURE)

Only after:
- OOS passes
- Kill switch `can_trade()` returns `True`
- `ENABLE_LIVE_TRADING=true`
- `ENABLE_REAL_WALLET=true`
- `ENABLE_TRANSACTION_SEND=true`
- Wallet keypair path exists
- Risk limits validated
- Dry-run runs cleanly for 7+ days

Start with $5–$10 positions. Max 1 open position.

## What NOT To Do Next

- Do not add more strategy profiles before OOS passes.
- Do not add leverage or margin.
- Do not add multi-chain support yet.
- Do not add LLM-based signal parsing yet.
