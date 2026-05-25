#!/usr/bin/env bash
set -e

echo "Running validation..."
bash scripts/validate_meme_king.sh

echo ""
echo "Running safety check..."
bash scripts/pre_commit_safety_check.sh

echo ""
echo "Git status..."
git status

echo ""
echo "Done. Ready to commit/push."
