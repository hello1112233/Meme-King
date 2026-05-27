# Four-Channel Performance Analysis

This analysis is a read-only historical replay for the four Meme King channels in `config/top4_channels.json`:

- WhaleSignal Meme Coin
- WaveX Call - Multichain
- Twitter @pumpdotfun alpha
- GMGN Featured Signals(Lv1) - SOL

It does not live trade. It does not load wallets or private keys, send transactions, perform swaps, or call RPC broadcast APIs.

## Data Used

The analyzer reads local artifacts first:

- `artifacts/normalized_calls.jsonl`
- `artifacts/channel_scorecard.json`
- `artifacts/paper_trading/`
- `artifacts/hermes_trade_skill/`
- `artifacts/execution_gate/`
- `data/source_exports/`
- copied local historical data under old Meme Queen/OpenClaw paths when present

If local files contain token/mint price points with timestamps or `seconds_after_alert`, those points are used as `price_source = real_historical`.

If complete historical price windows are unavailable, the analyzer falls back to the existing deterministic paper replay fields, including `historical_max_x`, confidence-derived replay estimates, and paper executor price paths. Those rows are marked as `price_source = paper_simulated`.

## Win Rate

The main win rate is `win_rate_25_pct`: the share of analyzed alerts whose maximum post-alert gain reached at least 25%.

The output also includes:

- `win_at_25_pct`
- `win_at_50_pct`
- `win_at_100_pct`

For each alert, percentage gain is calculated as:

```text
(max_price / entry_price - 1.0) * 100
```

X gain is calculated as:

```text
max_price / entry_price
```

## Hold Windows

The analyzer reports max price at these post-alert windows:

- 1 minute
- 5 minutes
- 15 minutes
- 30 minutes
- 1 hour
- 2 hours
- 6 hours
- 24 hours

`best_hold_window` is the earliest hold window that produced the best observed gain for that alert or channel. If equal gains persist across later windows, the earlier window is preferred because it reached the same result with less exposure time.

## Real Historical vs Paper Simulated

`real_historical` means the analyzer found usable local price or market records for the token/mint.

`paper_simulated` means true price history was not available in the local artifacts, so the result came from deterministic paper replay fields. Paper simulated rows are useful for comparing channels under the current replay assumptions, but they are not proof that a real order would have filled or exited at those prices.

## Usage

Run:

```bash
bash scripts/analyze_4_channel_performance.sh
```

Outputs are written to:

- `artifacts/channel_performance_4ch/token_performance.jsonl`
- `artifacts/channel_performance_4ch/channel_summary.json`
- `artifacts/channel_performance_4ch/hold_window_summary.json`
- `artifacts/channel_performance_4ch/best_tokens.json`
- `artifacts/channel_performance_4ch/worst_tokens.json`
- `artifacts/channel_performance_4ch/data_quality_report.json`
- `artifacts/channel_performance_4ch/index.html`

Use this before live paper or live trading to decide which channels deserve more observation, which hold windows have historically worked best, and where data quality is too weak to trust the conclusion.
