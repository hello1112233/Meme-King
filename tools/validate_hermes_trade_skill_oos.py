#!/usr/bin/env python3
"""Deterministic out-of-sample validation for Hermes trade skill.

Performs six anti-overfit checks:
1. Minimum accepted setups count
2. Minimum unique token count
3. Minimum day coverage (from full normalized_calls source)
4. Time-split winrate (chronological 70/30)
5. Channel concentration (no single channel > 95%)
6. Duplicate-token collapse winrate
7. Shuffled-order replay consistency

Reads skill_rules.json, accepted_setups.jsonl, normalized_calls.jsonl.
Writes oos_validation.json.
"""
from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meme_king.deterministic import read_json, read_jsonl, rel, stable_hash, write_json
from meme_king.hermes_trade_skill import EntryRule, ExitRule, HermesTradeSkill

# Pass thresholds
THRESHOLD_ACCEPTED_SETUPS = 100
THRESHOLD_UNIQUE_TOKENS = 50
THRESHOLD_DAY_COVERAGE = 7
THRESHOLD_TIME_SPLIT_WINRATE = 0.80
THRESHOLD_CHANNEL_CONCENTRATION = 0.95
THRESHOLD_DUPLICATE_COLLAPSE_WINRATE = 0.80


def load_skill(path: Path) -> HermesTradeSkill:
    data = read_json(path, default={})
    entry = data.get("entry_rule", {})
    exit_r = data.get("exit_rule", {})
    return HermesTradeSkill(
        EntryRule(
            min_confidence=float(entry.get("min_confidence", 0.0)),
            allowed_channels=list(entry.get("allowed_channels", [])),
            max_signal_age=int(entry.get("max_signal_age", 3600)),
            strategy_profile=str(entry.get("strategy_profile", "balanced")),
            cooldown_seconds=int(entry.get("cooldown_seconds", 0)),
            duplicate_window_seconds=int(entry.get("duplicate_window_seconds", 0)),
            min_channel_winrate=float(entry.get("min_channel_winrate", 0.0)),
            min_channel_trades=int(entry.get("min_channel_trades", 25)),
        ),
        ExitRule(
            stop_loss_pct=float(exit_r.get("stop_loss_pct", 0.3)),
            take_profit_pct=float(exit_r.get("take_profit_pct", 0.5)),
            max_hold_seconds=int(exit_r.get("max_hold_seconds", 7200)),
        ),
    )


def token_key(row: dict[str, Any]) -> str:
    return str(row.get("token_symbol") or row.get("mint_address") or row.get("message_id") or "")


def parse_date(created_at: str | None) -> str:
    if not created_at:
        return ""
    return str(created_at)[:10]


def compute_winrate_bool(wins: list[bool]) -> float:
    if not wins:
        return 0.0
    return round(sum(1 for w in wins if w) / len(wins), 6)


def check_time_split(rows: list[dict[str, Any]]) -> dict[str, Any]:
    sorted_rows = sorted(rows, key=lambda r: str(r.get("created_at") or ""))
    split_idx = int(len(sorted_rows) * 0.7)
    test_set = sorted_rows[split_idx:]
    wins = [bool(r.get("win")) for r in test_set]
    winrate = compute_winrate_bool(wins)
    return {
        "train_count": split_idx,
        "test_count": len(test_set),
        "test_winrate": winrate,
        "passed": winrate >= THRESHOLD_TIME_SPLIT_WINRATE and len(test_set) > 0,
    }


def check_channel_holdout(rows: list[dict[str, Any]]) -> dict[str, Any]:
    channels = Counter(str(r.get("channel_name") or "unknown") for r in rows)
    total = len(rows)
    max_share = max((c / total for c in channels.values()), default=0.0) if total else 0.0
    top_channel, top_count = channels.most_common(1)[0] if channels else ("", 0)
    return {
        "channel_counts": dict(channels),
        "largest_channel": top_channel,
        "largest_share": round(max_share, 6),
        "passed": max_share <= THRESHOLD_CHANNEL_CONCENTRATION,
    }


