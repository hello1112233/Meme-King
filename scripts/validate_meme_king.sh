#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON:-python3}"
if [[ -x "${PWD}/.venv/bin/python" && -z "${PYTHON:-}" ]]; then
  PYTHON_BIN="${PWD}/.venv/bin/python"
fi

"${PYTHON_BIN}" -m compileall meme_king tools tests
"${PYTHON_BIN}" -m pytest
bash scripts/run_meme_king.sh
bash scripts/run_paper_trading.sh
bash scripts/evaluate_paper_trading.sh
bash scripts/run_execution_gate.sh
bash scripts/train_hermes_trade_skill.sh
bash scripts/validate_hermes_trade_skill_oos.sh
bash scripts/run_live_paper_runtime.sh
bash scripts/check_live_trading_setup.sh
