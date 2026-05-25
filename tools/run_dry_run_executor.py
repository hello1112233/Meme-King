#!/usr/bin/env python3
"""Run dry-run executor on approved Hermes trade skill signals.

Produces planned quotes, transaction plans, and simulated results.
No real transactions are sent.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meme_king.deterministic import read_jsonl, rel
from meme_king.dry_run_executor import DryRunExecutor
from meme_king.live_executor_interface import TradeIntent
from meme_king.live_trading_config import load_live_trading_config


def main() -> None:
    config = load_live_trading_config(rel("config/live_trading.env"))
    approved = read_jsonl(rel("artifacts/execution_gate/approved_paper_signals.jsonl"))
    rules = read_jsonl(rel("artifacts/hermes_trade_skill/accepted_setups.jsonl"))

    # Use accepted setups as the dry-run input (they already passed Hermes skill)
    inputs = rules if rules else approved[:50]

    executor = DryRunExecutor(config=config)

    for row in inputs:
        intent = build_intent(row, config)
        executor.execute_intent(intent)

    summary = executor.write_summary()
    print(f"dry_run_quotes={summary['quotes_planned']}")
    print(f"dry_run_transactions={summary['transactions_planned']}")
    print(f"dry_run_summary=artifacts/live_trading_setup/dry_run_summary.json")


def build_intent(row: dict[str, Any], config: Any) -> TradeIntent:
    return TradeIntent(
        signal_id=row.get("gate_decision_id") or row.get("message_id", "unknown"),
        channel_name=str(row.get("channel_name") or "UNKNOWN"),
        token_symbol=row.get("token_symbol"),
        mint_address=row.get("mint_address"),
        side="buy",
        quantity_sol=config.risk.max_position_sol,
        slippage_bps=config.risk.default_slippage_bps,
        priority_fee_microlamports=config.risk.priority_fee_microlamports,
        jito_tip_lamports=config.risk.jito_tip_lamports,
        reason="hermes_skill_approved",
    )


if __name__ == "__main__":
    main()
