#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meme_king.deterministic import read_json, read_jsonl, rel, write_json, write_jsonl
from meme_king.historical_db_extractor import join_alerts_to_market, json_dumpable_rows, load_selected_channels


OUT_DIR = rel("artifacts/historical_market_data")


def main() -> None:
    calls = read_jsonl(rel("artifacts/normalized_calls.jsonl"))
    snapshots = read_jsonl(OUT_DIR / "market_snapshots_4ch.jsonl")
    config = read_json(rel("config/top4_channels.json"), default={"channels": []})
    selected_channels = load_selected_channels(config)
    joined, summary = join_alerts_to_market(calls, snapshots, selected_channels)

    write_jsonl(OUT_DIR / "alert_market_performance_4ch.jsonl", json_dumpable_rows(joined))
    write_json(OUT_DIR / "alert_market_summary_4ch.json", summary)

    print(f"alert_market_joins={summary['alert_market_joins']}")
    print(f"unjoined_alerts={summary['unjoined_alerts']}")
    print(f"alert_market_performance={OUT_DIR / 'alert_market_performance_4ch.jsonl'}")


if __name__ == "__main__":
    main()
