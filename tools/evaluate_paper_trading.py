#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meme_king.deterministic import read_json, read_jsonl, rel, write_json
from meme_king.paper_executor import PaperExecutor
from meme_king.paper_metrics import (
    compute_channel_performance,
    compute_exit_reason_stats,
    compute_pnl,
    dround,
    summarize_trades,
)
from meme_king.replay_engine import sorted_calls
from meme_king.strategy_profiles import StrategyProfile, all_profiles


def main() -> None:
    paper_summary = read_json(rel("artifacts/paper_trading/paper_summary.json"), default={})
    positions = read_jsonl(rel("artifacts/paper_trading/paper_positions.jsonl"))
    fills = read_jsonl(rel("artifacts/paper_trading/paper_fills.jsonl"))
    normalized_calls = read_jsonl(rel("artifacts/normalized_calls.jsonl"))

    trades = join_paper_trades(positions, fills)
    evaluation = {
        "mode": "paper_trading_evaluation_only",
        "live_trading": False,
        "wallets": False,
        "rpc_broadcast": False,
        "source_summary": paper_summary,
        "overall": summarize_trades(trades),
        "top_winners": sorted(trades, key=lambda row: (-row["pnl_units"], row["signal_id"]))[:25],
        "worst_losers": sorted(trades, key=lambda row: (row["pnl_units"], row["signal_id"]))[:25],
    }
    channel_performance = compute_channel_performance(trades)
    exit_reason_stats = compute_exit_reason_stats(trades)
    strategy_comparison = compare_strategies(normalized_calls)

    out_dir = rel("artifacts/paper_trading")
    write_json(out_dir / "evaluation_summary.json", evaluation)
    write_json(out_dir / "channel_performance.json", channel_performance)
    write_json(out_dir / "exit_reason_stats.json", exit_reason_stats)
    write_json(out_dir / "strategy_comparison.json", strategy_comparison)

    print(f"evaluation_summary={out_dir / 'evaluation_summary.json'}")
    print(f"strategy_comparison={out_dir / 'strategy_comparison.json'}")


def join_paper_trades(positions: list[dict[str, Any]], fills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    exit_fills = {row["signal_id"]: row for row in fills if row.get("side") == "exit"}
    trades = []
    for position in positions:
        exit_fill = exit_fills.get(position.get("signal_id"))
        if not exit_fill:
            continue
        pnl = compute_pnl(
            entry_price=float(position.get("entry_price") or 1.0),
            exit_price=float(exit_fill.get("fill_price") or 0.0),
            quantity=float(position.get("quantity") or 1.0),
        )
        trades.append(
            {
                "signal_id": position.get("signal_id"),
                "position_id": position.get("position_id"),
                "channel_name": position.get("channel_name"),
                "token_symbol": position.get("token_symbol"),
                "mint_address": position.get("mint_address"),
                "quantity": float(position.get("quantity") or 1.0),
                "entry_price": float(position.get("entry_price") or 1.0),
                "exit_price": float(exit_fill.get("fill_price") or 0.0),
                "exit_step": int(exit_fill.get("fill_step") or 0),
                "exit_reason": exit_fill.get("reason"),
                "pnl_units": pnl["gross_pnl_units"],
                "pnl_x": pnl["pnl_x"],
                "pnl_pct": pnl["pnl_pct"],
            }
        )
    return sorted(trades, key=lambda row: (str(row["channel_name"]), str(row["signal_id"])))


def compare_strategies(calls: list[dict[str, Any]]) -> dict[str, Any]:
    comparison = {}
    ordered_calls = sorted_calls(calls)
    for profile in all_profiles():
        trades = simulate_profile(ordered_calls, profile)
        summary = summarize_trades(trades)
        comparison[profile.name] = {
            "profile": profile.to_dict(),
            "summary": summary,
            "exit_reason_stats": compute_exit_reason_stats(trades),
            "channel_performance": compute_channel_performance(trades),
        }
    ranked = sorted(
        (
            {
                "profile": name,
                **row["summary"],
            }
            for name, row in comparison.items()
        ),
        key=lambda row: (
            -(row.get("expectancy_units") or 0.0),
            -(row.get("profit_factor") or 0.0 if row.get("profit_factor") != float("inf") else 999999.0),
            row["profile"],
        ),
    )
    return {
        "mode": "paper_strategy_comparison_only",
        "live_trading": False,
        "profiles": comparison,
        "ranking": ranked,
    }


def simulate_profile(calls: list[dict[str, Any]], profile: StrategyProfile) -> list[dict[str, Any]]:
    executor = PaperExecutor(
        take_profit_x=profile.take_profit_x,
        stop_loss_x=profile.stop_loss_x,
        max_hold_steps=profile.max_hold_steps,
        base_quantity=profile.position_size_units,
    )
    trades = []
    for signal in calls:
        if normalized_confidence(signal) < profile.min_confidence:
            continue
        result = executor.simulate_signal(signal)
        if not result:
            continue
        position = result["position"].to_dict()
        exit_record = result["exit"].to_dict()
        slippage_cost = profile.slippage_bps_simulated / 10000.0 * profile.position_size_units * 2
        pnl_units = (float(exit_record["pnl_x"]) - 1.0) * profile.position_size_units - slippage_cost
        trades.append(
            {
                "signal_id": position["signal_id"],
                "channel_name": position["channel_name"],
                "token_symbol": position.get("token_symbol"),
                "mint_address": position.get("mint_address"),
                "quantity": profile.position_size_units,
                "entry_price": 1.0,
                "exit_price": dround(float(exit_record["pnl_x"])),
                "exit_step": exit_record["exit_step"],
                "exit_reason": exit_record["reason"],
                "pnl_units": dround(pnl_units),
                "pnl_x": dround(1.0 + pnl_units / profile.position_size_units if profile.position_size_units else 0.0),
                "pnl_pct": dround((pnl_units / profile.position_size_units) * 100.0 if profile.position_size_units else 0.0),
            }
        )
    return sorted(trades, key=lambda row: (str(row["channel_name"]), str(row["signal_id"])))


def normalized_confidence(signal: dict[str, Any]) -> float:
    for key in ("confidence", "historical_score", "historical_winrate"):
        value = signal.get(key)
        if isinstance(value, (int, float)):
            return float(value) / 100.0 if float(value) > 1 else float(value)
    return 0.5


if __name__ == "__main__":
    main()

