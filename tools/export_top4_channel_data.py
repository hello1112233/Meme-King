#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meme_king.channel_registry import ChannelRegistry
from meme_king.deterministic import read_json, rel, sqlite_readonly_uri, stable_hash, utc_now_iso, write_json, write_jsonl
from meme_king.schemas import normalize_call


def main() -> None:
    parser = argparse.ArgumentParser(description="Export and normalize top-four channel records.")
    parser.add_argument("--discovered", default="artifacts/discovered_sources.json")
    parser.add_argument("--out-dir", default="data/source_exports")
    parser.add_argument("--normalized", default="artifacts/normalized_calls.jsonl")
    args = parser.parse_args()

    registry = ChannelRegistry()
    discovered = read_json(rel(args.discovered), default={"sources": []})
    out_dir = rel(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    normalized: list[dict[str, Any]] = []
    export_manifest = []

    for source in discovered.get("sources", []):
        path = Path(source["path"])
        if not path.exists():
            continue
        filtered = []
        for record in iter_records(path):
            call = normalize_call(record, str(path), registry)
            if call:
                filtered.append(record)
                normalized.append(call)
        if filtered:
            export_name = f"{stable_hash(str(path))[:12]}_{path.name}.jsonl"
            export_path = out_dir / export_name
            write_jsonl(export_path, filtered)
            export_manifest.append({"source": str(path), "export": str(export_path.relative_to(rel('.'))), "records": len(filtered)})
        elif source.get("matched_records", 0) > 0 and path.stat().st_size < 25_000_000:
            copy_path = out_dir / f"{stable_hash(str(path))[:12]}_{path.name}"
            shutil.copy2(path, copy_path)
            export_manifest.append({"source": str(path), "export": str(copy_path.relative_to(rel('.'))), "records": 0, "note": "copied candidate source; no structured records normalized"})

    normalized = dedupe_sorted(normalized)
    write_jsonl(rel(args.normalized), normalized)
    write_json(
        rel("artifacts/export_manifest.json"),
        {
            "created_at": utc_now_iso(),
            "exports": export_manifest,
            "normalized_calls": len(normalized),
            "per_channel_counts": per_channel_counts(normalized),
        },
    )


def iter_records(path: Path) -> Iterable[dict[str, Any]]:
    try:
        kind = path.suffix.lower()
        if kind == ".jsonl":
            yield from iter_jsonl(path)
        elif kind == ".json":
            yield from iter_json(path)
        elif kind == ".csv":
            yield from iter_csv(path)
        elif kind in {".db", ".sqlite", ".sqlite3"}:
            yield from iter_sqlite(path)
    except (OSError, sqlite3.Error):
        return


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                row.setdefault("_line_no", line_no)
                yield row


def iter_json(path: Path) -> Iterable[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return
    yield from flatten_json(data)


def flatten_json(data: Any) -> Iterable[dict[str, Any]]:
    if isinstance(data, dict):
        yield data
        for value in data.values():
            if isinstance(value, (dict, list)):
                yield from flatten_json(value)
    elif isinstance(data, list):
        for item in data:
            yield from flatten_json(item)


def iter_csv(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield dict(row)


def iter_sqlite(path: Path) -> Iterable[dict[str, Any]]:
    conn = sqlite3.connect(sqlite_readonly_uri(path), uri=True)
    conn.row_factory = sqlite3.Row
    try:
        tables = [row[0] for row in conn.execute("select name from sqlite_master where type='table' order by name")]
        for table in tables:
            columns = [row[1] for row in conn.execute(f'pragma table_info("{table}")')]
            if not columns:
                continue
            if not any(any(key in col.casefold() for key in ("channel", "source", "payload", "raw", "text", "json", "topic", "event")) for col in columns):
                continue
            for row in conn.execute(f'select * from "{table}" limit 100000'):
                record = dict(row)
                record["_sqlite_table"] = table
                for json_key in ("payload_json", "metadata_json", "raw_json"):
                    value = record.get(json_key)
                    if isinstance(value, str):
                        try:
                            decoded = json.loads(value)
                        except json.JSONDecodeError:
                            decoded = None
                        if isinstance(decoded, dict):
                            merged = {**record, **decoded}
                            merged[f"_{json_key}"] = value
                            yield merged
                yield record
    finally:
        conn.close()


def dedupe_sorted(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    output = []
    for row in sorted(rows, key=lambda item: (item.get("timestamp") or "", item.get("channel_name") or "", str(item.get("message_id") or ""))):
        key = stable_hash({k: row.get(k) for k in ("channel_name", "message_id", "timestamp", "token_symbol", "mint_address", "raw_text")})
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def per_channel_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["channel_name"]] = counts.get(row["channel_name"], 0) + 1
    return dict(sorted(counts.items()))


if __name__ == "__main__":
    main()
