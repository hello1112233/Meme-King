#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meme_king.deterministic import read_json, read_jsonl, rel
from meme_king.renderer import render_dashboard


def main() -> None:
    html = render_dashboard(
        replay_summary=read_json(rel("artifacts/replay_summary.json"), default={}),
        rankings=read_json(rel("artifacts/channel_rankings.json"), default=[]),
        statistics=read_json(rel("artifacts/channel_statistics.json"), default={}),
        scorecard=read_json(rel("artifacts/channel_scorecard.json"), default={}),
        discovered=read_json(rel("artifacts/discovered_sources.json"), default={"sources": []}),
        normalized_count=len(read_jsonl(rel("artifacts/normalized_calls.jsonl"))),
    )
    rel("artifacts/index.html").write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
