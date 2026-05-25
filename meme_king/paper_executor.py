from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from .deterministic import parse_timestamp, stable_hash


FORBIDDEN_EXECUTION_FIELDS = {
    "wallet",
    "wallet_address",
    "private_key",
    "privateKey",
    "rpc_url",
    "sendTransaction",
    "signed_transaction",
    "signature",
    "swap",
}


@dataclass(frozen=True)
class PaperOrder:
    order_id: str
    signal_id: str
    channel_name: str
    token_symbol: str | None
    mint_address: str | None
    side: str
    quantity: float
    reference_price: float
    created_at: str
    take_profit_x: float
    stop_loss_x: float
    max_hold_steps: int
    status: str = "created"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PaperFill:
    fill_id: str
    order_id: str
    signal_id: str
    side: str
    quantity: float
    fill_price: float
    fill_step: int
    created_at: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PaperPosition:
    position_id: str
    entry_order_id: str
    signal_id: str
    channel_name: str
    token_symbol: str | None
    mint_address: str | None
    quantity: float
    entry_price: float
    entry_step: int
    opened_at: str
    status: str
    take_profit_x: float
    stop_loss_x: float
    max_hold_steps: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PaperExit:
    exit_id: str
    position_id: str
    exit_order_id: str
    signal_id: str
    exit_price: float
    exit_step: int
    exited_at: str
    reason: str
    pnl_x: float
    pnl_pct: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PaperExecutor:
    """Deterministic paper-only lifecycle simulator.

    This class intentionally has no wallet, private-key, RPC, swap, or transaction
    fields. It simulates fills from historical/replay fields only.
    """

    def __init__(
        self,
        take_profit_x: float = 1.5,
        stop_loss_x: float = 0.7,
        max_hold_steps: int = 12,
        base_quantity: float = 1.0,
    ) -> None:
        self.take_profit_x = take_profit_x
        self.stop_loss_x = stop_loss_x
        self.max_hold_steps = max_hold_steps
        self.base_quantity = base_quantity

    def signal_id(self, signal: dict[str, Any]) -> str:
        return stable_hash(
            {
                "channel_name": signal.get("channel_name"),
                "message_id": signal.get("message_id"),
                "timestamp": signal.get("timestamp"),
                "token_symbol": signal.get("token_symbol"),
                "mint_address": signal.get("mint_address"),
                "source_file": signal.get("source_file"),
            }
        )[:24]

    def order_id(self, signal: dict[str, Any], side: str) -> str:
        return "paper_" + stable_hash({"signal_id": self.signal_id(signal), "side": side})[:24]

    def create_entry_order(self, signal: dict[str, Any]) -> PaperOrder | None:
        if not self.is_tradeable_signal(signal):
            return None
        signal_id = self.signal_id(signal)
        return PaperOrder(
            order_id=self.order_id(signal, "entry"),
            signal_id=signal_id,
            channel_name=str(signal.get("channel_name") or ""),
            token_symbol=signal.get("token_symbol"),
            mint_address=signal.get("mint_address"),
            side="entry",
            quantity=self.base_quantity,
            reference_price=1.0,
            created_at=self.signal_time(signal),
            take_profit_x=self.take_profit_x,
            stop_loss_x=self.stop_loss_x,
            max_hold_steps=self.max_hold_steps,
        )

    def simulate_entry(self, order: PaperOrder) -> tuple[PaperPosition, PaperFill]:
        fill = PaperFill(
            fill_id="fill_" + stable_hash({"order_id": order.order_id, "side": "entry"})[:24],
            order_id=order.order_id,
            signal_id=order.signal_id,
            side="entry",
            quantity=order.quantity,
            fill_price=order.reference_price,
            fill_step=0,
            created_at=order.created_at,
            reason="paper_entry",
        )
        position = PaperPosition(
            position_id="pos_" + stable_hash({"order_id": order.order_id, "signal_id": order.signal_id})[:24],
            entry_order_id=order.order_id,
            signal_id=order.signal_id,
            channel_name=order.channel_name,
            token_symbol=order.token_symbol,
            mint_address=order.mint_address,
            quantity=order.quantity,
            entry_price=fill.fill_price,
            entry_step=0,
            opened_at=order.created_at,
            status="open",
            take_profit_x=order.take_profit_x,
            stop_loss_x=order.stop_loss_x,
            max_hold_steps=order.max_hold_steps,
        )
        return position, fill

    def create_exit_order(self, position: PaperPosition, signal: dict[str, Any]) -> PaperOrder:
        return PaperOrder(
            order_id=self.order_id(signal, "exit"),
            signal_id=position.signal_id,
            channel_name=position.channel_name,
            token_symbol=position.token_symbol,
            mint_address=position.mint_address,
            side="exit",
            quantity=position.quantity,
            reference_price=position.entry_price,
            created_at=self.signal_time(signal),
            take_profit_x=position.take_profit_x,
            stop_loss_x=position.stop_loss_x,
            max_hold_steps=position.max_hold_steps,
        )

    def simulate_exit(self, position: PaperPosition, signal: dict[str, Any]) -> tuple[PaperExit, PaperFill, PaperOrder]:
        path = self.price_path(signal, position.max_hold_steps)
        exit_step, exit_price, reason = self.resolve_exit(path, position)
        exit_order = self.create_exit_order(position, signal)
        exit_fill = PaperFill(
            fill_id="fill_" + stable_hash({"order_id": exit_order.order_id, "side": "exit", "step": exit_step})[:24],
            order_id=exit_order.order_id,
            signal_id=position.signal_id,
            side="exit",
            quantity=position.quantity,
            fill_price=exit_price,
            fill_step=exit_step,
            created_at=exit_order.created_at,
            reason=reason,
        )
        pnl_x = round(exit_price / position.entry_price, 6)
        exit_record = PaperExit(
            exit_id="exit_" + stable_hash({"position_id": position.position_id, "step": exit_step, "price": exit_price})[:24],
            position_id=position.position_id,
            exit_order_id=exit_order.order_id,
            signal_id=position.signal_id,
            exit_price=exit_price,
            exit_step=exit_step,
            exited_at=exit_order.created_at,
            reason=reason,
            pnl_x=pnl_x,
            pnl_pct=round((pnl_x - 1.0) * 100.0, 4),
        )
        return exit_record, exit_fill, exit_order

    def simulate_signal(self, signal: dict[str, Any]) -> dict[str, Any] | None:
        entry_order = self.create_entry_order(signal)
        if not entry_order:
            return None
        position, entry_fill = self.simulate_entry(entry_order)
        exit_record, exit_fill, exit_order = self.simulate_exit(position, signal)
        closed_position = PaperPosition(**{**position.to_dict(), "status": "closed"})
        return {
            "orders": [entry_order, exit_order],
            "position": closed_position,
            "fills": [entry_fill, exit_fill],
            "exit": exit_record,
        }

    def resolve_exit(self, path: list[float], position: PaperPosition) -> tuple[int, float, str]:
        for step, price in enumerate(path[1:], start=1):
            if price <= position.stop_loss_x:
                return step, round(price, 6), "stop_loss"
            if price >= position.take_profit_x:
                return step, round(price, 6), "take_profit"
            if step >= position.max_hold_steps:
                return step, round(price, 6), "max_hold"
        return len(path) - 1, round(path[-1], 6), "max_hold"

    def price_path(self, signal: dict[str, Any], max_hold_steps: int) -> list[float]:
        peak = self.historical_peak(signal)
        trough = self.historical_trough(signal, peak)
        path = [1.0]
        if trough <= self.stop_loss_x:
            path.extend([round((1.0 + trough) / 2.0, 6), trough])
        elif peak >= self.take_profit_x:
            midpoint = min((1.0 + peak) / 2.0, self.take_profit_x * 0.98)
            path.extend([round(midpoint, 6), peak])
        else:
            final = max(trough, min(peak, self.take_profit_x - 0.01))
            steps = max(1, max_hold_steps)
            for step in range(1, steps + 1):
                path.append(round(1.0 + (final - 1.0) * step / steps, 6))
        return path

    def historical_peak(self, signal: dict[str, Any]) -> float:
        value = to_float(signal.get("historical_max_x"))
        if value and value > 0:
            return value
        raw_text = str(signal.get("raw_text") or "")
        for pattern in (r"outcome_peak['\"]?:\s*([0-9]+(?:\.[0-9]+)?)", r"peak[_ ]?x['\"]?:\s*([0-9]+(?:\.[0-9]+)?)", r"avg_peak['\"]?:\s*([0-9]+(?:\.[0-9]+)?)"):
            match = re.search(pattern, raw_text, flags=re.IGNORECASE)
            if match:
                return float(match.group(1))
        confidence = to_float(signal.get("confidence")) or to_float(signal.get("historical_score")) or 0.0
        normalized_confidence = confidence / 100.0 if confidence > 1 else confidence
        return round(0.75 + max(0.0, min(normalized_confidence, 1.0)) * 0.9, 6)

    def historical_trough(self, signal: dict[str, Any], peak: float) -> float:
        raw_text = str(signal.get("raw_text") or "")
        for pattern in (r"outcome_min['\"]?:\s*([0-9]+(?:\.[0-9]+)?)", r"min[_ ]?x['\"]?:\s*([0-9]+(?:\.[0-9]+)?)"):
            match = re.search(pattern, raw_text, flags=re.IGNORECASE)
            if match:
                return float(match.group(1))
        if peak < 0.75:
            return peak
        return 0.82

    def is_tradeable_signal(self, signal: dict[str, Any]) -> bool:
        if not signal.get("replayable"):
            return False
        if not (signal.get("token_symbol") or signal.get("mint_address")):
            return False
        return not any(field in signal for field in FORBIDDEN_EXECUTION_FIELDS)

    def signal_time(self, signal: dict[str, Any]) -> str:
        return parse_timestamp(signal.get("timestamp") or signal.get("created_at")) or "1970-01-01T00:00:00Z"


def to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value))
    return float(match.group(0)) if match else None

