#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meme_king.deterministic import rel, write_json
from meme_king.historical_db_extractor import discover_database_files, discover_databases


OUT_DIR = rel("artifacts/historical_market_data")


def main() -> None:
    db_files = discover_database_files()
    inventory = discover_databases(db_files)
    write_json(OUT_DIR / "db_inventory.json", inventory)
    totals = inventory.get("totals", {})
    print(f"sqlite_dbs={totals.get('sqlite', 0)}")
    print(f"duckdb_dbs={totals.get('duckdb', 0)}")
    print(f"tables={totals.get('tables', 0)}")
    print(f"db_inventory={OUT_DIR / 'db_inventory.json'}")


if __name__ == "__main__":
    main()
