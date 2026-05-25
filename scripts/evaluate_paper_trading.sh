#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON:-python3}"
if [[ -x "${PWD}/.venv/bin/python" && -z "${PYTHON:-}" ]]; then
  PYTHON_BIN="${PWD}/.venv/bin/python"
fi

"${PYTHON_BIN}" tools/evaluate_paper_trading.py
"${PYTHON_BIN}" tools/render_paper_trading_dashboard.py

