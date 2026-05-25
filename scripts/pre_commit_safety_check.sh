#!/usr/bin/env bash
set -euo pipefail

FAILED=0

echo "========================================"
echo "Pre-Commit Safety Check"
echo "========================================"

# 1. Check for real .env files (exclude .example.env templates)
echo "[1/5] Checking for .env files..."
ENV_FILES=$(git ls-files | grep -E '\.env$' | grep -v '\.example\.env$' || true)
if [[ -n "${ENV_FILES}" ]]; then
  echo "  FAIL: .env file(s) found in tracked files:"
  echo "${ENV_FILES}" | sed 's/^/    /'
  FAILED=1
else
  echo "  OK: no .env files tracked"
fi

# 2. Check for wallet JSON files
echo "[2/5] Checking for wallet JSON files..."
WALLET_FILES=$(git ls-files | grep -Eiq 'wallet.*\.json|.*wallet.*\.json|keypair.*\.json' && git ls-files | grep -Ei 'wallet.*\.json|.*wallet.*\.json|keypair.*\.json' || true)
if [[ -n "${WALLET_FILES}" ]]; then
  echo "  FAIL: wallet/keypair JSON file(s) found in tracked files:"
  echo "${WALLET_FILES}" | sed 's/^/    /'
  FAILED=1
else
  echo "  OK: no wallet JSON files tracked"
fi

# 3. Check for session files
echo "[3/5] Checking for session files..."
SESSION_FILES=$(git ls-files | grep -E '\.session$|\.session-journal$' || true)
if [[ -n "${SESSION_FILES}" ]]; then
  echo "  FAIL: session file(s) found in tracked files:"
  echo "${SESSION_FILES}" | sed 's/^/    /'
  FAILED=1
else
  echo "  OK: no session files tracked"
fi

# 4. Check for unsafe ENABLE_LIVE_TRADING flags in actual config files only
echo "[4/5] Checking for unsafe ENABLE_LIVE_TRADING flags in config..."
# Only check .env, .json, .toml, .yaml, .yml, .ini files (not docs/tests/code)
CONFIG_FILES=$(git ls-files | grep -E '\.(env|json|toml|yaml|yml|ini)$' | grep -v '\.example\.env$' || true)
LIVE_TRADING_UNSAFE=""
if [[ -n "${CONFIG_FILES}" ]]; then
  LIVE_TRADING_UNSAFE=$(echo "${CONFIG_FILES}" | xargs grep -l 'ENABLE_LIVE_TRADING=true' 2>/dev/null || true)
fi
if [[ -n "${LIVE_TRADING_UNSAFE}" ]]; then
  echo "  FAIL: ENABLE_LIVE_TRADING=true found in config files:"
  echo "${LIVE_TRADING_UNSAFE}" | sed 's/^/    /'
  FAILED=1
else
  echo "  OK: no unsafe ENABLE_LIVE_TRADING flags in config"
fi

# 5. Check for unsafe ENABLE_TRANSACTION_SEND flags in actual config files only
echo "[5/5] Checking for unsafe ENABLE_TRANSACTION_SEND flags in config..."
TX_SEND_UNSAFE=""
if [[ -n "${CONFIG_FILES}" ]]; then
  TX_SEND_UNSAFE=$(echo "${CONFIG_FILES}" | xargs grep -l 'ENABLE_TRANSACTION_SEND=true' 2>/dev/null || true)
fi
if [[ -n "${TX_SEND_UNSAFE}" ]]; then
  echo "  FAIL: ENABLE_TRANSACTION_SEND=true found in config files:"
  echo "${TX_SEND_UNSAFE}" | sed 's/^/    /'
  FAILED=1
else
  echo "  OK: no unsafe ENABLE_TRANSACTION_SEND flags in config"
fi

echo "========================================"
if [[ ${FAILED} -eq 0 ]]; then
  echo "SAFETY CHECK PASSED — OK to commit"
else
  echo "SAFETY CHECK FAILED — fix issues before committing"
fi
echo "========================================"
exit ${FAILED}
