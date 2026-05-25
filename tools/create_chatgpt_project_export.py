#!/usr/bin/env python3
"""Create a flat export package for ChatGPT Project upload.

Flattens all important source files, configs, docs, and artifacts into a single
folder with unique descriptive filenames. Excludes caches, WAL files, venv,
giant datasets, and temporary files.
"""
from __future__ import annotations

import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = Path("/Users/macbook/Desktop/meme_king_export")
MAX_SAMPLE_LINES = 1000


def flatten_name(rel_path: Path) -> str:
    """Convert a relative path to a unique flat filename."""
    parts = list(rel_path.parts)
    # Replace dots in hidden files and slashes in paths
    name = "_".join(parts)
    # Ensure no double underscores and safe chars
    name = name.replace("__", "_")
    return name


def ensure_unique(names: dict[Path, str]) -> dict[Path, str]:
    """Resolve collisions by appending a counter."""
    counts: Counter[str] = Counter()
    result: dict[Path, str] = {}
    for src, proposed in names.items():
        counts[proposed] += 1
        if counts[proposed] > 1:
            stem = Path(proposed).stem
            suffix = Path(proposed).suffix
            unique_name = f"{stem}_{counts[proposed]}{suffix}"
            result[src] = unique_name
        else:
            result[src] = proposed
    return result


def sample_jsonl(src: Path, dst: Path, max_lines: int = MAX_SAMPLE_LINES) -> None:
    """Copy first N lines of a JSONL file as a representative sample."""
    lines_written = 0
    with src.open("r", encoding="utf-8") as fin, dst.open("w", encoding="utf-8") as fout:
        for line in fin:
            if lines_written >= max_lines:
                break
            if line.strip():
                fout.write(line)
                lines_written += 1


def build_file_list() -> dict[Path, str]:
    """Map source paths to flattened export names."""
    mappings: dict[Path, str] = {}

    # --- Core source ---------------------------------------------------------
    core_src = list((PROJECT_ROOT / "meme_king").glob("*.py"))
    for src in core_src:
        if src.name == "__pycache__":
            continue
        mappings[src] = flatten_name(src.relative_to(PROJECT_ROOT))

    # --- Tests ---------------------------------------------------------------
    test_src = list((PROJECT_ROOT / "tests").glob("*.py"))
    for src in test_src:
        mappings[src] = flatten_name(src.relative_to(PROJECT_ROOT))

    # --- Tools ---------------------------------------------------------------
    tool_src = list((PROJECT_ROOT / "tools").glob("*.py"))
    for src in tool_src:
        mappings[src] = flatten_name(src.relative_to(PROJECT_ROOT))

    # --- Scripts -------------------------------------------------------------
    script_src = list((PROJECT_ROOT / "scripts").glob("*.sh"))
    for src in script_src:
        mappings[src] = flatten_name(src.relative_to(PROJECT_ROOT))

    # --- Config --------------------------------------------------------------
    for src in (PROJECT_ROOT / "config").glob("*"):
        if src.is_file():
            mappings[src] = flatten_name(src.relative_to(PROJECT_ROOT))

    # --- Docs ----------------------------------------------------------------
    for src in (PROJECT_ROOT / "docs").glob("*.md"):
        mappings[src] = flatten_name(src.relative_to(PROJECT_ROOT))

    # --- Root files ----------------------------------------------------------
    for name in ("README.md", "pyproject.toml", "requirements-dev.txt", ".gitignore"):
        src = PROJECT_ROOT / name
        if src.exists():
            mappings[src] = name

    # --- Small artifacts (summaries only) ------------------------------------
    artifact_files = [
        "artifacts/channel_rankings.json",
        "artifacts/channel_statistics.json",
        "artifacts/channel_scorecard.json",
        "artifacts/replay_summary.json",
        "artifacts/execution_gate/gate_summary.json",
        "artifacts/paper_trading/paper_summary.json",
        "artifacts/paper_trading/evaluation_summary.json",
        "artifacts/paper_trading/strategy_comparison.json",
        "artifacts/paper_trading/channel_performance.json",
        "artifacts/hermes_trade_skill/skill_rules.json",
        "artifacts/hermes_trade_skill/backtest_summary.json",
        "artifacts/hermes_trade_skill/training_summary.json",
        "artifacts/hermes_trade_skill/oos_validation.json",
        "artifacts/live_paper/live_daily_summary.json",
        "artifacts/live_trading_setup/setup_readiness.json",
        "artifacts/live_trading_setup/dry_run_summary.json",
        "artifacts/live_trading_setup/kill_switch_state.json",
        "artifacts/live_trading_setup/risk_limits.json",
        "artifacts/live_trading_setup/missing_items.json",
    ]
    for rel in artifact_files:
        src = PROJECT_ROOT / rel
        if src.exists():
            mappings[src] = flatten_name(Path(rel))

    # --- Small datasets (full) -----------------------------------------------
    small_datasets = [
        "artifacts/hermes_trade_skill/accepted_setups.jsonl",
        "artifacts/execution_gate/approved_paper_signals.jsonl",
    ]
    for rel in small_datasets:
        src = PROJECT_ROOT / rel
        if src.exists():
            mappings[src] = flatten_name(Path(rel))

    # --- Large dataset (sampled) ---------------------------------------------
    large_jsonl = PROJECT_ROOT / "artifacts/normalized_calls.jsonl"
    if large_jsonl.exists():
        sample_name = "artifacts_normalized_calls_SAMPLE.jsonl"
        mappings[large_jsonl] = sample_name

    return ensure_unique(mappings)


