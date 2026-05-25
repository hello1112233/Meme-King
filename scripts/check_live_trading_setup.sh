#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON:-python3}"
if [[ -x "${PWD}/.venv/bin/python" && -z "${PYTHON:-}" ]]; then
  PYTHON_BIN="${PWD}/.venv/bin/python"
fi

"${PYTHON_BIN}" tools/run_live_trading_setup_check.py
"${PYTHON_BIN}" tools/run_dry_run_executor.py
