from __future__ import annotations

import re
from collections import Counter, deque
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from .channel_registry import ChannelRegistry
from .deterministic import stable_hash
from .strategy_profiles import STRATEGY_PROFILES, StrategyProfile


class GateDecision(str, Enum):
    APPROVE_FOR_PAPER = "APPROVE_FOR_PAPER"
    BLOCK_FOR_RISK = "BLOCK_FOR_RISK"
    WATCH_ONLY = "WATCH_ONLY"
    NEEDS_MORE_DATA = "NEEDS_MORE_DATA"


class GateReason(str, Enum):
    CHANNEL_NOT_ALLOWLISTED = "CHANNEL_NOT_ALLOWLISTED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    MISSING_CONFIDENCE = "MISSING_CONFIDENCE"
    INSUFFICIENT_REPLAY_SUPPORT = "INSUFFICIENT_REPLAY_SUPPORT"
    LIQUIDITY_UNVERIFIED = "LIQUIDITY_UNVERIFIED"
    TOKEN_RECURRENCE_HIGH = "TOKEN_RECURRENCE_HIGH"
    DUPLICATE_SIGNAL = "DUPLICATE_SIGNAL"
    COOLDOWN_ACTIVE = "COOLDOWN_ACTIVE"
    SUSPICIOUS_TEXT = "SUSPICIOUS_TEXT"
    MAX_OPEN_PAPER_POSITIONS = "MAX_OPEN_PAPER_POSITIONS"
    BALANCED_PROFILE_INCOMPATIBLE = "BALANCED_PROFILE_INCOMPATIBLE"
    APPROVED_BALANCED_PROFILE = "APPROVED_BALANCED_PROFILE"


@dataclass(frozen=True)
class GateConfig:
    confidence_threshold: float = 0.45
    min_replay_support: int = 20
    max_token_recurrence: int = 25
    cooldown_window_signals: int = 3
    max_open_paper_positions: int = 250
    liquidity_placeholder_required: bool = False


