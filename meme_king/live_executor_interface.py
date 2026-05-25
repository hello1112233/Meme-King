"""Abstract interfaces for live execution.

No real trading logic lives here. submit_transaction() raises RuntimeError
unless transaction sending is explicitly enabled.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from .live_trading_config import ExecutionFlags, LiveTradingConfig, load_live_trading_config


@dataclass(frozen=True)
class TradeIntent:
    signal_id: str
    channel_name: str
    token_symbol: str | None
    mint_address: str | None
    side: str  # "buy" or "sell"
    quantity_sol: float
    slippage_bps: int
    priority_fee_microlamports: int
    jito_tip_lamports: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "channel_name": self.channel_name,
            "token_symbol": self.token_symbol,
            "mint_address": self.mint_address,
            "side": self.side,
            "quantity_sol": self.quantity_sol,
            "slippage_bps": self.slippage_bps,
            "priority_fee_microlamports": self.priority_fee_microlamports,
            "jito_tip_lamports": self.jito_tip_lamports,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class QuotePlan:
    intent: TradeIntent
    quote_id: str
    expected_price: float
    minimum_out_amount: float
    route: str
    valid_until: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent.to_dict(),
            "quote_id": self.quote_id,
            "expected_price": self.expected_price,
            "minimum_out_amount": self.minimum_out_amount,
            "route": self.route,
            "valid_until": self.valid_until,
        }


@dataclass(frozen=True)
class TransactionPlan:
    quote: QuotePlan
    plan_id: str
    serialized_transaction: str
    signer_required: bool
    simulation_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "quote": self.quote.to_dict(),
            "plan_id": self.plan_id,
            "serialized_transaction": self.serialized_transaction,
            "signer_required": self.signer_required,
            "simulation_hash": self.simulation_hash,
        }


@dataclass(frozen=True)
class ExecutionResult:
    plan_id: str
    success: bool
    transaction_signature: str | None
    error: str | None
    executed_at: str
    mode: str  # "dry_run", "simulation", "live"

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "success": self.success,
            "transaction_signature": self.transaction_signature,
            "error": self.error,
            "executed_at": self.executed_at,
            "mode": self.mode,
        }


class LiveExecutorInterface(ABC):
    """Abstract live executor. Real implementations must override all methods."""

    def __init__(self, config: LiveTradingConfig | None = None) -> None:
        self.config = config or load_live_trading_config()

    @abstractmethod
    def build_quote_plan(self, intent: TradeIntent) -> QuotePlan:
        ...

    @abstractmethod
    def build_transaction_plan(self, quote: QuotePlan) -> TransactionPlan:
        ...

    @abstractmethod
    def simulate_transaction(self, plan: TransactionPlan) -> ExecutionResult:
        ...

    def submit_transaction(self, plan: TransactionPlan) -> ExecutionResult:
        """Submit a signed transaction to the network.

        Raises RuntimeError unless ENABLE_TRANSACTION_SEND is true.
        """
        if not self.config.flags.enable_transaction_send:
            raise RuntimeError(
                "Transaction submission is disabled. Set ENABLE_TRANSACTION_SEND=true to enable."
            )
        return self._submit_live(plan)

    @abstractmethod
    def _submit_live(self, plan: TransactionPlan) -> ExecutionResult:
        """Actual live submission. Only called when ENABLE_TRANSACTION_SEND is true."""
        ...
