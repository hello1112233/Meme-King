#!/usr/bin/env python3
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meme_king.deterministic import read_json, read_jsonl, rel, write_json
from meme_king.hermes_trade_skill import EntryRule, ExitRule, HermesTradeSkill
from meme_king.paper_metrics import compute_channel_performance, compute_exit_reason_stats, summarize_trades


def main() -> None:
    rules = read_json(rel("artifacts/hermes_trade_skill/skill_rules.json"), default={})
    accepted = read_jsonl(rel("artifacts/hermes_trade_skill/accepted_setups.jsonl"))
    skill = load_skill(rules)
    trades = []
    exit_counts = Counter()
    for row in accepted:
        entry_decision = skill.decide_entry(row)
        if entry_decision.decision != "ENTER_PAPER":
            continue
        current_x = 1.0 + float(row.get("pnl_units") or 0.0)
        exit_decision = skill.decide_exit(
            {
                **row,
                "current_x": current_x,
                "hold_seconds": skill.exit_rule.max_hold_seconds,
            }
        )
        exit_counts[exit_decision.decision] += 1
        trades.append(
            {
                "signal_id": row.get("skill_decision_id"),
                "channel_name": row.get("channel_name"),
                "token_symbol": row.get("token_symbol"),
                "mint_address": row.get("mint_address"),
                "pnl_units": float(row.get("pnl_units") or 0.0),
                "pnl_x": current_x,
                "exit_reason": exit_decision.decision,
            }
        )

    out_dir = rel("artifacts/hermes_trade_skill")
    write_json(out_dir / "backtest_summary.json", summarize_trades(trades) | {"target_winrate": 0.8, "target_reached": summarize_trades(trades)["winrate"] >= 0.8 and len(trades) >= 25})
    write_json(out_dir / "channel_breakdown.json", compute_channel_performance(trades))
    write_json(out_dir / "exit_breakdown.json", compute_exit_reason_stats(trades) | {"decision_counts": dict(sorted(exit_counts.items()))})
    print(f"backtest_summary={out_dir / 'backtest_summary.json'}")


def load_skill(rules: dict) -> HermesTradeSkill:
    entry = rules.get("entry_rule") or {}
    exit_rule = rules.get("exit_rule") or {}
    return HermesTradeSkill(
        EntryRule(
            min_confidence=float(entry.get("min_confidence", 0.0)),
            allowed_channels=list(entry.get("allowed_channels", [])),
            max_signal_age=int(entry.get("max_signal_age", 999999999)),
            strategy_profile=str(entry.get("strategy_profile", "balanced")),
            cooldown_seconds=int(entry.get("cooldown_seconds", 0)),
            duplicate_window_seconds=int(entry.get("duplicate_window_seconds", 0)),
            min_channel_winrate=float(entry.get("min_channel_winrate", 0.0)),
            min_channel_trades=int(entry.get("min_channel_trades", 25)),
        ),
        ExitRule(
            stop_loss_pct=float(exit_rule.get("stop_loss_pct", 0.3)),
            take_profit_pct=float(exit_rule.get("take_profit_pct", 0.5)),
            max_hold_seconds=int(exit_rule.get("max_hold_seconds", 7200)),
        ),
    )


if __name__ == "__main__":
    main()

