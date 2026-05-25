# Meme King Runtime Architecture

This document proposes a new isolated Meme King runtime architecture optimized for an M1 Mac Mini with 8 GB RAM. It is architecture-only: no live trading implementation, no wallet integration, no private key handling, and no transaction submission are added in this phase.

## Design Goals

- Low latency for source ingestion and candidate routing.
- Non-breaking execution path: executor faults must not crash ingestion or replay cognition.
- Isolated executor boundary for any future live actions.
- Replay-safe cognition with deterministic inputs and reproducible artifacts.
- Lightweight ingestion that can run continuously on 8 GB RAM.
- Deterministic append-only logs for debugging, replay, and audit.
- Portable deployment with minimal services and local-first storage.

## OpenClaw Findings

The old OpenClaw/Meme Queen runtime is a large asyncio Python process started from `main.py`. Its own notes describe 17-20 concurrent tasks: PumpPortal/PumpDev websocket ingestion, Telegram listener, orchestrator, position manager, shadow collector, agent trainer, notifier, Hermes bridge, Hermes poller, retrospective, shadow trader, hourly analyst, self trainer, strategy lab, strategy discovery, health monitor, wallet miner, and optional slash/scraper/Twitter tasks.

Key old modules:

- `fast_bot/listener.py`: Telegram message parsing, classification, routing, gating, and direct dispatch.
- `feeds/pumpportal.py`: Dual PumpPortal/PumpDev websocket client.
- `fast_bot/executor.py`: Jupiter and PumpPortal execution adapter in the old system.
- `agents/mc_tracker.py`: market-cap/liquidity enrichment from PumpPortal cache, Jupiter, DexScreener, GMGN, GeckoTerminal, DexPaprika, and Helius fallback.
- `agents/token_quality.py`: in-memory PumpPortal behavioral scoring.
- `agents/helius_validator.py`: holder concentration validation through Helius JSON-RPC.
- `agents/shadow_trader.py`: shadow lifecycle and simulated outcomes.
- `tools/hermes_filter.py`: research/scoring layer, pair gates, ML/router gates, and shadow entry.
- `data/openclaw.db`, `data/shadow_trading.db`, `data/hermes_research.db`, `data/quantbot.duckdb`: primary old persistence layers.

The old system mixed ingestion, cognition, shadow execution, live execution, model routing, scheduled training, and health monitoring in one Python runtime. Meme King should not inherit that coupling.

## Proposed Runtime Shape

```text
                    local config + allowlists
                              |
                              v
┌───────────────────────────────────────────────────────────────┐
│                  meme-king-ingest (Python)                     │
│  Telegram | PumpPortal/PumpDev | GMGN | DexScreener | Twitter  │
│  bounded async connectors, backpressure, source health          │
└───────────────┬───────────────────────────────────────────────┘
                v
┌───────────────────────────────────────────────────────────────┐
│                  append-only event log                         │
│  SQLite WAL, deterministic IDs, raw payload, provenance, hash   │
└───────────────┬───────────────────────────────────────────────┘
                v
┌───────────────────────────────────────────────────────────────┐
│                  replay-safe cognition                         │
│  projection rebuilds, scorecards, channel state, feature views  │
│  reads event log only; writes derived artifacts only            │
└───────────────┬───────────────────────────────────────────────┘
                v
┌───────────────────────────────────────────────────────────────┐
│                  decision outbox                               │
│  immutable candidate intents, safety gates, dry-run default     │
│  no private keys; no network send                               │
└───────────────┬───────────────────────────────────────────────┘
                v
┌───────────────────────────────────────────────────────────────┐
│           future isolated executor (Rust sidecar)              │
│  separate process, explicit enable flag, bounded queue          │
│  idempotency keys, preflight, confirmation watchdog             │
└───────────────────────────────────────────────────────────────┘
```

## Process Model

For an M1 Mac Mini 8 GB, keep the always-on set small:

