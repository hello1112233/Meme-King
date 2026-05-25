# Meme King M1 Optimization

Target hardware: M1 Mac Mini, 8 GB unified memory.

## Constraints

- Unified memory is shared by CPU/GPU and OS.
- Heavy Python data stacks can consume memory quickly.
- Long-running websocket ingestion must avoid memory growth.
- Large graph/vector systems should be offline or derived caches.
- Swap pressure will destroy latency.

## Runtime Budget

| Component | Target RSS | Notes |
| --- | ---: | --- |
| Python ingest process | 150-250 MB | asyncio, aiohttp/websockets, sqlite only |
| SQLite page cache | 64-128 MB | explicit pragmas and bounded write batches |
| enrichment workers | 100-200 MB | inside ingest or separate small process |
| replay/cognition batch | 300-700 MB | scheduled, not always-on |
| DuckDB analytical rebuild | 512 MB-1.5 GB | run with memory limit and threads cap |
| optional Rust executor | 20-80 MB | future, disabled by default |
| dashboard renderer | 100-300 MB | batch generation only |

Keep steady-state below 2 GB RSS to leave room for OS, browser, terminal, and transient batch jobs.

## Python Settings

Recommended environment:

```bash
export PYTHONUNBUFFERED=1
export MEME_KING_MAX_INGEST_QUEUE=5000
export MEME_KING_ENRICH_CONCURRENCY=4
export MEME_KING_SQLITE_BUSY_TIMEOUT_MS=5000
export DUCKDB_MEMORY_LIMIT=1GB
export DUCKDB_THREADS=2
```

Avoid:

- pandas in always-on ingestion.
- loading full JSON exports into memory.
- unbounded task creation.
- in-memory graph rebuilds in the live runtime.
- model inference inside the source ingestion critical path.

## SQLite

SQLite should be the ingest source of truth.

Recommended pragmas for runtime DBs:

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA temp_store=MEMORY;
PRAGMA mmap_size=268435456;
PRAGMA busy_timeout=5000;
```

Use:

- append-only event table
- deterministic unique ID
- small indexed columns for source, token, timestamp, event type
- raw payload compressed only if benchmarks show benefit
- batched writes where latency budget allows

Avoid:

- large analytical joins in the ingest DB
- frequent VACUUM during runtime
- large BLOB vectors in the hot event table

## DuckDB

DuckDB should be a derived analytics layer:

- rebuild from SQLite snapshots
- cap memory: `SET memory_limit='1GB'`
- cap threads: `SET threads=2`
- write analytical outputs to artifacts
- do not use DuckDB as the live event log

DuckDB VSS is useful for offline vector experiments, but its HNSW index must fit in RAM and persistent index support is explicitly experimental in current DuckDB docs. On 8 GB, keep VSS indexes small and rebuildable.

## TurboVec

TurboVec is promising for compact local vector search. The current Rust crate describes 2-4 bit coordinate compression, no training requirement, read/write index files, and concurrent search through `&self`. It should be evaluated as a derived index for:

- similar historical calls
- channel behavior fingerprints
- token narrative similarity
- replay explanation retrieval

Do not place TurboVec in the hot ingest path initially. Build index files offline and memory-map/load them only for cognition queries.

## Recommended Runtime Modes

### Observatory Mode

Default.

- live source ingestion optional
- no executor
- replay/cognition scheduled
- dashboard artifacts

### Paper Execution Simulation Mode

Future safe mode.

- executor sidecar still disabled for live sends
- outbox intents created and journaled
- fake RPC confirms used in tests
- latency and queue behavior measured

### Live Execution Mode

Future gated mode.

- Rust sidecar only
- manual approval
- private keys never loaded by Python
- kill switch required
- fake RPC integration tests must pass first

## Benchmark Plan

Run on the M1 Mac Mini:

1. Ingest 100K historical source events into SQLite and measure p50/p95 write latency.
2. Replay 100K events into projections and measure memory peak.
3. Run DuckDB scorecard queries with `memory_limit=512MB`, `1GB`, and `2GB`.
4. Build TurboVec indexes at 2-bit and 4-bit compression for 10K, 50K, and 100K vectors.
5. Compare TurboVec recall/latency against brute-force NumPy and DuckDB VSS.
6. Simulate 10x source burst and verify queue backpressure.
7. Kill cognition during rebuild and verify event log remains consistent.
8. Kill future executor during leased intents and verify state recovery.

## Operational Guidance

- Run ingestion continuously.
- Run cognition every 1-5 minutes depending on source volume.
- Run DuckDB/vector rebuilds every 15-60 minutes or on demand.
- Keep generated HTML self-contained.
- Use launchd or a simple supervisor, not a large container stack.
- Export tarballs for portability.

