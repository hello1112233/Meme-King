#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON:-python3}"
if [[ -x "${PWD}/.venv/bin/python" && -z "${PYTHON:-}" ]]; then
  PYTHON_BIN="${PWD}/.venv/bin/python"
fi

# Run in mock mode with bounded events for safe initial testing.
# For continuous 7–14 day collection, remove --mock-mode and --max-events
# and wire real ingestor implementations in tools/run_live_paper_runtime.py.
"${PYTHON_BIN}" tools/run_live_paper_runtime.py --mock-mode --max-events 50
