# Live Paper Runtime

## Purpose

The live paper runtime is a **read-only signal collection and paper simulation loop**. It does not trade real money, hold private keys, call RPC endpoints, or submit transactions.

Its sole purpose is to collect live signals continuously for **7–14 days** so the Hermes trade skill can gain real temporal diversity for out-of-sample (OOS) validation.

## What It Does

1. **Ingests** events from configured sources (Telegram, DexScreener, PumpPortal, GMGN, Pump.fun)
2. **Normalizes** raw events into the same format used by historical replay
3. **Deduplicates** events via SQLite-backed state (survives restarts)
4. **Runs the execution gate** with persistent cooldown/position/token counts
5. **Runs the Hermes trade skill** on approved signals
6. **Creates paper trades only** using the existing `PaperExecutor`
7. **Appends** results to rolling JSONL logs

## What It Does NOT Do

- No wallet integration
- No private key handling
- No RPC `sendTransaction`
- No swap execution
- No LLM inference
- No large in-memory dataframes

## Architecture

```
Ingestors (async generators)
    → Bounded asyncio.Queue(maxsize=1000)
    → Normalizer
    → SQLite dedup check
    → Execution Gate (persistent state)
    → Hermes Trade Skill
    → Paper Executor (simulation only)
    → Append-only JSONL logs
```

### Memory Optimizations for M1 Mac Mini 8GB

- **Append-only JSONL**: Logs are never rewritten. The runtime only opens files in append mode.
- **SQLite WAL mode**: Writes do not block reads. Journal is kept on disk, not in memory.
- **Bounded queue**: `asyncio.Queue(maxsize=1000)` drops events under backpressure instead of growing unbounded.
- **No pandas/numpy**: Pure Python + stdlib. Low RAM footprint.
- **Stateless skill**: Hermes trade skill has no hidden state. The gate state is persisted to SQLite after each signal.
- **File handle discipline**: Files are opened, written, and closed per event. Safe for long-running processes.

## Outputs

| Artifact | Description |
|----------|-------------|
| `artifacts/live_paper/live_signals.jsonl` | All normalized signals ingested |
| `artifacts/live_paper/live_gate_decisions.jsonl` | Gate decisions with reasons |
| `artifacts/live_paper/live_paper_positions.jsonl` | Closed paper positions from approved+skilled signals |
| `artifacts/live_paper/live_daily_summary.json` | Daily rollup stats |
| `artifacts/live_paper/live_state.db` | SQLite WAL database for dedup, cooldowns, positions, token counts |

## Running

### Quick test (mock ingestors, bounded events)

```bash
bash scripts/run_live_paper_runtime.sh
```

### Replay historical calls as a mock live feed

```bash
python3 tools/run_live_paper_runtime.py --replay-calls --max-events 500
```

### Continuous collection (after wiring real ingestors)

```bash
python3 tools/run_live_paper_runtime.py --duration-seconds 604800
```

Run for 7 days (604,800 seconds). The runtime gracefully handles SIGINT and persists state.

## Ingestor Stubs

The runtime ships with stub ingestors that yield synthetic events for safe testing:

- `StubTelegramIngestor`
- `StubDexScreenerIngestor`
- `StubPumpPortalIngestor`
- `StubGMGNIngestor`
- `StubPumpFunIngestor`

To connect real APIs, subclass `Ingestor` and implement `async def events(self)`. Drop the new ingestor into the runtime's ingestor list.

## OOS Timeline

After 7–14 days of continuous collection:

1. Run `tools/validate_hermes_trade_skill_oos.py`
2. The day-coverage check should now read ≥ 7 (or ≥ 14)
3. If all thresholds pass, the skill is cleared for **micro live testing**

Until then, the runtime stays in paper-only mode.
