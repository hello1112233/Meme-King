#!/usr/bin/env python3
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meme_king.deterministic import read_json, read_jsonl, rel, write_json, write_jsonl
from meme_king.paper_executor import PaperExecutor
from meme_king.replay_engine import sorted_calls


def main() -> None:
    calls = read_jsonl(rel("artifacts/normalized_calls.jsonl"))
    scorecard = read_json(rel("artifacts/channel_scorecard.json"), default={"channels": {}})
    executor = PaperExecutor()
    results = []
    orders = []
    positions = []
    fills = []
    exits = []

    for signal in sorted_calls(calls):
        result = executor.simulate_signal(signal)
        if not result:
            continue
        results.append(result)
        orders.extend(order.to_dict() for order in result["orders"])
        positions.append(result["position"].to_dict())
        fills.extend(fill.to_dict() for fill in result["fills"])
        exits.append(result["exit"].to_dict())

    out_dir = rel("artifacts/paper_trading")
    write_jsonl(out_dir / "paper_orders.jsonl", orders)
    write_jsonl(out_dir / "paper_positions.jsonl", positions)
    write_jsonl(out_dir / "paper_fills.jsonl", fills)
    write_jsonl(out_dir / "paper_exits.jsonl", exits)
    write_json(out_dir / "paper_summary.json", build_summary(calls, orders, positions, fills, exits, scorecard))
    print(f"paper_trades={len(orders) // 2}")
    print(f"paper_positions={len(positions)}")
    print(f"paper_summary={out_dir / 'paper_summary.json'}")


def build_summary(
    calls: list[dict[str, Any]],
    orders: list[dict[str, Any]],
    positions: list[dict[str, Any]],
    fills: list[dict[str, Any]],
    exits: list[dict[str, Any]],
    scorecard: dict[str, Any],
) -> dict[str, Any]:
    reason_counts = Counter(exit_row["reason"] for exit_row in exits)
    channel_counts = Counter(position["channel_name"] for position in positions)
    pnl_values = [float(exit_row["pnl_x"]) for exit_row in exits]
    winners = [value for value in pnl_values if value >= 1.0]
    return {
        "mode": "paper_trading_simulation_only",
        "live_trading": False,
        "wallets": False,
        "rpc_broadcast": False,
        "total_input_calls": len(calls),
        "paper_trades": len(positions),
        "paper_orders": len(orders),
        "paper_positions": len(positions),
        "paper_fills": len(fills),
        "paper_exits": len(exits),
        "exit_reasons": dict(sorted(reason_counts.items())),
        "per_channel_positions": dict(sorted(channel_counts.items())),
        "avg_pnl_x": round(mean(pnl_values), 6) if pnl_values else None,
        "winrate": round(len(winners) / len(pnl_values), 6) if pnl_values else None,
        "scorecard_channels_available": sorted((scorecard.get("channels") or {}).keys()),
    }


if __name__ == "__main__":
    main()

