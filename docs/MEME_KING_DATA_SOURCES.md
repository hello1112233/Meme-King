# Meme King Data Sources

This inventory is based on the existing OpenClaw repository and generated Meme King discovery artifacts. It describes source roles and proposed handling for a new isolated runtime. It does not enable live connections.

## Source Classes

| Class | Purpose | Runtime Criticality |
| --- | --- | --- |
| Behavioral truth | wallet/token events that describe actual market behavior | high |
| Narrative context | Telegram/Twitter/social callouts and claims | high |
| Market enrichment | price, market cap, liquidity, route availability | medium |
| Chain validation | holder concentration, account state, blockhash/confirmation | medium |
| Research/model | offline scoring, channel intelligence, reflection | low for live path |

## Inventory

| Source | Found In OpenClaw | Old Role | Meme King Proposed Role | Notes |
| --- | --- | --- | --- | --- |
| Telegram | `fast_bot/listener.py`, docs | Channel signal ingestion, classification, convergence | Lightweight narrative connector | Restrict channels by allowlist; persist raw message before scoring |
| PumpPortal | `feeds/pumpportal.py`, `fast_bot/executor.py`, `agents/token_quality.py` | Token creation/trade stream, fallback execution in old executor | Behavioral event stream only in architecture phase | No execution use in Meme King until separate approval |
| PumpDev | `feeds/pumpportal.py`, config `PUMPDEV_API_KEY` | PumpPortal-compatible websocket source | Secondary PumpPortal-compatible behavioral stream | Health tracked separately |
| Pump.fun | `agents/bonding_curve.py`, `main.py`, scraper | Bonding curve, launch/graduation context, trending | Curve/graduation state source | Treat as state/enrichment, not action path |
| GMGN | `agents/wallet_tracker.py`, `agents/mc_tracker.py`, exports | Smart wallet discovery, token endpoint, channel families | Wallet/token intelligence source | Authenticated CLI/API use should be optional and bounded |
| DexScreener | `agents/mc_tracker.py`, `agents/alert_retrospective.py`, `twitter_scanner.py`, scraper | Market cap, liquidity, boosted/trending, retrospective | Market enrichment and liquidity snapshot | Rate-limited; async queue only |
| Helius | `agents/helius_validator.py`, config | Holder concentration and RPC fallback | Chain validation source | Credit budget and cooldown required |
| Solana RPC | `fast_bot/executor.py`, `agents/bonding_curve.py`, `agents/mc_tracker.py` | Account data, blockhash, submission in old executor | Read-only chain state in this phase | Future executor owns all send paths |
| Jupiter | `fast_bot/executor.py`, `agents/mc_tracker.py`, position manager | Quotes, swaps, price polling | Quote/route enrichment only in architecture phase | No swap execution in Meme King docs phase |
| Jito | `fast_bot/executor.py`, settings | Old parallel submission path | Future executor endpoint candidate | Executor-only, disabled by default |
| Helius Sender | `fast_bot/executor.py`, settings | Old staked sender path | Future executor endpoint candidate | Executor-only, disabled by default |
| Twitter/X/xAI | `agents/twitter_scanner.py`, settings | Social sentiment scanner from DexScreener trending + model scoring | Optional narrative enrichment | Keep outside critical path; default disabled |
| RugCheck | `main.py`, `tools/hermes_filter.py` references | Rug risk gate | Optional enrichment gate | Use only as async risk annotation unless benchmarked |
| GeckoTerminal | `agents/mc_tracker.py` | DexScreener fallback | Market enrichment fallback | Useful under 429s |
| DexPaprika | `agents/mc_tracker.py` | GeckoTerminal fallback | Market enrichment fallback | Low priority |
| Chroma | `memory/memory_engine.py`, `data/chroma` | Vector similarity memory | Avoid always-on runtime use on 8 GB | Replace with optional lightweight vector layer |
| NetworkX knowledge graph | `memory/memory_engine.py`, docs | Large nightly graph | Offline only | Too memory-heavy for always-on M1 runtime |
| DuckDB snapshot | `tools/migrate_to_duckdb.py`, docs | Analytics snapshot | Derived analytical cache | Rebuildable, not source of truth |
| SQLite DBs | `data/*.db` | primary persistence and shadow evidence | event log and state store | Use WAL, immutable reads for old artifacts |

## Old Source Priority In `mc_tracker.py`

OpenClaw market cap logic used:

1. PumpPortal in-memory cache.
2. Jupiter price endpoint.
3. DexScreener REST.
4. GMGN token endpoint.
5. GeckoTerminal fallback.
6. DexPaprika fallback.
7. Helius RPC fallback.

Meme King should split this into:

- immediate local cache reads
- async enrichment queue
- replay projection updates
- no network call inside the append-only ingest transaction

## Data Source Contracts

Every source adapter should emit:

```json
{
  "source": "telegram",
  "source_kind": "narrative_context",
  "source_event_id": "...",
  "observed_at": "2026-05-25T00:00:00Z",
  "token_mint": null,
  "channel_name": null,
  "payload": {},
  "payload_hash": "sha256:...",
  "connector_version": "..."
}
```

Forbidden fields at the source boundary:

- `should_buy`
- `should_sell`
- `recommended_action`
- `private_key`
- `signed_transaction`
- `send_transaction`

## Ingestion Priorities On M1 8 GB

Always-on:

- Telegram allowlisted channels.
- PumpPortal/PumpDev behavioral events.
- SQLite event log.
- compact source health tracker.

Bounded async:

- DexScreener liquidity snapshots.
- GMGN token/wallet enrichment.
- Helius holder validation.
- Solana RPC read-only curve/account checks.

Scheduled/offline:

- DuckDB analytical rebuild.
- vector index rebuild.
- channel scorecard generation.
- dashboard rendering.
- historical backfills.

Disabled by default:

- broad Twitter/X model scanning.
- Chroma/NetworkX always-on graph.
- live executor.
- heavyweight multi-provider LLM cascades.

## Source Health Model

Track per source:

- enabled
- status: `starting`, `healthy`, `degraded`, `failed`, `disabled`
- last event timestamp
- last successful request
- event lag
- error rate
- rate-limit state
- reconnect attempts
- queue depth
- last deterministic event ID

## Replay Inventory Artifacts

The current Meme King run discovered OpenClaw source artifacts and normalized historical records from allowlisted channels. These are replay artifacts, not live source connectors.

Primary generated files:

- `artifacts/discovered_sources.json`
- `artifacts/export_manifest.json`
- `artifacts/normalized_calls.jsonl`
- `artifacts/replay_summary.json`
- `artifacts/channel_statistics.json`
- `artifacts/channel_scorecard.json`