@dataclass(frozen=True)
class GateReview:
    decision_id: str
    signal_id: str
    decision: str
    reasons: list[str]
    channel_name: str | None
    token_symbol: str | None
    mint_address: str | None
    confidence: float | None
    reference_profile: str
    replay_support: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExecutionGate:
    suspicious_pattern = re.compile(
        r"\b(rug|scam|honeypot|blacklist|stolen|drain|drainer|exploit|fake|blocked|reject|rejected|wrapper token)\b",
        re.IGNORECASE,
    )

    def __init__(
        self,
        scorecard: dict[str, Any] | None = None,
        strategy_comparison: dict[str, Any] | None = None,
        profile: StrategyProfile | None = None,
        config: GateConfig | None = None,
        registry: ChannelRegistry | None = None,
    ) -> None:
        self.scorecard = scorecard or {"channels": {}}
        self.strategy_comparison = strategy_comparison or {}
        self.profile = profile or STRATEGY_PROFILES["balanced"]
        self.config = config or GateConfig(confidence_threshold=self.profile.min_confidence)
        self.registry = registry or ChannelRegistry()
        self.seen_signal_keys: set[str] = set()
        self.cooldowns: dict[str, int] = {}
        self.open_positions: deque[str] = deque()
        self.token_counts: Counter[str] = Counter()

    def review(self, signal: dict[str, Any], replay_index: int = 0) -> GateReview:
        signal_id = self.signal_id(signal)
        token_key = self.token_key(signal)
        reasons: list[GateReason] = []
        confidence = normalized_confidence(signal)
        channel_name = signal.get("channel_name")

        if channel_name not in self.registry.allowed_names():
            reasons.append(GateReason.CHANNEL_NOT_ALLOWLISTED)
        if confidence is None:
            reasons.append(GateReason.MISSING_CONFIDENCE)
        elif confidence < self.config.confidence_threshold:
            reasons.append(GateReason.LOW_CONFIDENCE)
        replay_support = self.replay_support(channel_name)
        if replay_support < self.config.min_replay_support:
            reasons.append(GateReason.INSUFFICIENT_REPLAY_SUPPORT)
        if self.config.liquidity_placeholder_required and not self.has_liquidity_placeholder(signal):
            reasons.append(GateReason.LIQUIDITY_UNVERIFIED)
        if self.token_counts[token_key] >= self.config.max_token_recurrence:
            reasons.append(GateReason.TOKEN_RECURRENCE_HIGH)
        signal_key = self.signal_key(signal)
        if signal_key in self.seen_signal_keys:
            reasons.append(GateReason.DUPLICATE_SIGNAL)
        if token_key in self.cooldowns and replay_index - self.cooldowns[token_key] <= self.config.cooldown_window_signals:
            reasons.append(GateReason.COOLDOWN_ACTIVE)
        if self.suspicious_pattern.search(str(signal.get("raw_text") or "")):
            reasons.append(GateReason.SUSPICIOUS_TEXT)
        if len(self.open_positions) >= self.config.max_open_paper_positions:
            reasons.append(GateReason.MAX_OPEN_PAPER_POSITIONS)
        if not self.profile_is_supported():
            reasons.append(GateReason.BALANCED_PROFILE_INCOMPATIBLE)

        decision = self.decide(reasons)
        if decision == GateDecision.APPROVE_FOR_PAPER:
            reasons.append(GateReason.APPROVED_BALANCED_PROFILE)
            self.open_positions.append(signal_id)
            if len(self.open_positions) > self.config.max_open_paper_positions:
                self.open_positions.popleft()

        self.seen_signal_keys.add(signal_key)
        self.cooldowns[token_key] = replay_index
        self.token_counts[token_key] += 1

        reason_values = [reason.value for reason in reasons]
        return GateReview(
            decision_id=self.decision_id(signal, reason_values),
            signal_id=signal_id,
            decision=decision.value,
            reasons=reason_values,
            channel_name=channel_name,
            token_symbol=signal.get("token_symbol"),
            mint_address=signal.get("mint_address"),
            confidence=confidence,
            reference_profile=self.profile.name,
            replay_support=replay_support,
        )

    def decide(self, reasons: list[GateReason]) -> GateDecision:
        block_reasons = {
            GateReason.CHANNEL_NOT_ALLOWLISTED,
            GateReason.DUPLICATE_SIGNAL,
            GateReason.COOLDOWN_ACTIVE,
            GateReason.SUSPICIOUS_TEXT,
            GateReason.MAX_OPEN_PAPER_POSITIONS,
            GateReason.BALANCED_PROFILE_INCOMPATIBLE,
            GateReason.TOKEN_RECURRENCE_HIGH,
        }
        if any(reason in block_reasons for reason in reasons):
            return GateDecision.BLOCK_FOR_RISK
        if GateReason.MISSING_CONFIDENCE in reasons or GateReason.INSUFFICIENT_REPLAY_SUPPORT in reasons:
            return GateDecision.NEEDS_MORE_DATA
        if GateReason.LOW_CONFIDENCE in reasons or GateReason.LIQUIDITY_UNVERIFIED in reasons:
            return GateDecision.WATCH_ONLY
        return GateDecision.APPROVE_FOR_PAPER

    def decision_id(self, signal: dict[str, Any], reasons: list[str]) -> str:
        return "gate_" + stable_hash({"signal_id": self.signal_id(signal), "reasons": reasons, "profile": self.profile.name})[:24]

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

    def signal_key(self, signal: dict[str, Any]) -> str:
        return stable_hash(
            {
                "channel_name": signal.get("channel_name"),
                "message_id": signal.get("message_id"),
                "token": self.token_key(signal),
            }
        )

    def token_key(self, signal: dict[str, Any]) -> str:
        return str(signal.get("mint_address") or signal.get("token_symbol") or "UNKNOWN").casefold()

    def replay_support(self, channel_name: Any) -> int:
        channels = self.scorecard.get("channels") or {}
        row = channels.get(str(channel_name)) or {}
        return int(row.get("replay_frequency") or row.get("records") or 0)

    def has_liquidity_placeholder(self, signal: dict[str, Any]) -> bool:
        text = str(signal.get("raw_text") or "").casefold()
        return any(key in signal and signal.get(key) not in (None, "") for key in ("liquidity", "liquidity_usd", "market_cap")) or "liquidity" in text or "market_cap" in text or "market cap" in text

    def profile_is_supported(self) -> bool:
        ranking = self.strategy_comparison.get("ranking") or []
        if not ranking:
            return True
        return any(row.get("profile") == self.profile.name for row in ranking)


def normalized_confidence(signal: dict[str, Any]) -> float | None:
    for key in ("confidence", "historical_score", "historical_winrate"):
        value = signal.get(key)
        if isinstance(value, (int, float)):
            return round(float(value) / 100.0 if float(value) > 1 else float(value), 6)
    return None

