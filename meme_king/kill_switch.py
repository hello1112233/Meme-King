"""Kill switch for live trading.

Default state is HALTED. Real trading can only proceed when the kill switch
is explicitly released AND all safety checks pass.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .deterministic import utc_now_iso


@dataclass(frozen=True)
class KillSwitchState:
    halted: bool = True
    reasons: list[str] = field(default_factory=list)
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "halted": self.halted,
            "reasons": list(self.reasons),
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KillSwitchState":
        return cls(
            halted=bool(data.get("halted", True)),
            reasons=list(data.get("reasons", [])),
            updated_at=str(data.get("updated_at", "")),
        )


class KillSwitch:
    """Tracks why real trading is blocked."""

    REASON_DAILY_LOSS_LIMIT = "daily_loss_limit"
    REASON_MAX_OPEN_POSITIONS = "max_open_positions"
    REASON_MISSING_SOURCE = "missing_source"
    REASON_SOURCE_DEGRADED = "source_degraded"
    REASON_OOS_FAILED = "oos_failed"
    REASON_MANUAL_HALT = "manual_halt"
    REASON_TRANSACTION_SEND_DISABLED = "transaction_send_disabled"
    REASON_LIVE_TRADING_DISABLED = "live_trading_disabled"
    REASON_MISSING_WALLET = "missing_wallet"
    REASON_CONFIG_INVALID = "config_invalid"

    def __init__(self, state: KillSwitchState | None = None) -> None:
        self._state = state or KillSwitchState()
        self._active_reasons: set[str] = set(self._state.reasons)

    @property
    def halted(self) -> bool:
        return self._state.halted or bool(self._active_reasons)

    @property
    def reasons(self) -> list[str]:
        return sorted(self._active_reasons)

    @property
    def state(self) -> KillSwitchState:
        return KillSwitchState(
            halted=self.halted,
            reasons=self.reasons,
            updated_at=utc_now_iso(),
        )

    def halt(self, reason: str) -> None:
        self._active_reasons.add(reason)

    def release(self, reason: str) -> None:
        self._active_reasons.discard(reason)

    def release_all(self) -> None:
        self._active_reasons.clear()
        self._state = KillSwitchState(halted=False, reasons=[], updated_at=utc_now_iso())

    def can_trade(self) -> bool:
        return not self.halted

    def to_dict(self) -> dict[str, Any]:
        return self.state.to_dict()
