#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meme_king.deterministic import read_json, rel, write_json, write_jsonl
from meme_king.historical_db_extractor import extract_from_inventory, json_dumpable_rows


OUT_DIR = rel("artifacts/historical_market_data")


def main() -> None:
    universe_doc = read_json(OUT_DIR / "token_universe_4ch.json", default={"tokens": [], "selected_channels": []})
    inventory = read_json(OUT_DIR / "db_inventory.json", default={"databases": []})
    extracted = extract_from_inventory(universe_doc.get("tokens", []), inventory, universe_doc.get("selected_channels", []))
    summary = {
        **extracted["summary"],
        "token_universe_size": universe_doc.get("token_count", len(universe_doc.get("tokens", []))),
        "market_snapshots_4ch": len(extracted["market_snapshots"]),
        "channel_alerts_4ch": len(extracted["channel_alerts"]),
        "token_lifecycle_4ch": len(extracted["token_lifecycle"]),
    }

    write_jsonl(OUT_DIR / "market_snapshots_4ch.jsonl", json_dumpable_rows(extracted["market_snapshots"]))
    write_jsonl(OUT_DIR / "channel_alerts_4ch.jsonl", json_dumpable_rows(extracted["channel_alerts"]))
    write_jsonl(OUT_DIR / "token_lifecycle_4ch.jsonl", json_dumpable_rows(extracted["token_lifecycle"]))
    write_json(OUT_DIR / "extraction_summary_4ch.json", summary)

    print(f"market_snapshots_4ch={summary['market_snapshots_4ch']}")
    print(f"channel_alerts_4ch={summary['channel_alerts_4ch']}")
    print(f"token_lifecycle_4ch={summary['token_lifecycle_4ch']}")
    print(f"rows_excluded={summary['rows_excluded']}")


if __name__ == "__main__":
    main()
