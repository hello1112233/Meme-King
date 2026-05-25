from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from .deterministic import stable_hash


class TradeDecision(str, Enum):
    ENTER_PAPER = "ENTER_PAPER"
    SKIP = "SKIP"
    EXIT_TAKE_PROFIT = "EXIT_TAKE_PROFIT"
    EXIT_STOP_LOSS = "EXIT_STOP_LOSS"
    EXIT_TIMEOUT = "EXIT_TIMEOUT"
    HOLD = "HOLD"


@dataclass(frozen=True)
class EntryRule:
    min_confidence: float
    allowed_channels: list[str]
    max_signal_age: int
    strategy_profile: str
    cooldown_seconds: int
    duplicate_window_seconds: int
    min_channel_winrate: float
    min_channel_trades: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExitRule:
    stop_loss_pct: float
    take_profit_pct: float
    max_hold_seconds: int

    @property
    def stop_loss_x(self) -> float:
        return round(1.0 - self.stop_loss_pct, 6)

    @property
    def take_profit_x(self) -> float:
        return round(1.0 + self.take_profit_pct, 6)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["stop_loss_x"] = self.stop_loss_x
        data["take_profit_x"] = self.take_profit_x
        return data


@dataclass(frozen=True)
class SkillDecision:
    decision_id: str
    decision: str
    reasons: list[str]
    token: str | None
    channel_name: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class HermesTradeSkill:
    risk_pattern = re.compile(r"\b(rug|scam|honeypot|blacklist|drain|drainer|exploit|fake|reject|rejected|stolen)\b", re.I)

    def __init__(self, entry_rule: EntryRule, exit_rule: ExitRule) -> None:
        self.entry_rule = entry_rule
        self.exit_rule = exit_rule

    def decide_entry(self, setup: dict[str, Any]) -> SkillDecision:
        reasons: list[str] = []
        channel = setup.get("channel_name")
        confidence = normalized_confidence(setup.get("confidence"))
        if channel not in self.entry_rule.allowed_channels:
            reasons.append("channel_not_allowed")
        if confidence is None or confidence < self.entry_rule.min_confidence:
            reasons.append("confidence_below_rule")
        if float(setup.get("channel_winrate") or 0.0) < self.entry_rule.min_channel_winrate:
            reasons.append("channel_edge_below_rule")
        if int(setup.get("channel_trades") or 0) < self.entry_rule.min_channel_trades:
            reasons.append("channel_sample_below_rule")
        if bool(setup.get("duplicate")):
            reasons.append("duplicate_signal")
        if bool(setup.get("cooldown_active")):
            reasons.append("cooldown_active")
        if int(setup.get("signal_age_seconds") or 0) > self.entry_rule.max_signal_age:
            reasons.append("signal_too_old")
        if self.risk_pattern.search(str(setup.get("raw_text") or "")):
            reasons.append("risk_keyword")

        decision = TradeDecision.SKIP if reasons else TradeDecision.ENTER_PAPER
        return SkillDecision(
            decision_id=self.decision_id(setup, decision.value, reasons),
            decision=decision.value,
            reasons=reasons,
            token=setup.get("token_symbol") or setup.get("mint_address"),
            channel_name=channel,
        )

    def decide_exit(self, position: dict[str, Any]) -> SkillDecision:
        current_x = float(position.get("current_x") or 1.0)
        hold_seconds = int(position.get("hold_seconds") or 0)
        reasons: list[str] = []
        if current_x >= self.exit_rule.take_profit_x:
            decision = TradeDecision.EXIT_TAKE_PROFIT
            reasons.append("take_profit_reached")
        elif current_x <= self.exit_rule.stop_loss_x:
            decision = TradeDecision.EXIT_STOP_LOSS
            reasons.append("stop_loss_reached")
        elif hold_seconds >= self.exit_rule.max_hold_seconds:
            decision = TradeDecision.EXIT_TIMEOUT
            reasons.append("max_hold_reached")
        else:
            decision = TradeDecision.HOLD
            reasons.append("within_exit_bounds")
        return SkillDecision(
            decision_id=self.decision_id(position, decision.value, reasons),
            decision=decision.value,
            reasons=reasons,
            token=position.get("token_symbol") or position.get("mint_address"),
            channel_name=position.get("channel_name"),
        )

    def decision_id(self, payload: dict[str, Any], decision: str, reasons: list[str]) -> str:
        return "hermes_" + stable_hash(
            {
                "channel_name": payload.get("channel_name"),
                "token": payload.get("token_symbol") or payload.get("mint_address"),
                "message_id": payload.get("message_id"),
                "decision": decision,
                "reasons": reasons,
                "entry_rule": self.entry_rule.to_dict(),
                "exit_rule": self.exit_rule.to_dict(),
            }
        )[:24]

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_rule": self.entry_rule.to_dict(),
            "exit_rule": self.exit_rule.to_dict(),
        }


def normalized_confidence(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return round(number / 100.0 if number > 1 else number, 6)
    return None