| Process | Language | Default | Memory Target | Role |
| --- | --- | --- | ---: | --- |
| `meme-king-ingest` | Python asyncio | enabled | 150-250 MB | Source connectors and append-only event persistence |
| `meme-king-cognition` | Python CLI/cron | scheduled | 300-700 MB | Projection rebuilds, scorecards, dashboard artifacts |
| `meme-king-api` | optional Python/FastAPI or stdlib HTTP | disabled | 80-150 MB | Local dashboard/status API |
| `meme-king-executor` | future Rust sidecar | disabled | 20-80 MB | Isolated transaction state machine if live mode is approved later |

Do not run old OpenClaw's full task set on the 8 GB machine. Disable nightly ML suites, heavyweight LLM cascades, Chroma, NetworkX graph rebuilds, dashboards with pandas/Streamlit, and broad scraping in the runtime process.

## Storage Layout

```text
data/runtime/events.sqlite         append-only raw event log
data/runtime/runtime_state.sqlite  source health, cursors, outbox state
data/runtime/features.duckdb       analytical snapshots and batch feature tables
data/runtime/vector/               optional TurboVec files or SQLite vector extension data
artifacts/runtime_architecture/    generated plans and inventory
artifacts/replay/                  deterministic replay outputs
logs/runtime/*.jsonl               structured JSONL logs
```

SQLite remains the source of truth for event ingestion. DuckDB is a derived analytical cache and can be rebuilt. TurboVec, if used, is a derived approximate search index and can be rebuilt from SQLite/DuckDB rows.

## Latency Budget

Target candidate path on local machine:

| Stage | Target |
| --- | ---: |
| Source receive to append log | < 20 ms local work, excluding network |
| Telegram parse and allowlist normalize | < 5 ms |
| PumpPortal trade event ingest | < 3 ms |
| in-memory quality lookup | < 1 ms |
| DexScreener/GMGN enrichment | async, budgeted 200-600 ms, never blocks ingestion |
| Helius/RPC validation | async, budgeted 500-1500 ms, bounded by queue |
| decision outbox write | < 10 ms |
| future executor dequeue to signed submit | separate SLO, executor-only |

Network calls must be outside the ingestion critical section. Ingest writes a canonical event first; enrichment workers append follow-up events.

## Replay Safety

Replay-safe cognition means:

- All live source records are persisted before interpretation.
- Deterministic event IDs include source, source event ID or timestamp bucket, token address, channel identity, and payload hash.
- Projectors rebuild from event log into derived tables.
- Cognition writes explanations, scorecards, and candidate intents, not side effects.
- Replay cannot call executor APIs.
- Any future executor reads only explicit outbox rows with `execution_enabled=true`, manual approval state, and idempotency keys.

## Deterministic Logging

Every process writes JSONL:

```json
{
  "ts": "2026-05-25T00:00:00Z",
  "seq": 123,
  "process": "meme-king-ingest",
  "event": "source_event_persisted",
  "source": "telegram",
  "event_id": "sha256:...",
  "token": "...",
  "decision": null,
  "hash": "sha256:..."
}
```

Rules:

- Monotonic per-process sequence.
- Stable event IDs and payload hashes.
- No private keys or signed transactions in logs.
- Source payloads stored in SQLite; logs include references and hashes.
- Log rotation by size, not time, to avoid clock-dependent replay drift.

## Failure Model

- Source connector failure: mark degraded, retry with exponential backoff and jitter, continue other sources.
- SQLite write failure: stop ingestion process, do not proceed with in-memory-only state.
- Cognition failure: leave prior artifacts untouched; write failure artifact.
- Executor failure: future sidecar owns retries and confirmation state; ingestion/cognition continue.
- RPC outage: source/replay continue; executor queue remains pending or cancelled by TTL.

## Deployment

Single-host deployment on M1:

```text
launchd or tmux
  ├─ .venv/bin/python -m meme_king_runtime.ingest
  ├─ periodic: .venv/bin/python tools/replay_top4_channels.py
  └─ optional: ./target/release/meme-king-executor --disabled
```

Keep default deployment in observatory mode. The executor sidecar is disabled unless explicitly enabled in a future implementation phase.

