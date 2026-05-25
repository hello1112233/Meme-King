#!/usr/bin/env bash
set -euo pipefail

FAILED=0

echo "========================================"
echo "Pre-Commit Safety Check"
echo "========================================"

# 1. Check for .env files
echo "[1/5] Checking for .env files..."
if git ls-files | grep -Eq '^\.env$|\.env$'; then
  echo "  FAIL: .env file(s) found in tracked files:"
  git ls-files | grep -E '^\.env$|\.env$' | sed 's/^/    /'
  FAILED=1
else
  echo "  OK: no .env files tracked"
fi

# 2. Check for wallet JSON files
echo "[2/5] Checking for wallet JSON files..."
if git ls-files | grep -Eiq 'wallet.*\.json|.*wallet.*\.json|keypair.*\.json'; then
  echo "  FAIL: wallet/keypair JSON file(s) found in tracked files:"
  git ls-files | grep -Eiq 'wallet.*\.json|.*wallet.*\.json|keypair.*\.json' | sed 's/^/    /'
  FAILED=1
else
  echo "  OK: no wallet JSON files tracked"
fi

# 3. Check for session files
echo "[3/5] Checking for session files..."
if git ls-files | grep -Eq '\.session$|\.session-journal$'; then
  echo "  FAIL: session file(s) found in tracked files:"
  git ls-files | grep -E '\.session$|\.session-journal$' | sed 's/^/    /'
  FAILED=1
else
  echo "  OK: no session files tracked"
fi

# 4. Check for ENABLE_LIVE_TRADING=true in config templates
echo "[4/5] Checking for unsafe ENABLE_LIVE_TRADING flags..."
if git grep -n "ENABLE_LIVE_TRADING=true" -- ':!scripts/pre_commit_safety_check.sh' || \
   git grep -n "ENABLE_LIVE_TRADING = true" -- ':!scripts/pre_commit_safety_check.sh' || \
   git grep -n "ENABLE_LIVE_TRADING=1" -- ':!scripts/pre_commit_safety_check.sh' 2>/dev/null; then
  echo "  FAIL: ENABLE_LIVE_TRADING set to true in tracked files"
  FAILED=1
else
  echo "  OK: no unsafe ENABLE_LIVE_TRADING flags found"
fi

# 5. Check for ENABLE_TRANSACTION_SEND=true in config templates
echo "[5/5] Checking for unsafe ENABLE_TRANSACTION_SEND flags..."
if git grep -n "ENABLE_TRANSACTION_SEND=true" -- ':!scripts/pre_commit_safety_check.sh' || \
   git grep -n "ENABLE_TRANSACTION_SEND = true" -- ':!scripts/pre_commit_safety_check.sh' || \
   git grep -n "ENABLE_TRANSACTION_SEND=1" -- ':!scripts/pre_commit_safety_check.sh' 2>/dev/null; then
  echo "  FAIL: ENABLE_TRANSACTION_SEND set to true in tracked files"
  FAILED=1
else
  echo "  OK: no unsafe ENABLE_TRANSACTION_SEND flags found"
fi

echo "========================================"
if [[ ${FAILED} -eq 0 ]]; then
  echo "SAFETY CHECK PASSED — OK to commit"
else
  echo "SAFETY CHECK FAILED — fix issues before committing"
fi
echo "========================================"
exit ${FAILED}
