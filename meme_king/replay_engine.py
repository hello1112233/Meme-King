from __future__ import annotations

from collections import Counter, defaultdict
from statistics import median
from typing import Any


def sorted_calls(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(calls, key=lambda row: (row.get("timestamp") or "", row.get("channel_name") or "", str(row.get("message_id") or "")))


def replay(calls: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted_calls([row for row in calls if row.get("replayable")])
    channel_counts = Counter(row["channel_name"] for row in ordered)
    token_counts = Counter((row.get("token_symbol") or row.get("mint_address") or "UNKNOWN") for row in ordered)
    timeline = []
    for index, row in enumerate(ordered, start=1):
        token = row.get("token_symbol") or row.get("mint_address") or "UNKNOWN"
        timeline.append(
            {
                "replay_index": index,
                "timestamp": row.get("timestamp"),
                "channel_name": row.get("channel_name"),
                "token": token,
                "confidence": row.get("confidence"),
                "historical_max_x": row.get("historical_max_x"),
                "source_file": row.get("source_file"),
            }
        )
    return {
        "total_calls": len(calls),
        "replayable_calls": len(ordered),
        "channel_counts": dict(sorted(channel_counts.items())),
        "top_tokens": token_counts.most_common(25),
        "timeline": timeline,
    }


def channel_statistics(calls: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in calls:
        grouped[row["channel_name"]].append(row)
    stats = {}
    for channel, rows in sorted(grouped.items()):
        max_values = [float(row["historical_max_x"]) for row in rows if isinstance(row.get("historical_max_x"), (int, float))]
        confidences = [float(row["confidence"]) for row in rows if isinstance(row.get("confidence"), (int, float))]
        tokens = [row.get("token_symbol") or row.get("mint_address") or "UNKNOWN" for row in rows]
        stats[channel] = {
            "records": len(rows),
            "replayable": sum(1 for row in rows if row.get("replayable")),
            "unique_tokens": len(set(tokens)),
            "median_confidence": median(confidences) if confidences else None,
            "median_max_x": median(max_values) if max_values else None,
            "best_max_x": max(max_values) if max_values else None,
            "winrate_at_1_5x": sum(1 for value in max_values if value >= 1.5) / len(max_values) if max_values else None,
        }
    return stats


def channel_rankings(stats: dict[str, Any]) -> list[dict[str, Any]]:
    rankings = []
    for channel, row in stats.items():
        score = (
            (row.get("winrate_at_1_5x") or 0) * 40
            + min(row.get("records") or 0, 100) / 100 * 20
            + min(row.get("unique_tokens") or 0, 100) / 100 * 10
            + min(row.get("median_confidence") or 0, 1) * 20
            + min(row.get("best_max_x") or 0, 20) / 20 * 10
        )
        rankings.append({"channel_name": channel, "confidence_ranking": round(score, 4), **row})
    return sorted(rankings, key=lambda row: (-row["confidence_ranking"], row["channel_name"]))

