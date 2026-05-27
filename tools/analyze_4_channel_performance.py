#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meme_king.channel_performance_analyzer import ChannelPerformanceAnalyzer
from meme_king.deterministic import read_json, read_jsonl, rel, write_json, write_jsonl


OUT_DIR = rel("artifacts/channel_performance_4ch")


def main() -> None:
    calls = read_jsonl(rel("artifacts/normalized_calls.jsonl"))
    config = read_json(rel("config/top4_channels.json"), default={"channels": []})
    selected_channels = [row["canonical_name"] for row in config.get("channels", [])]
    paper_positions = read_jsonl(rel("artifacts/paper_trading/paper_positions.jsonl"))
    paper_exits = read_jsonl(rel("artifacts/paper_trading/paper_exits.jsonl"))
    joined_performances = read_jsonl(rel("artifacts/historical_market_data/alert_market_performance_4ch.jsonl"))

    analyzer = ChannelPerformanceAnalyzer(
        selected_channels=selected_channels,
        paper_positions=paper_positions,
        paper_exits=paper_exits,
        joined_performances=joined_performances,
    )
    performances = analyzer.analyze_alerts(calls)
    channel_summary = analyzer.summarize_channels(performances)
    hold_window_summary = build_hold_window_summary(analyzer, performances, selected_channels)
    rankings = analyzer.rankings(channel_summary)
    data_quality = analyzer.data_quality_report(calls, performances)

    write_jsonl(OUT_DIR / "token_performance.jsonl", [row.to_dict() for row in performances])
    write_json(
        OUT_DIR / "channel_summary.json",
        {
            "channels": {name: row.to_dict() for name, row in channel_summary.items()},
            **rankings,
        },
    )
    write_json(OUT_DIR / "hold_window_summary.json", hold_window_summary)
    write_json(OUT_DIR / "best_tokens.json", {"tokens": analyzer.best_tokens(performances)})
    write_json(OUT_DIR / "worst_tokens.json", {"tokens": analyzer.worst_tokens(performances)})
    write_json(OUT_DIR / "data_quality_report.json", data_quality)

    print(f"alerts_analyzed={len(performances)}")
    print(f"tokens_analyzed={len({token_key(row) for row in performances})}")
    print(f"price_sources={data_quality.get('price_sources', {})}")
    print(f"channel_performance_dir={OUT_DIR}")


def build_hold_window_summary(
    analyzer: ChannelPerformanceAnalyzer,
    performances: list[Any],
    selected_channels: list[str],
) -> dict[str, Any]:
    overall = analyzer.hold_window_summary(performances)
    per_channel = {}
    for channel in selected_channels:
        rows = [row for row in performances if row.channel_name == channel]
        per_channel[channel] = {name: stats.to_dict() for name, stats in analyzer.hold_window_summary(rows).items()}
    return {
        "overall": {name: stats.to_dict() for name, stats in overall.items()},
        "per_channel": per_channel,
    }


def token_key(row: Any) -> str:
    return str(row.mint_address or row.token_symbol or "UNKNOWN")


if __name__ == "__main__":
    main()
