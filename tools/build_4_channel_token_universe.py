#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meme_king.deterministic import read_json, read_jsonl, rel, write_json
from meme_king.historical_db_extractor import build_token_universe, load_selected_channels, universe_mints, universe_symbols


OUT_DIR = rel("artifacts/historical_market_data")


def main() -> None:
    calls = read_jsonl(rel("artifacts/normalized_calls.jsonl"))
    config = read_json(rel("config/top4_channels.json"), default={"channels": []})
    selected_channels = load_selected_channels(config)
    universe = build_token_universe(calls, selected_channels)
    mints = sorted(universe_mints(universe))
    symbols = sorted(universe_symbols(universe))

    write_json(
        OUT_DIR / "token_universe_4ch.json",
        {
            "selected_channels": selected_channels,
            "token_count": len(universe),
            "mint_count": len(mints),
            "symbol_count": len(symbols),
            "tokens": universe,
        },
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "token_universe_4ch_mints.txt").write_text("\n".join(mints) + ("\n" if mints else ""), encoding="utf-8")
    (OUT_DIR / "token_universe_4ch_symbols.txt").write_text("\n".join(symbols) + ("\n" if symbols else ""), encoding="utf-8")

    print(f"token_universe={len(universe)}")
    print(f"mints={len(mints)}")
    print(f"symbols={len(symbols)}")


if __name__ == "__main__":
    main()
