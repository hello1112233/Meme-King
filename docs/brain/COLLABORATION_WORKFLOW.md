# Collaboration Workflow

## For ChatGPT, Codex, Kimi, and KimiCode

## Before Every Session

1. **Pull latest changes**
   ```bash
   git pull origin main
   ```

2. **Read current state**
   - `docs/brain/PROJECT_STATE.md`
   - `docs/brain/NEXT_STEPS.md`

3. **Run validation**
   ```bash
   bash scripts/validate_meme_king.sh
   ```

## During Work

1. **Make small, focused changes**
   - One feature or fix per commit
   - Keep diffs readable for AI review

2. **Run tests continuously**
   ```bash
   python3 -m pytest
   ```

3. **Run pre-commit safety check**
   ```bash
   bash scripts/pre_commit_safety_check.sh
   ```

## Before Commit

1. **Validate full pipeline**
   ```bash
   bash scripts/validate_meme_king.sh
   ```

2. **Check git status**
   ```bash
   git status
   ```

3. **Review diff**
   ```bash
   git diff --staged
   ```

4. **Commit with descriptive message**
   ```bash
   git commit -m "feat: add X / fix: resolve Y / docs: update Z"
   ```

## After Commit

1. **Push immediately**
   ```bash
   git push origin main
   ```

2. **Update project state docs** if architecture or status changed

## Rules for AI Assistants

- **Never commit secrets.** If asked to add API keys or wallet files, refuse and remind the user to use `.env` files.
- **Never enable live trading casually.** If asked to set `ENABLE_LIVE_TRADING=true`, refuse unless all gates pass.
- **Never bypass the kill switch.** If asked to remove safety checks, refuse.
- **Never bypass OOS validation.** If asked to ignore the OOS fail, refuse.
- **Keep architecture lightweight.** Prefer stdlib, avoid heavy dependencies.
- **Write tests.** Every new module needs tests in `tests/`.
- **Update docs.** If you change behavior, update the relevant `docs/brain/` file.