def write_export_readme() -> None:
    text = """MEME KING — ChatGPT Project Export
=====================================

This is a flattened export of the Meme King project for continuation
in ChatGPT Projects or on another computer.

WHAT IS INCLUDED
----------------
- Core Python modules (meme_king_*.py)
- Tests (tests_*.py)
- Tools (tools_*.py)
- Shell scripts (scripts_*.sh)
- Configuration templates (config_*.json / .env)
- Architecture and runtime documentation (docs_*.md)
- JSON artifacts and summaries (artifacts_*.json)
- Representative dataset sample (artifacts_normalized_calls_SAMPLE.jsonl)
- Setup files (pyproject.toml, requirements-dev.txt, README.md)

WHAT IS EXCLUDED
----------------
- .venv (rebuild locally)
- __pycache__ / .pytest_cache
- SQLite WAL/shm files
- Giant raw datasets (orders, fills, exits, blocked signals)
- Node modules (none in this project)
- Temporary files

CONTINUATION CHECKLIST
----------------------
1. python3 -m venv .venv
2. source .venv/bin/activate
3. python3 -m pip install -e ".[dev]"
4. bash scripts/validate_meme_king.sh
5. Review docs/LIVE_TRADING_SETUP.md before considering live trading

SAFETY
------
Live trading is DISABLED by default.
No private keys are included in this export.
All transaction submission requires explicit ENABLE_TRANSACTION_SEND=true.
"""
    (EXPORT_DIR / "EXPORT_README.txt").write_text(text, encoding="utf-8")


def write_macmini_setup() -> None:
    text = """Mac Mini M1 8GB Setup Guide
===========================

1. Install Python 3.11+ (Homebrew or python.org)
2. Open Terminal in the project folder
3. Create virtual environment:
   python3 -m venv .venv
4. Activate:
   source .venv/bin/activate
5. Install dependencies:
   python3 -m pip install -e ".[dev]"
6. Run validation:
   bash scripts/validate_meme_king.sh

MEMORY OPTIMIZATION NOTES
-------------------------
- Append-only JSONL logs (no rewrites)
- SQLite WAL mode for state persistence
- Bounded asyncio.Queue(maxsize=1000)
- No pandas/numpy required for core runtime
- Dry-run executor uses stdlib only

LIVE TRADING (SCAFFOLDING ONLY)
-------------------------------
Real trading is blocked by default.
Copy config/live_trading.example.env to config/live_trading.env
Fill in API keys and set ENABLE_LIVE_TRADING=true ONLY after:
- OOS validation passes (day coverage >= 7)
- Dry-run executor runs cleanly
- Kill switch can_trade() returns True
"""
    (EXPORT_DIR / "MACMINI_SETUP.txt").write_text(text, encoding="utf-8")


