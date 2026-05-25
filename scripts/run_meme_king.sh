#!/usr/bin/env bash
set -euo pipefail

python3 tools/discover_old_meme_queen_data.py
python3 tools/export_top4_channel_data.py
python3 tools/replay_top4_channels.py
python3 tools/build_channel_scorecard.py
python3 tools/render_meme_king_dashboard.py

echo "Meme King artifacts generated:"
echo "  artifacts/discovered_sources.json"
echo "  artifacts/normalized_calls.jsonl"
echo "  artifacts/replay_summary.json"
echo "  artifacts/channel_rankings.json"
echo "  artifacts/channel_statistics.json"
echo "  artifacts/channel_scorecard.json"
echo "  artifacts/index.html"

