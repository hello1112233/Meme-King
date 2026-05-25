from __future__ import annotations

from collections import Counter, defaultdict
from statistics import median
from typing import Any


def build_scorecard(calls: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in calls:
        grouped[row["channel_name"]].append(row)

    channels = {}
    for channel, rows in sorted(grouped.items()):
        max_values = [float(row["historical_max_x"]) for row in rows if isinstance(row.get("historical_max_x"), (int, float))]
        timestamps = sorted(row.get("timestamp") for row in rows if row.get("timestamp"))
        tokens = [row.get("token_symbol") or row.get("mint_address") or "UNKNOWN" for row in rows]
        token_counts = Counter(tokens)
        clusters = cluster_rows(rows)
        channels[channel] = {
            "winrate": round(sum(1 for value in max_values if value >= 1.5) / len(max_values), 4) if max_values else None,
            "median_survival": None,
            "best_multipliers": sorted(max_values, reverse=True)[:10],
            "replay_frequency": len(rows),
            "signal_clustering": clusters,
            "timing_quality": timing_quality(timestamps),
            "token_recurrence": token_counts.most_common(10),
            "confidence_ranking": confidence_ranking(rows, max_values, clusters),
        }
    return {"channels": channels}


def cluster_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_token = Counter(row.get("token_symbol") or row.get("mint_address") or "UNKNOWN" for row in rows)
    repeated = {token: count for token, count in by_token.items() if count > 1 and token != "UNKNOWN"}
    return {
        "repeated_token_clusters": repeated,
        "cluster_count": len(repeated),
        "largest_cluster": max(repeated.values()) if repeated else 0,
    }


def timing_quality(timestamps: list[str]) -> dict[str, Any]:
    if not timestamps:
        return {"coverage": "none", "observations": 0}
    days = {value[:10] for value in timestamps if len(value) >= 10}
    return {
        "coverage": "multi_day" if len(days) > 1 else "single_day",
        "observations": len(timestamps),
        "active_days": len(days),
        "first_seen": timestamps[0],
        "last_seen": timestamps[-1],
    }


def confidence_ranking(rows: list[dict[str, Any]], max_values: list[float], clusters: dict[str, Any]) -> float:
    confidence_values = [float(row["confidence"]) for row in rows if isinstance(row.get("confidence"), (int, float))]
    winrate = sum(1 for value in max_values if value >= 1.5) / len(max_values) if max_values else 0
    median_confidence = median(confidence_values) if confidence_values else 0
    recurrence_penalty = min(clusters.get("largest_cluster") or 0, 10) * 0.01
    score = winrate * 0.45 + median_confidence * 0.35 + min(len(rows), 100) / 100 * 0.2 - recurrence_penalty
    return round(max(score, 0), 4)