def write_import_order() -> None:
    text = """ChatGPT Project Import Order
=============================

Recommended upload order for ChatGPT Projects (knowledge files):

1. README.md
2. pyproject.toml
3. requirements-dev.txt
4. EXPORT_README.txt
5. MACMINI_SETUP.txt
6. docs_MEME_KING_ARCHITECTURE.md
7. docs_MEME_KING_RUNTIME_ARCHITECTURE.md
8. docs_LIVE_TRADING_SETUP.md
9. docs_LIVE_PAPER_RUNTIME.md
10. docs_HERMES_TRADE_SKILL_OOS.md
11. docs_HERMES_TRADE_SKILL.md
12. docs_PAPER_TRADING_SANDBOX.md
13. docs_EXECUTION_GATE.md
14. meme_king_live_trading_config.py
15. meme_king_kill_switch.py
16. meme_king_live_executor_interface.py
17. meme_king_dry_run_executor.py
18. meme_king_hermes_trade_skill.py
19. meme_king_execution_gate.py
20. meme_king_paper_executor.py
21. meme_king_paper_metrics.py
22. meme_king_replay_engine.py
23. meme_king_channel_registry.py
24. meme_king_deterministic.py
25. meme_king_strategy_profiles.py
26. artifacts_hermes_trade_skill_skill_rules.json
27. artifacts_hermes_trade_skill_oos_validation.json
28. artifacts_live_trading_setup_setup_readiness.json
29. artifacts_live_trading_setup_dry_run_summary.json
30. artifacts_execution_gate_gate_summary.json
31. artifacts_paper_trading_paper_summary.json
32. artifacts_paper_trading_evaluation_summary.json
33. artifacts_live_paper_live_daily_summary.json
34. artifacts_channel_scorecard.json
35. artifacts_channel_rankings.json
36. artifacts_channel_statistics.json
37. artifacts_replay_summary.json
38. config_top4_channels.json
39. config_live_trading_example.env
40. scripts_validate_meme_king.sh
41. All remaining tests_*.py and tools_*.py as needed
42. artifacts_normalized_calls_SAMPLE.jsonl (last, largest)

NOTE: ChatGPT Projects have file size limits. If the sample JSONL is too large,
upload it in parts or omit it and reference the structure from the code.
"""
    (EXPORT_DIR / "PROJECT_SESSION_IMPORT_ORDER.txt").write_text(text, encoding="utf-8")


def generate_manifest(copies: dict[Path, Path]) -> dict[str, Any]:
    entries = []
    total_size = 0
    for src, dst in copies.items():
        size = dst.stat().st_size
        total_size += size
        try:
            rel = str(src.relative_to(PROJECT_ROOT))
            category = rel.split("/")[0]
        except ValueError:
            rel = dst.name
            category = "generated"
        entries.append(
            {
                "source_path": rel,
                "export_name": dst.name,
                "size_bytes": size,
                "category": category,
            }
        )
    entries.sort(key=lambda x: x["export_name"])
    return {
        "export_dir": str(EXPORT_DIR),
        "total_files": len(entries),
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "flat": True,
        "files": entries,
    }


def main() -> None:
    if EXPORT_DIR.exists():
        shutil.rmtree(EXPORT_DIR)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    file_list = build_file_list()
    copies: dict[Path, Path] = {}

    for src, flat_name in file_list.items():
        dst = EXPORT_DIR / flat_name
        if src.name == "normalized_calls.jsonl" and flat_name == "artifacts_normalized_calls_SAMPLE.jsonl":
            sample_jsonl(src, dst, MAX_SAMPLE_LINES)
        elif src.name == "replay_summary.json" and flat_name == "artifacts_replay_summary.json":
            # Trim the massive timeline array to first/last 50 entries
            with src.open("r", encoding="utf-8") as f:
                data = json.load(f)
            timeline = data.get("timeline", [])
            if len(timeline) > 200:
                data["timeline"] = timeline[:100] + timeline[-100:]
                data["timeline_note"] = f"Trimmed from {len(timeline)} to 200 entries for export"
            with dst.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, sort_keys=True)
                f.write("\n")
        else:
            shutil.copy2(src, dst)
        copies[src] = dst

    write_export_readme()
    write_macmini_setup()
    write_import_order()

    # Add generated text files to manifest
    for gen_name in ("EXPORT_README.txt", "MACMINI_SETUP.txt", "PROJECT_SESSION_IMPORT_ORDER.txt"):
        gen_path = EXPORT_DIR / gen_name
        if gen_path.exists():
            copies[gen_path] = gen_path

    manifest = generate_manifest(copies)
    manifest_path = EXPORT_DIR / "export_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")

    # Print report
    print("=" * 50)
    print("MEME KING — CHATGPT PROJECT EXPORT COMPLETE")
    print("=" * 50)
    print(f"Export folder:     {EXPORT_DIR}")
    print(f"Total files:       {manifest['total_files']}")
    print(f"Total size:        {manifest['total_size_mb']} MB")
    print(f"Flat (no subs):    {manifest['flat']}")
    print("-" * 50)
    print("Largest files:")
    largest = sorted(manifest["files"], key=lambda x: -x["size_bytes"])[:10]
    for entry in largest:
        size_kb = round(entry["size_bytes"] / 1024, 1)
        print(f"  {entry['export_name']:60s} {size_kb:>8.1f} KB")
    print("-" * 50)
    print(f"Manifest:          {manifest_path}")
    print("=" * 50)


if __name__ == "__main__":
    main()
