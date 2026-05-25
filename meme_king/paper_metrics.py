from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from typing import Any


ROUND_DIGITS = 6


def dround(value: float | int | None, digits: int = ROUND_DIGITS) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def compute_pnl(entry_price: float, exit_price: float, quantity: float = 1.0) -> dict[str, float]:
    gross = (float(exit_price) - float(entry_price)) * float(quantity)
    pnl_x = float(exit_price) / float(entry_price) if entry_price else 0.0
    return {
        "gross_pnl_units": dround(gross),
        "pnl_x": dround(pnl_x),
        "pnl_pct": dround((pnl_x - 1.0) * 100.0),
    }


def compute_winrate(pnl_values: list[float]) -> float:
    if not pnl_values:
        return 0.0
    return dround(sum(1 for value in pnl_values if value > 0) / len(pnl_values))


def compute_drawdown(pnl_values: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for pnl in pnl_values:
        equity += float(pnl)
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity - peak)
    return dround(max_drawdown)


def compute_expectancy(pnl_values: list[float]) -> float:
    if not pnl_values:
        return 0.0
    return dround(mean(pnl_values))


def compute_profit_factor(pnl_values: list[float]) -> float | None:
    gross_profit = sum(value for value in pnl_values if value > 0)
    gross_loss = abs(sum(value for value in pnl_values if value < 0))
    if gross_loss == 0:
        return None if gross_profit == 0 else dround(float("inf"))
    return dround(gross_profit / gross_loss)


def compute_channel_performance(trades: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        grouped[str(trade.get("channel_name") or "UNKNOWN")].append(trade)
    output = {}
    for channel, rows in sorted(grouped.items()):
        pnls = [float(row.get("pnl_units") or 0.0) for row in rows]
        pnl_x = [float(row.get("pnl_x") or 0.0) for row in rows]
        output[channel] = {
            "trades": len(rows),
            "winrate": compute_winrate(pnls),
            "expectancy_units": compute_expectancy(pnls),
            "total_pnl_units": dround(sum(pnls)),
            "avg_pnl_x": dround(mean(pnl_x)) if pnl_x else 0.0,
            "profit_factor": compute_profit_factor(pnls),
            "max_drawdown_units": compute_drawdown(pnls),
        }
    return output


def compute_exit_reason_stats(trades: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        grouped[str(trade.get("exit_reason") or "unknown")].append(trade)
    output = {}
    total = len(trades)
    for reason, rows in sorted(grouped.items()):
        pnls = [float(row.get("pnl_units") or 0.0) for row in rows]
        output[reason] = {
            "trades": len(rows),
            "share": dround(len(rows) / total) if total else 0.0,
            "winrate": compute_winrate(pnls),
            "expectancy_units": compute_expectancy(pnls),
            "total_pnl_units": dround(sum(pnls)),
            "profit_factor": compute_profit_factor(pnls),
        }
    return output


def summarize_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [float(row.get("pnl_units") or 0.0) for row in trades]
    pnl_x = [float(row.get("pnl_x") or 0.0) for row in trades]
    reasons = Counter(str(row.get("exit_reason") or "unknown") for row in trades)
    return {
        "trades": len(trades),
        "winrate": compute_winrate(pnls),
        "expectancy_units": compute_expectancy(pnls),
        "total_pnl_units": dround(sum(pnls)),
        "avg_pnl_x": dround(mean(pnl_x)) if pnl_x else 0.0,
        "profit_factor": compute_profit_factor(pnls),
        "max_drawdown_units": compute_drawdown(pnls),
        "exit_reasons": dict(sorted(reasons.items())),
    }

