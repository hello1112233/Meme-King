# Portability Guide

## Setup

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
bash scripts/run_meme_king.sh
```

## Moving Computers

Copy the full project directory, not only the Python package directory. The directory should include:

- `README.md`
- `pyproject.toml`
- `requirements-dev.txt`
- `meme_king/`
- `tools/`
- `scripts/`
- `tests/`
- `docs/`
- `config/`
- `data/`
- `artifacts/`

Exact copy flow from the original computer:

```bash
cd /Users/macbook/Desktop
tar -czf meme_king_portable.tar.gz meme_king
```

On the new computer:

```bash
mkdir -p ~/Desktop
cd ~/Desktop
tar -xzf /path/to/meme_king_portable.tar.gz
cd meme_king
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
```

The project uses relative paths internally for its own config, data, artifacts, tests, and docs.

The default old source path is `/Users/macbook/openclaw`. On another computer, run discovery with a replacement path:

```bash
python3 tools/discover_old_meme_queen_data.py --old-root /path/to/openclaw
bash scripts/run_meme_king.sh
```

If the old source data is not available, previously generated files in `data/source_exports/` and `artifacts/normalized_calls.jsonl` can still be inspected, but a fresh discovery/export requires the old source directory.

## Validate On A New Computer

```bash
bash scripts/validate_meme_king.sh
```

This runs:

- `python3 -m compileall meme_king tools tests`
- `python3 -m pytest`
- `bash scripts/run_meme_king.sh`

## Open Dashboard

Open:

```text
artifacts/index.html
```

If the project has not been initialized as a git repository, `git diff --check` prints a Git usage warning. That warning is expected for a copied standalone folder and does not affect Meme King validation. To use git checks on a new computer, run `git init` first.

## Generated Artifacts

Generated files are intentionally ignored by git:

- `artifacts/*.json`
- `artifacts/*.jsonl`
- `artifacts/*.html`
- `data/source_exports/*`

Keep those files when moving a completed replay snapshot.

## Safety

Meme King has no trading dependencies and no wallet integration. It only reads local files and writes deterministic artifacts under this project directory.

Historical SQLite files are opened with `mode=ro&immutable=1`. `shadow_trading.db`, when present, is handled only as historical read-only data; no trading behavior is imported or executed.
