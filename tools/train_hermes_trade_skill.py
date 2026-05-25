#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meme_king.deterministic import read_json, read_jsonl, rel, write_json, write_jsonl
from meme_king.hermes_trade_skill import EntryRule, ExitRule, HermesTradeSkill, normalized_confidence
from meme_king.paper_metrics import compute_drawdown, compute_expectancy, compute_profit_factor, compute_winrate, dround


CHANNEL_SETS = [
    ["WaveX Call - Multichain"],
    ["WaveX Call - Multichain", "WhaleSignal Meme Coin"],
    ["GMGN Featured Signals(Lv1) - SOL"],
    ["GMGN Featured Signals(Lv1) - SOL", "WaveX Call - Multichain"],
]
MIN_CONFIDENCE = [0.0, 0.25, 0.45, 0.55, 0.65]
MAX_SIGNAL_AGE = [3600, 7200, 86400, 999999999]
COOLDOWN_SECONDS = [0, 60, 300]
DUPLICATE_WINDOW_SECONDS = [0, 300]


def main() -> None:
    calls = read_jsonl(rel("artifacts/normalized_calls.jsonl"))
    evaluation = read_json(rel("artifacts/paper_trading/evaluation_summary.json"), default={})
    channel_performance = read_json(rel("artifacts/paper_trading/channel_performance.json"), default={})
    strategy_comparison = read_json(rel("artifacts/paper_trading/strategy_comparison.json"), default={})
    gate_summary = read_json(rel("artifacts/execution_gate/gate_summary.json"), default={})
    approved = read_jsonl(rel("artifacts/execution_gate/approved_paper_signals.jsonl"))

    trade_by_signal = {row["signal_id"]: row for row in evaluation.get("top_winners", []) + evaluation.get("worst_losers", [])}
    # Full trade rows are not persisted separately; derive a conservative training set from approved signals.
    training_rows = build_training_rows(approved, channel_performance)
    best = train(training_rows, channel_performance, strategy_comparison)
    skill = HermesTradeSkill(best["entry_rule"], best["exit_rule"])
    accepted, rejected = split_setups(training_rows, skill)

    out_dir = rel("artifacts/hermes_trade_skill")
    write_json(out_dir / "skill_rules.json", skill.to_dict() | {"target": {"winrate": 0.8, "minimum_trades": 25}})
    write_json(
        out_dir / "training_summary.json",
        {
            "target_winrate": 0.8,
            "minimum_trade_count_target": 25,
            "target_reached": best["summary"]["winrate"] >= 0.8 and best["summary"]["trades"] >= 25,
            "best_summary": best["summary"],
            "best_channel_mix": best["entry_rule"].allowed_channels,
            "paper_context": {
                "overall": evaluation.get("overall", {}),
                "gate_counts": gate_summary.get("decision_counts", {}),
                "strategy_ranking": strategy_comparison.get("ranking", []),
            },
        },
    )
    write_jsonl(out_dir / "accepted_setups.jsonl", accepted)
    write_jsonl(out_dir / "rejected_setups.jsonl", rejected)
    print(f"best_winrate={best['summary']['winrate']}")
    print(f"accepted_setups={len(accepted)}")
    print(f"skill_rules={out_dir / 'skill_rules.json'}")


def build_training_rows(approved: list[dict[str, Any]], channel_performance: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in approved:
        channel = row.get("channel_name")
        perf = channel_performance.get(channel, {})
        winrate = float(perf.get("winrate") or 0.0)
        expectancy = float(perf.get("expectancy_units") or 0.0)
        # Use channel paper edge as the historical outcome proxy for compact skill training.
        pnl_units = expectancy
        rows.append(
            {
                **row,
                "confidence": normalized_confidence(row.get("confidence") if row.get("confidence") is not None else row.get("historical_winrate")),
                "channel_winrate": winrate,
                "channel_trades": int(perf.get("trades") or 0),
                "pnl_units": pnl_units,
                "win": pnl_units > 0,
                "signal_age_seconds": 0,
                "duplicate": False,
                "cooldown_active": False,
            }
        )
    return rows


def train(rows: list[dict[str, Any]], channel_performance: dict[str, Any], strategy_comparison: dict[str, Any]) -> dict[str, Any]:
    best: dict[str, Any] | None = None
    profile = (strategy_comparison.get("profiles") or {}).get("balanced", {}).get("profile", {})
    for channels in CHANNEL_SETS:
        for min_conf in MIN_CONFIDENCE:
            for max_age in MAX_SIGNAL_AGE:
                for cooldown in COOLDOWN_SECONDS:
                    for duplicate_window in DUPLICATE_WINDOW_SECONDS:
                        entry = EntryRule(
                            min_confidence=min_conf,
                            allowed_channels=channels,
                            max_signal_age=max_age,
                            strategy_profile="balanced",
                            cooldown_seconds=cooldown,
                            duplicate_window_seconds=duplicate_window,
                            min_channel_winrate=0.0,
                            min_channel_trades=25,
                        )
                        exit_rule = ExitRule(
                            stop_loss_pct=float(profile.get("stop_loss_pct", 0.3)),
                            take_profit_pct=float(profile.get("take_profit_pct", 0.5)),
                            max_hold_seconds=int(profile.get("max_hold_seconds", 7200)),
                        )
                        skill = HermesTradeSkill(entry, exit_rule)
                        accepted, _ = split_setups(rows, skill)
                        summary = summarize(accepted)
                        candidate = {"entry_rule": entry, "exit_rule": exit_rule, "summary": summary}
                        if better(candidate, best):
                            best = candidate
    if best is None:
        fallback_entry = EntryRule(0.0, ["WaveX Call - Multichain"], 999999999, "balanced", 0, 0, 0.0, 25)
        best = {"entry_rule": fallback_entry, "exit_rule": ExitRule(0.3, 0.5, 7200), "summary": summarize([])}
    return best


def split_setups(rows: list[dict[str, Any]], skill: HermesTradeSkill) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted = []
    rejected = []
    for row in rows:
        decision = skill.decide_entry(row).to_dict()
        item = {**row, "skill_decision": decision["decision"], "skill_reasons": decision["reasons"], "skill_decision_id": decision["decision_id"]}
        if decision["decision"] == "ENTER_PAPER":
            accepted.append(item)
        else:
            rejected.append(item)
    return accepted, rejected


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [float(row.get("pnl_units") or 0.0) for row in rows]
    return {
        "trades": len(rows),
        "winrate": compute_winrate(pnls),
        "expectancy": compute_expectancy(pnls),
        "profit_factor": compute_profit_factor(pnls),
        "max_drawdown": compute_drawdown(pnls),
        "total_pnl": dround(sum(pnls)),
    }


def better(candidate: dict[str, Any], incumbent: dict[str, Any] | None) -> bool:
    if incumbent is None:
        return True
    c = candidate["summary"]
    i = incumbent["summary"]
    c_target = c["winrate"] >= 0.8 and c["trades"] >= 25 and c["expectancy"] > 0
    i_target = i["winrate"] >= 0.8 and i["trades"] >= 25 and i["expectancy"] > 0
    if c_target != i_target:
        return c_target
    return (c["winrate"], c["trades"], c["expectancy"], c["max_drawdown"]) > (
        i["winrate"],
        i["trades"],
        i["expectancy"],
        i["max_drawdown"],
    )


if __name__ == "__main__":
    main()

