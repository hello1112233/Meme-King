#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON:-python3}"
if [[ -x "${PWD}/.venv/bin/python" && -z "${PYTHON:-}" ]]; then
  PYTHON_BIN="${PWD}/.venv/bin/python"
fi

"${PYTHON_BIN}" tools/build_4_channel_token_universe.py
"${PYTHON_BIN}" tools/discover_historical_databases.py
"${PYTHON_BIN}" tools/pull_4_channel_historical_market_data.py
"${PYTHON_BIN}" tools/join_4_channel_alerts_to_market_history.py
"${PYTHON_BIN}" tools/analyze_4_channel_performance.py
"${PYTHON_BIN}" tools/render_4_channel_performance_dashboard.py
