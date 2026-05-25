"""Dry-run executor: plans trades without signing or sending.

Implements LiveExecutorInterface. Produces audit artifacts for review.
Never submits real transactions.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .deterministic import stable_hash, utc_now_iso
from .live_executor_interface import (
    ExecutionResult,
    LiveExecutorInterface,
    QuotePlan,
    TradeIntent,
    TransactionPlan,
)
from .live_trading_config import LiveTradingConfig, load_live_trading_config


class DryRunExecutor(LiveExecutorInterface):
    """Deterministic dry-run executor. No real transactions."""

    def __init__(self, config: LiveTradingConfig | None = None, out_dir: Path | None = None) -> None:
        super().__init__(config)
        self.out_dir = out_dir or Path("artifacts/live_trading_setup")
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._quote_count = 0
        self._plan_count = 0
        self._result_count = 0

    def build_quote_plan(self, intent: TradeIntent) -> QuotePlan:
        self._quote_count += 1
        quote_id = f"dry_quote_{self._quote_count}_{stable_hash(intent.to_dict())[:16]}"
        # Placeholder pricing derived deterministically from intent hash
        base = int(stable_hash(intent.signal_id)[:8], 16) / 0xFFFFFFFF
        expected_price = round(0.000001 + base * 0.001, 12)
        min_out = round(expected_price * intent.quantity_sol * 0.95, 12)

        quote = QuotePlan(
            intent=intent,
            quote_id=quote_id,
            expected_price=expected_price,
            minimum_out_amount=min_out,
            route="dry_run/jupiter_placeholder",
            valid_until=utc_now_iso(),
        )
        self._append_jsonl(self.out_dir / "dry_run_quotes.jsonl", quote.to_dict())
        return quote

    def build_transaction_plan(self, quote: QuotePlan) -> TransactionPlan:
        self._plan_count += 1
        plan_id = f"dry_plan_{self._plan_count}_{stable_hash(quote.quote_id)[:16]}"
        # Placeholder serialized tx: NOT a real transaction
        placeholder_tx = (
            "DRY_RUN_PLACEHOLDER_"
            + stable_hash({"quote_id": quote.quote_id, "plan_id": plan_id})[:48]
        )

        plan = TransactionPlan(
            quote=quote,
            plan_id=plan_id,
            serialized_transaction=placeholder_tx,
            signer_required=False,
            simulation_hash=stable_hash(quote.to_dict())[:32],
        )
        self._append_jsonl(self.out_dir / "dry_run_transaction_plans.jsonl", plan.to_dict())
        return plan

    def simulate_transaction(self, plan: TransactionPlan) -> ExecutionResult:
        # Deterministic simulation: succeed if hash is even, fail if odd
        hash_int = int(plan.simulation_hash[-1], 16)
        success = hash_int % 2 == 0

        result = ExecutionResult(
            plan_id=plan.plan_id,
            success=success,
            transaction_signature=None,
            error=None if success else "dry_run_simulated_failure",
            executed_at=utc_now_iso(),
            mode="dry_run",
        )
        self._append_jsonl(self.out_dir / "dry_run_results.jsonl", result.to_dict())
        return result

    def _submit_live(self, plan: TransactionPlan) -> ExecutionResult:
        # Dry run never submits live, but implements the abstract method
        raise RuntimeError("DryRunExecutor does not support live submission")

    def execute_intent(self, intent: TradeIntent) -> ExecutionResult:
        """Full dry-run pipeline for a single intent."""
        quote = self.build_quote_plan(intent)
        plan = self.build_transaction_plan(quote)
        return self.simulate_transaction(plan)

    def write_summary(self) -> dict[str, Any]:
        summary = {
            "mode": "dry_run_only",
            "live_trading": False,
            "wallets": False,
            "rpc_broadcast": False,
            "transaction_send": False,
            "timestamp_utc": utc_now_iso(),
            "quotes_planned": self._quote_count,
            "transactions_planned": self._plan_count,
            "simulations_run": self._result_count,
            "artifacts_dir": str(self.out_dir),
        }
        summary_path = self.out_dir / "dry_run_summary.json"
        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False, sort_keys=True)
            f.write("\n")
        return summary

    @staticmethod
    def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
