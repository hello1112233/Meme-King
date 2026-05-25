# Execution Gate

The Meme King execution gate is simulation and paper-only. It does not add live execution, wallet integration, private key handling, RPC broadcast, `sendTransaction`, swaps, or real buys/sells.

## Purpose

The gate reviews every replay candidate and emits one deterministic decision:

- `APPROVE_FOR_PAPER`
- `BLOCK_FOR_RISK`
- `WATCH_ONLY`
- `NEEDS_MORE_DATA`

The balanced strategy profile is the default reference profile because Phase 2 paper evaluation ranked it first.

## Inputs

- `artifacts/normalized_calls.jsonl`
- `artifacts/channel_scorecard.json`
- `artifacts/paper_trading/strategy_comparison.json`

## Guardrails

The gate checks:

- channel allowlist
- confidence threshold
- minimum replay support
- liquidity placeholder availability
- token recurrence
- duplicate signal identity
- cooldown window
- suspicious rug/scam text
- max open paper positions
- balanced profile compatibility

## Decision Behavior

`APPROVE_FOR_PAPER` means a signal is eligible for paper simulation only.

`BLOCK_FOR_RISK` means a deterministic risk guardrail fired, such as duplicate signal, cooldown, suspicious text, unsupported channel, recurrence pressure, position pressure, or profile incompatibility.

`WATCH_ONLY` means the signal is not safe enough for paper approval, usually because confidence is below the balanced profile threshold or liquidity is unverified when that check is required.

`NEEDS_MORE_DATA` means the signal lacks required historical context, such as confidence or replay support.

## Future Executor Protection

This gate protects future live design by requiring deterministic review artifacts before any isolated executor can exist. A future executor should only ever see explicitly approved outbox records, and this phase does not create such live outbox records.

## Run

```bash
bash scripts/run_execution_gate.sh
```

Outputs:

```text
artifacts/execution_gate/gate_decisions.jsonl
artifacts/execution_gate/gate_summary.json
artifacts/execution_gate/blocked_signals.jsonl
artifacts/execution_gate/approved_paper_signals.jsonl
artifacts/execution_gate/index.html
```

