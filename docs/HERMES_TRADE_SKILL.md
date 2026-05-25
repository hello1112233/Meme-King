# Hermes Trade Skill

The Hermes Trade Skill is the compact Meme King decision brain for entry and exit understanding. It is trained from the four selected channels and existing Meme King historical, paper-trading, and execution-gate artifacts.

It is not live execution.

It does not:

- connect wallets
- read private keys
- call RPC broadcast APIs
- submit `sendTransaction`
- perform swaps
- execute real buys or sells

## Purpose

The skill learns a simple rule set that only approves setups matching observed historical paper edge. The target is 80%+ paper win rate with at least 25 accepted setups when possible. The target is not guaranteed. If 80% cannot be reached with enough trades, the trainer reports the best honest deterministic result.

## Decisions

Entry:

- `ENTER_PAPER`
- `SKIP`

Exit:

- `EXIT_TAKE_PROFIT`
- `EXIT_STOP_LOSS`
- `EXIT_TIMEOUT`
- `HOLD`

## Inputs

The skill considers:

- channel name
- token symbol or mint
- confidence
- channel historical score
- paper strategy result
- duplicate/cooldown status
- signal age
- text risk keywords
- historical channel performance

## Training

```bash
bash scripts/train_hermes_trade_skill.sh
```

Outputs:

```text
artifacts/hermes_trade_skill/skill_rules.json
artifacts/hermes_trade_skill/training_summary.json
artifacts/hermes_trade_skill/accepted_setups.jsonl
artifacts/hermes_trade_skill/rejected_setups.jsonl
artifacts/hermes_trade_skill/backtest_summary.json
artifacts/hermes_trade_skill/channel_breakdown.json
artifacts/hermes_trade_skill/exit_breakdown.json
```

## Future Executor Protection

This layer is intentionally compact and deterministic. A future isolated executor should not receive any candidate that the skill cannot explain, and this phase still creates no live execution outbox.

