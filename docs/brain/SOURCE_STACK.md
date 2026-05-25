# Source Stack

## Required Sources (for live paper + future live trading)

| Source | Purpose | Integration Point |
|--------|---------|-------------------|
| Telegram | Signal channel ingestion | `tools/run_live_paper_runtime.py` → `StubTelegramIngestor` replacement |
| Helius RPC | Solana node access | `config/live_trading.env` → `HELIUS_RPC_URL` |
| Jupiter API | Swap routing / quotes | `config/live_trading.env` → `JUPITER_API_BASE` |
| PumpPortal WebSocket | Launch events | `tools/run_live_paper_runtime.py` → new ingestor |
| Pump.fun API | Graduation events | `tools/run_live_paper_runtime.py` → new ingestor |
| DexScreener | Token snapshots / liquidity | `tools/run_live_paper_runtime.py` → new ingestor |
| GMGN API | Smart money signals | `tools/run_live_paper_runtime.py` → new ingestor |

## Optional Sources

| Source | Purpose | Notes |
|--------|---------|-------|
| Twitter/X API | Alpha signals | Expensive, low priority |
| Jito | MEV-protected transactions | Future optimization |
| Birdeye | Price feeds | Alternative to DexScreener |

## Removed Sources

| Source | Reason |
|--------|--------|
| Alchemy | Removed from stack; Helius preferred for Solana |

## Configuration Template

Copy `config/live_trading.example.env` to `config/live_trading.env` and fill in real values.
Keep all `ENABLE_*` flags `false` during live paper collection.
