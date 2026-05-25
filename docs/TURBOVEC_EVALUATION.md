# TurboVec Evaluation

This document evaluates TurboVec integration possibilities for Meme King. It is architecture-only and does not add TurboVec as a dependency.

## Current Research Notes

TurboVec `0.5.0` on docs.rs is a Rust crate for TurboQuant vector search. Its documentation says it compresses high-dimensional vectors to 2-4 bits per coordinate, is data-oblivious with no training required, supports read/write index files, and allows concurrent search because `search` takes `&self`. It also exposes a `prepare` path to pay lazy initialization costs up front.

DuckDB's official VSS extension provides HNSW vector indexes over fixed-size `FLOAT` arrays. Its docs call the extension experimental for persistence; HNSW indexes must fit in RAM, and persistent index storage has WAL/recovery caveats.

SQLite's official `vec1` extension is a recent SQLite vector extension using virtual tables for approximate nearest-neighbor search. It is worth watching, but portability and Python/Rust packaging should be benchmarked before adoption.

References:

- TurboVec docs: https://docs.rs/turbovec/latest/turbovec/
- DuckDB VSS docs: https://duckdb.org/docs/current/core_extensions/vss.html
- DuckDB VSS blog: https://duckdb.org/2024/05/03/vector-similarity-search-vss
- SQLite vec1 docs: https://sqlite.org/vec1

## Candidate Uses

TurboVec should be considered for derived cognition indexes:

- similar call retrieval
- channel behavior vectors
- token lifecycle fingerprints
- source reliability fingerprints
- replay-nearest-neighbor explanations

It should not be used for:

- transaction execution
- private-key operations
- hot source ingestion
- source-of-truth persistence
- safety-critical hard gates until benchmarked

## SQLite + DuckDB + TurboVec Hybrid

Recommended split:

| Layer | Tool | Responsibility |
| --- | --- | --- |
| Source of truth | SQLite | append-only events, outbox, health, deterministic logs |
| Analytics | DuckDB | batch joins, scorecards, aggregate features, parquet/csv exports |
| Vector retrieval | TurboVec | compact approximate nearest-neighbor index over derived feature vectors |

Data flow:

```text
SQLite events -> projection tables -> DuckDB feature export -> TurboVec index build
                                                |
                                                v
                                     cognition query results
```

TurboVec index files should include:

- index version
- feature schema version
- source dataset hash
- vector dimension
- compression bits
- build timestamp
- record ID mapping

## Benchmark Matrix

| Test | Dataset Sizes | Metrics |
| --- | --- | --- |
| Build time | 10K, 50K, 100K, 500K vectors | seconds, peak RSS |
| Search latency | 1, 10, 100 query batch | p50/p95 latency |
| Recall | known nearest-neighbor fixture | recall@10, recall@50 |
| Compression | 2-bit vs 4-bit | index size, recall, latency |
| Warmup | cold load vs `prepare` | first query latency |
| Concurrency | 1, 2, 4 threads | throughput, tail latency |
| Rebuild safety | interrupted build | old index remains readable |

## M1-Specific Test Parameters

- dimensions: 64, 128, 384, 768, 1536
- compression: 2 and 4 bits
- vector counts: 10K to 500K
- memory ceiling: 256 MB per index target
- thread counts: 1, 2, 4
- query batch sizes: 1, 8, 32

## Integration Plan

Phase A: no runtime dependency.

- define vector feature schema
- export vectors from replay artifacts
- write benchmark harness
- compare with brute-force baseline

Phase B: optional offline index.

- build `artifacts/vector/*.tv`
- build ID map
- query from CLI only
- verify deterministic results for fixed input

Phase C: cognition integration.

- use TurboVec nearest neighbors to annotate replay scorecards
- never make hard execution decisions solely from approximate vector search
- record index hash in every explanation

## Risks

- crate maturity and API stability
- arm64/macOS performance unknown until local benchmark
- approximate search recall may be insufficient for safety gates
- index rebuilds could spike memory
- feature drift can make old indexes misleading

## Recommendation

Use TurboVec as an optional derived cognition accelerator, not as a runtime dependency. Keep SQLite and DuckDB sufficient for all core observatory functions. Adopt TurboVec only after local M1 benchmarks prove that it improves latency or memory use versus DuckDB/SQLite/NumPy baselines.

