#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meme_king.channel_registry import ChannelRegistry
from meme_king.deterministic import OLD_OPENCLAW_ROOT, rel, sqlite_readonly_uri, utc_now_iso, write_json


SEARCH_DIRS = ["data", "artifacts", "reports", "observatory", "exports", "out"]
EXTENSIONS = {".json", ".jsonl", ".csv", ".parquet", ".sqlite", ".sqlite3", ".db"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover old Meme Queen/OpenClaw historical data sources.")
    parser.add_argument("--old-root", default=str(OLD_OPENCLAW_ROOT))
    parser.add_argument("--out", default="artifacts/discovered_sources.json")
    args = parser.parse_args()

    old_root = Path(args.old_root).expanduser().resolve()
    registry = ChannelRegistry()
    sources = discover(old_root, registry)
    write_json(
        rel(args.out),
        {
            "created_at": utc_now_iso(),
            "old_root": str(old_root),
            "search_dirs": SEARCH_DIRS,
            "extensions": sorted(EXTENSIONS),
            "sources": sources,
        },
    )


def discover(old_root: Path, registry: ChannelRegistry) -> list[dict[str, Any]]:
    candidates: list[Path] = []
    for dirname in SEARCH_DIRS:
        root = old_root / dirname
        if root.exists():
            candidates.extend(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in EXTENSIONS)
    candidates.extend(path for path in old_root.glob("*") if path.is_file() and path.suffix.lower() in EXTENSIONS)
    seen = set()
    sources = []
    for path in sorted(candidates):
        if path in seen:
            continue
        seen.add(path)
        item = describe_source(path, old_root, registry)
        if item:
            sources.append(item)
    return sources


def describe_source(path: Path, old_root: Path, registry: ChannelRegistry) -> dict[str, Any] | None:
    kind = path.suffix.lower().lstrip(".")
    matched = 0
    sample_matches: list[str] = []
    try:
        if kind in {"json", "jsonl", "csv"}:
            matched, sample_matches = scan_text(path, registry)
        elif kind in {"db", "sqlite", "sqlite3"}:
            matched, sample_matches = scan_sqlite(path, registry)
        elif kind == "parquet":
            matched = 0
    except Exception as exc:
        return {
            "path": str(path),
            "relative_path": str(path.relative_to(old_root)) if path.is_relative_to(old_root) else str(path),
            "kind": kind,
            "size_bytes": path.stat().st_size,
            "matched_records": 0,
            "error": str(exc),
        }
    keywords = ["telegram", "signal", "call", "replay", "observatory", "channel", "meme", "queen", "hermes"]
    likely = any(word in str(path).casefold() for word in keywords) or matched > 0
    if not likely:
        return None
    return {
        "path": str(path),
        "relative_path": str(path.relative_to(old_root)) if path.is_relative_to(old_root) else str(path),
        "kind": kind,
        "size_bytes": path.stat().st_size,
        "matched_records": matched,
        "sample_matches": sample_matches[:5],
    }


def scan_text(path: Path, registry: ChannelRegistry) -> tuple[int, list[str]]:
    matched = 0
    samples: list[str] = []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for idx, line in enumerate(handle):
            if idx > 20_000:
                break
            match = registry.match(line)
            if match:
                matched += 1
                if len(samples) < 5:
                    samples.append(match.canonical_name)
    return matched, samples


def scan_sqlite(path: Path, registry: ChannelRegistry) -> tuple[int, list[str]]:
    matched = 0
    samples: list[str] = []
    conn = sqlite3.connect(sqlite_readonly_uri(path), uri=True)
    try:
        tables = [row[0] for row in conn.execute("select name from sqlite_master where type='table' order by name")]
        for table in tables[:25]:
            columns = [row[1] for row in conn.execute(f'pragma table_info("{table}")')]
            text_columns = [col for col in columns if any(key in col.casefold() for key in ("channel", "source", "payload", "raw", "text", "json", "topic"))]
            if not text_columns:
                continue
            quoted = ", ".join(f'"{col}"' for col in text_columns[:8])
            for row in conn.execute(f'select {quoted} from "{table}" limit 5000'):
                text = " ".join("" if value is None else str(value) for value in row)
                match = registry.match(text)
                if match:
                    matched += 1
                    if len(samples) < 5:
                        samples.append(f"{table}:{match.canonical_name}")
    finally:
        conn.close()
    return matched, samples


if __name__ == "__main__":
    main()
