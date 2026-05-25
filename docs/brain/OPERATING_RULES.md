# Operating Rules

## Do

- Keep the architecture lightweight (M1 Mac Mini 8GB target)
- Use append-only JSONL logs
- Use SQLite WAL mode for state
- Use bounded queues (`asyncio.Queue(maxsize=1000)`)
- Run `bash scripts/validate_meme_king.sh` before every commit
- Commit frequently with descriptive messages
- Pull before starting any work session
- Prefer stdlib over heavy dependencies
- Write tests for every new module

## Do Not

- **Do NOT overbuild.** Solve the current goal, not every hypothetical future goal.
- **Do NOT enable live trading casually.** It requires explicit config changes + kill switch release + OOS pass.
- **Do NOT bypass the kill switch.** It exists for a reason.
- **Do NOT bypass OOS validation.** 100% historical winrate is suspect until OOS passes.
- **Do NOT commit secrets.** No `.env`, no wallet JSONs, no session files, no API keys.
- **Do NOT add LLM inference to the hot path.** Keep the runtime deterministic and fast.
- **Do NOT accumulate giant in-memory datasets.** Stream and append.
- **Do NOT modify safety boundaries without updating docs.**
