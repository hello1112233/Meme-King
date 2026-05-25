# GitHub Workflow

## Canonical Repository

**GitHub:** `git@github.com:hello1112233/Meme-King.git`

This is the single source of truth for Meme King code, docs, and configuration.

## Before Every Work Session

```bash
git pull origin main
```

## After Every Work Session

```bash
bash scripts/validate_meme_king.sh
bash scripts/pre_commit_safety_check.sh
git add .
git commit -m "describe what changed"
git push origin main
```

## Rules

- **GitHub = canonical repo.** Always pull before work. Always push after commit.
- **ChatGPT Project = memory/context.** Upload docs and key artifacts for AI context, but source of truth remains GitHub.
- **Mac Mini = runtime machine.** Executes the live paper runtime and future live trading.
- **Never commit secrets.** `.env`, wallet JSONs, session files stay local.
- **Never enable live trading casually.** Requires explicit config + kill switch release + OOS pass.
- **Keep Meme King compact.** One feature per commit. Small diffs. Fast reviews.
