#!/usr/bin/env python3
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meme_king.deterministic import read_json, read_jsonl, rel, write_json, write_jsonl
from meme_king.execution_gate import ExecutionGate, GateDecision
from meme_king.replay_engine import sorted_calls


def main() -> None:
    calls = read_jsonl(rel("artifacts/normalized_calls.jsonl"))
    scorecard = read_json(rel("artifacts/channel_scorecard.json"), default={"channels": {}})
    strategy_comparison = read_json(rel("artifacts/paper_trading/strategy_comparison.json"), default={})
    gate = ExecutionGate(scorecard=scorecard, strategy_comparison=strategy_comparison)

    decisions = []
    approved = []
    blocked = []
    for index, signal in enumerate(sorted_calls(calls), start=1):
        review = gate.review(signal, replay_index=index).to_dict()
        decisions.append(review)
        if review["decision"] == GateDecision.APPROVE_FOR_PAPER.value:
            approved.append({**signal, "gate_decision_id": review["decision_id"], "gate_reasons": review["reasons"]})
        elif review["decision"] == GateDecision.BLOCK_FOR_RISK.value:
            blocked.append({**signal, "gate_decision_id": review["decision_id"], "gate_reasons": review["reasons"]})

    out_dir = rel("artifacts/execution_gate")
    write_jsonl(out_dir / "gate_decisions.jsonl", decisions)
    write_jsonl(out_dir / "blocked_signals.jsonl", blocked)
    write_jsonl(out_dir / "approved_paper_signals.jsonl", approved)
    write_json(out_dir / "gate_summary.json", build_summary(decisions))

    print(f"gate_decisions={len(decisions)}")
    print(f"approved={len(approved)}")
    print(f"blocked={len(blocked)}")
    print(f"gate_summary={out_dir / 'gate_summary.json'}")


def build_summary(decisions: list[dict]) -> dict:
    decision_counts = Counter(row["decision"] for row in decisions)
    reason_counts = Counter(reason for row in decisions for reason in row.get("reasons", []))
    channel_counts: dict[str, Counter] = defaultdict(Counter)
    duplicate_cooldown = Counter()
    suspicious_examples = []
    for row in decisions:
        channel_counts[str(row.get("channel_name") or "UNKNOWN")][row["decision"]] += 1
        reasons = set(row.get("reasons", []))
        if "DUPLICATE_SIGNAL" in reasons:
            duplicate_cooldown["duplicate"] += 1
        if "COOLDOWN_ACTIVE" in reasons:
            duplicate_cooldown["cooldown"] += 1
        if "SUSPICIOUS_TEXT" in reasons and len(suspicious_examples) < 25:
            suspicious_examples.append(row)

    channel_approval_rates = {}
    for channel, counts in sorted(channel_counts.items()):
        total = sum(counts.values())
        channel_approval_rates[channel] = {
            "total": total,
            "approved": counts.get(GateDecision.APPROVE_FOR_PAPER.value, 0),
            "blocked": counts.get(GateDecision.BLOCK_FOR_RISK.value, 0),
            "watch_only": counts.get(GateDecision.WATCH_ONLY.value, 0),
            "needs_more_data": counts.get(GateDecision.NEEDS_MORE_DATA.value, 0),
            "approval_rate": round(counts.get(GateDecision.APPROVE_FOR_PAPER.value, 0) / total, 6) if total else 0.0,
        }

    return {
        "mode": "paper_execution_gate_only",
        "live_trading": False,
        "wallets": False,
        "rpc_broadcast": False,
        "reference_profile": "balanced",
        "total_decisions": len(decisions),
        "decision_counts": dict(sorted(decision_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
        "top_block_reasons": reason_counts.most_common(20),
        "channel_approval_rates": channel_approval_rates,
        "duplicate_cooldown_counts": dict(sorted(duplicate_cooldown.items())),
        "suspicious_signal_examples": suspicious_examples,
    }


if __name__ == "__main__":
    main()

