# Four-Channel Historical Database Extraction

This extractor is scoped to the four selected Meme King channels only:

- WhaleSignal Meme Coin
- WaveX Call - Multichain
- Twitter @pumpdotfun (alpha)
- GMGN Featured Signals(Lv1) - SOL

It does not extract unrelated tokens, dump full databases, live trade, send transactions, load wallets, or read private keys.

## Scope

The first step builds an allowlisted token universe from `artifacts/normalized_calls.jsonl` using only the channels in `config/top4_channels.json`.

Only tokens with a mint address or symbol from those selected-channel alerts are eligible for extraction. Database rows are pulled only when:

- a mint column matches an allowlisted mint, or
- a symbol column matches an allowlisted symbol, or
- a channel column matches one of the four selected channel names

Unmatched rows are counted as excluded and are not written to extraction artifacts.

## Database Discovery

The discovery tool scans the configured local source locations for:

- `.db`
- `.sqlite`
- `.sqlite3`
- `.duckdb`
- `.ddb`

For each database, discovery records table names, schemas, row counts, and columns that look related to mint, token, symbol, price, liquidity, market cap, volume, timestamp, channel, message, signal, alert, or source. It does not extract full rows during discovery.

## Extracted Artifacts

Run:

```bash
bash scripts/pull_4_channel_historical_db_data.sh
```

Outputs:

- `artifacts/historical_market_data/token_universe_4ch.json`
- `artifacts/historical_market_data/token_universe_4ch_mints.txt`
- `artifacts/historical_market_data/token_universe_4ch_symbols.txt`
- `artifacts/historical_market_data/db_inventory.json`
- `artifacts/historical_market_data/market_snapshots_4ch.jsonl`
- `artifacts/historical_market_data/channel_alerts_4ch.jsonl`
- `artifacts/historical_market_data/token_lifecycle_4ch.jsonl`
- `artifacts/historical_market_data/extraction_summary_4ch.json`
- `artifacts/historical_market_data/alert_market_performance_4ch.jsonl`
- `artifacts/historical_market_data/alert_market_summary_4ch.json`

## Replacing Paper Simulation

After extraction, `tools/join_4_channel_alerts_to_market_history.py` joins selected-channel alerts to extracted market snapshots by mint or symbol and timestamp.

When a joined market history exists for an alert, `tools/analyze_4_channel_performance.py` uses it first and marks:

```text
price_source = historical_market_4ch
```

If no joined historical market row exists, the analyzer falls back to the existing deterministic paper replay and marks:

```text
price_source = paper_simulated
```

## Data Quality Limitations

Symbol matching is broader than mint matching because symbols can collide across unrelated tokens. Mint matches are preferred whenever available.

Historical database schemas vary, so extraction uses detected column names and conservative row filters. If a table lacks recognizable mint, symbol, or channel columns, it is not extracted.

Joined performance requires usable timestamps and positive price values. Alerts without timestamps, tokens without market snapshots, or snapshots outside the 24-hour post-alert window remain on `paper_simulated`.
