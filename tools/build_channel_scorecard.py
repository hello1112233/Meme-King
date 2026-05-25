#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meme_king.deterministic import read_jsonl, rel, write_json
from meme_king.scorecard import build_scorecard


def main() -> None:
    calls = read_jsonl(rel("artifacts/normalized_calls.jsonl"))
    write_json(rel("artifacts/channel_scorecard.json"), build_scorecard(calls))


if __name__ == "__main__":
    main()
