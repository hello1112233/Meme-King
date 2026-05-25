# Meme King Architecture

Meme King is a standalone historical observatory. It follows a Hermes CLI style cognition flow:

1. Discover candidate local OpenClaw/Meme Queen sources.
2. Filter records through a strict four-channel allowlist.
3. Normalize records into a deterministic JSONL schema.
4. Replay records in stable timestamp/channel/message order.
5. Build channel statistics and scorecards.
6. Render a self-contained HTML observatory dashboard.

## Components

- `meme_king/channel_registry.py`: channel allowlist, alias normalization, and rejection of all non-selected channels.
- `meme_king/schemas.py`: normalized call schema creation from JSON, CSV, and SQLite-derived records.
- `meme_king/replay_engine.py`: deterministic replay ordering, channel rankings, and statistics.
- `meme_king/scorecard.py`: winrate, replay frequency, clustering, recurrence, timing, and confidence scoring.
- `meme_king/renderer.py`: self-contained HTML dashboard renderer.
- `tools/*.py`: CLI orchestration entry points.
- `scripts/run_meme_king.sh`: full deterministic pipeline runner.

## Deterministic Guarantees

- Inputs are local files only.
- SQLite databases are opened read-only using `mode=ro`.
- Outputs are sorted by timestamp, channel name, and message id.
- JSON artifacts use sorted keys.
- Duplicate normalized records are removed with stable SHA-256 keys.
- No network, wallet, private key, transaction, swap, or autonomous execution code exists.

## Replay Methodology

Replay is event-order reconstruction from historical records. It does not infer live market state or make trading decisions. When historical multiplier or confidence fields exist, they are included in statistics; missing fields remain `null`.

## Observatory Boundaries

The system is research/replay only. It can produce evidence artifacts and HTML summaries, but it cannot submit transactions, place orders, connect wallets, sign payloads, or execute autonomous actions.