def check_duplicate_collapse(rows: list[dict[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    collapsed: list[dict[str, Any]] = []
    for row in rows:
        key = token_key(row)
        if key and key not in seen:
            seen.add(key)
            collapsed.append(row)
    wins = [bool(r.get("win")) for r in collapsed]
    winrate = compute_winrate_bool(wins)
    return {
        "original_count": len(rows),
        "collapsed_count": len(collapsed),
        "collapsed_winrate": winrate,
        "passed": winrate >= THRESHOLD_DUPLICATE_COLLAPSE_WINRATE,
    }


def check_shuffled_replay(rows: list[dict[str, Any]], skill: HermesTradeSkill) -> dict[str, Any]:
    seed = int(stable_hash(skill.to_dict())[:16], 16)
    # Deterministic Fisher-Yates shuffle using the seed
    shuffled = list(rows)
    n = len(shuffled)
    state = seed
    for i in range(n - 1, 0, -1):
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        j = state % (i + 1)
        shuffled[i], shuffled[j] = shuffled[j], shuffled[i]

    accepted: list[dict[str, Any]] = []
    for row in shuffled:
        decision = skill.decide_entry(row)
        if decision.decision == "ENTER_PAPER":
            accepted.append(row)

    original_wins = [bool(r.get("win")) for r in rows]
    replay_wins = [bool(r.get("win")) for r in accepted]
    original_winrate = compute_winrate_bool(original_wins)
    replay_winrate = compute_winrate_bool(replay_wins)
    return {
        "original_count": len(rows),
        "replay_count": len(accepted),
        "original_winrate": original_winrate,
        "replay_winrate": replay_winrate,
        "count_match": len(rows) == len(accepted),
        "passed": len(rows) == len(accepted),
    }


def check_day_coverage(calls: list[dict[str, Any]]) -> dict[str, Any]:
    dates = {parse_date(r.get("created_at")) for r in calls}
    dates.discard("")
    return {
        "day_coverage": len(dates),
        "passed": len(dates) >= THRESHOLD_DAY_COVERAGE,
    }


def main() -> None:
    skill = load_skill(rel("artifacts/hermes_trade_skill/skill_rules.json"))
    accepted = read_jsonl(rel("artifacts/hermes_trade_skill/accepted_setups.jsonl"))
    calls = read_jsonl(rel("artifacts/normalized_calls.jsonl"))

    # 1. Accepted setups count
    accepted_count = len(accepted)
    passed_accepted = accepted_count >= THRESHOLD_ACCEPTED_SETUPS

    # 2. Unique tokens
    unique_tokens = len({token_key(r) for r in accepted if token_key(r)})
    passed_unique = unique_tokens >= THRESHOLD_UNIQUE_TOKENS

    # 3. Day coverage (from full source calls)
    day_result = check_day_coverage(calls)

    # 4. Time split
    time_split = check_time_split(accepted)

    # 5. Channel holdout / concentration
    channel_result = check_channel_holdout(accepted)

    # 6. Duplicate-token collapse
    dup_result = check_duplicate_collapse(accepted)

    # 7. Shuffled-order replay
    shuffle_result = check_shuffled_replay(accepted, skill)

    all_passed = (
        passed_accepted
        and passed_unique
        and day_result["passed"]
        and time_split["passed"]
        and channel_result["passed"]
        and dup_result["passed"]
        and shuffle_result["passed"]
    )

    report: dict[str, Any] = {
        "oos_pass": all_passed,
        "ready_for_micro_live": all_passed,
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "thresholds": {
            "accepted_setups": THRESHOLD_ACCEPTED_SETUPS,
            "unique_tokens": THRESHOLD_UNIQUE_TOKENS,
            "day_coverage": THRESHOLD_DAY_COVERAGE,
            "time_split_winrate": THRESHOLD_TIME_SPLIT_WINRATE,
            "channel_concentration": THRESHOLD_CHANNEL_CONCENTRATION,
            "duplicate_collapse_winrate": THRESHOLD_DUPLICATE_COLLAPSE_WINRATE,
        },
        "results": {
            "accepted_setups": {"value": accepted_count, "passed": passed_accepted},
            "unique_tokens": {"value": unique_tokens, "passed": passed_unique},
            "day_coverage": day_result,
            "time_split": time_split,
            "channel_concentration": channel_result,
            "duplicate_collapse": dup_result,
            "shuffled_replay": shuffle_result,
        },
    }

    out_path = rel("artifacts/hermes_trade_skill/oos_validation.json")
    write_json(out_path, report)

    # Console report
    print("=" * 50)
    print("HERMES TRADE SKILL — OOS VALIDATION REPORT")
    print("=" * 50)
    print(f"OOS pass/fail:     {'PASS' if all_passed else 'FAIL'}")
    print(f"Accepted setups:   {accepted_count}  ({'PASS' if passed_accepted else 'FAIL'})")
    print(f"Unique tokens:     {unique_tokens}  ({'PASS' if passed_unique else 'FAIL'})")
    print(f"Day coverage:      {day_result['day_coverage']}  ({'PASS' if day_result['passed'] else 'FAIL'})")
    print(f"Time-split WR:     {time_split.get('test_winrate', 0.0):.4f}  ({'PASS' if time_split['passed'] else 'FAIL'})")
    print(f"Top channel share: {channel_result.get('largest_share', 0.0):.4f}  ({'PASS' if channel_result['passed'] else 'FAIL'})")
    print(f"Dup-collapse WR:   {dup_result.get('collapsed_winrate', 0.0):.4f}  ({'PASS' if dup_result['passed'] else 'FAIL'})")
    print(f"Shuffle replay:    count_match={shuffle_result['count_match']}  ({'PASS' if shuffle_result['passed'] else 'FAIL'})")
    print(f"Ready for micro live: {'YES' if all_passed else 'NO'}")
    print("=" * 50)


if __name__ == "__main__":
    main()
