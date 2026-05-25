#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meme_king.deterministic import read_jsonl, rel, write_json
from meme_king.replay_engine import channel_rankings, channel_statistics, replay


def main() -> None:
    calls = read_jsonl(rel("artifacts/normalized_calls.jsonl"))
    summary = replay(calls)
    stats = channel_statistics(calls)
    rankings = channel_rankings(stats)
    write_json(rel("artifacts/replay_summary.json"), summary)
    write_json(rel("artifacts/channel_statistics.json"), stats)
    write_json(rel("artifacts/channel_rankings.json"), rankings)


if __name__ == "__main__":
    main()
