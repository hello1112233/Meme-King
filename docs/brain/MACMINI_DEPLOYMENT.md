# Mac Mini M1 8GB Deployment

## Hardware Target

- Mac Mini M1 (Apple Silicon)
- 8 GB unified memory
- macOS (latest stable)

## Install Steps

```bash
cd ~/Desktop
tar -xzf meme_king_macmini_ready.tar.gz
cd meme_king
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
bash scripts/validate_meme_king.sh
```

## Memory Constraints

| Constraint | Implementation |
|------------|----------------|
| Low RAM | Append-only JSONL, no pandas/numpy in core |
| Fast state | SQLite WAL mode (`PRAGMA journal_mode=WAL`) |
| Backpressure | `asyncio.Queue(maxsize=1000)` drops overflow |
| Bounded caches | `deque(maxlen=5000)` for in-memory state |
| No LLM inference | Pure Python + stdlib hot path |

## Long-Running Process

For 7–14 day live paper collection:

```bash
source .venv/bin/activate
python3 tools/run_live_paper_runtime.py --duration-seconds 604800
```

Use `tmux` or `screen` to keep it running after SSH disconnect:

```bash
tmux new -s meme_king_live
source .venv/bin/activate
python3 tools/run_live_paper_runtime.py --duration-seconds 604800
# Detach: Ctrl-B, D
# Reattach: tmux attach -t meme_king_live
```

## Monitoring

Check daily:
- `artifacts/live_paper/live_daily_summary.json`
- `artifacts/live_paper/live_signals.jsonl` growth
- Disk usage: `du -sh artifacts/live_paper/`

## Safety

- Live trading remains blocked by default
- Kill switch state persisted to `artifacts/live_trading_setup/kill_switch_state.json`
- No private keys on this machine until explicit future enablement
