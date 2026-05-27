#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON:-python3}"
if [[ -x "${PWD}/.venv/bin/python" && -z "${PYTHON:-}" ]]; then
  PYTHON_BIN="${PWD}/.venv/bin/python"
fi

"${PYTHON_BIN}" tools/analyze_4_channel_performance.py
"${PYTHON_BIN}" tools/render_4_channel_performance_dashboard.py
