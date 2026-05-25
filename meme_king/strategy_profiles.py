from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class StrategyProfile:
    name: str
    entry_delay_seconds: int
    stop_loss_pct: float
    take_profit_pct: float
    max_hold_seconds: int
    position_size_units: float
    slippage_bps_simulated: int
    min_confidence: float

    @property
    def stop_loss_x(self) -> float:
        return round(1.0 - self.stop_loss_pct, 6)

    @property
    def take_profit_x(self) -> float:
        return round(1.0 + self.take_profit_pct, 6)

    @property
    def max_hold_steps(self) -> int:
        return max(1, round(self.max_hold_seconds / 600))

    def to_dict(self) -> dict[str, float | int | str]:
        data = asdict(self)
        data["stop_loss_x"] = self.stop_loss_x
        data["take_profit_x"] = self.take_profit_x
        data["max_hold_steps"] = self.max_hold_steps
        return data


STRATEGY_PROFILES: dict[str, StrategyProfile] = {
    "conservative": StrategyProfile(
        name="conservative",
        entry_delay_seconds=60,
        stop_loss_pct=0.18,
        take_profit_pct=0.35,
        max_hold_seconds=1800,
        position_size_units=0.5,
        slippage_bps_simulated=50,
        min_confidence=0.65,
    ),
    "balanced": StrategyProfile(
        name="balanced",
        entry_delay_seconds=30,
        stop_loss_pct=0.30,
        take_profit_pct=0.50,
        max_hold_seconds=7200,
        position_size_units=1.0,
        slippage_bps_simulated=100,
        min_confidence=0.45,
    ),
    "sniper": StrategyProfile(
        name="sniper",
        entry_delay_seconds=5,
        stop_loss_pct=0.35,
        take_profit_pct=1.00,
        max_hold_seconds=1800,
        position_size_units=0.75,
        slippage_bps_simulated=250,
        min_confidence=0.55,
    ),
    "graduation_watch": StrategyProfile(
        name="graduation_watch",
        entry_delay_seconds=120,
        stop_loss_pct=0.25,
        take_profit_pct=0.75,
        max_hold_seconds=14400,
        position_size_units=0.6,
        slippage_bps_simulated=150,
        min_confidence=0.35,
    ),
    "fast_exit": StrategyProfile(
        name="fast_exit",
        entry_delay_seconds=15,
        stop_loss_pct=0.15,
        take_profit_pct=0.25,
        max_hold_seconds=900,
        position_size_units=0.8,
        slippage_bps_simulated=75,
        min_confidence=0.25,
    ),
}


def all_profiles() -> list[StrategyProfile]:
    return [STRATEGY_PROFILES[name] for name in sorted(STRATEGY_PROFILES)]

