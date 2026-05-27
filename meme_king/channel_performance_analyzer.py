from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import mean, median
from typing import Any

from .deterministic import parse_timestamp, stable_hash
from .paper_executor import PaperExecutor


HOLD_WINDOWS: tuple[tuple[str, int], ...] = (
    ("1m", 60),
    ("5m", 300),
    ("15m", 900),
    ("30m", 1800),
    ("1h", 3600),
    ("2h", 7200),
    ("6h", 21600),
    ("24h", 86400),
)
QUICK_FLIP_WINDOWS = {"1m", "5m", "15m"}
LONGER_HOLD_WINDOWS = {"1h", "2h", "6h", "24h"}


@dataclass(frozen=True)
class AlertPerformance:
    channel_name: str
    token_symbol: str | None
    mint_address: str | None
    alert_timestamp: str | None
    entry_price: float | None
    max_price_1m: float | None
    max_price_5m: float | None
    max_price_15m: float | None
    max_price_30m: float | None
    max_price_1h: float | None
    max_price_2h: float | None
    max_price_6h: float | None
    max_price_24h: float | None
    max_gain_pct: float | None
    max_gain_x: float | None
    time_to_max_seconds: int | None
    worst_drawdown_pct: float | None
    best_hold_window: str | None
    win_at_25_pct: bool
    win_at_50_pct: bool
    win_at_100_pct: bool
    source_files: list[str]
    confidence: float | None
    price_source: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HoldWindowStats:
    hold_window: str
    seconds: int
    alerts: int
    win_rate_25_pct: float | None
    average_gain_pct: float | None
    median_gain_pct: float | None
    average_gain_x: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ChannelPerformance:
    channel_name: str
    alerts: int
    tokens: int
    win_rate_25_pct: float | None
    win_rate_50_pct: float | None
    win_rate_100_pct: float | None
    average_max_gain_pct: float | None
    median_max_gain_pct: float | None
    average_max_gain_x: float | None
    median_max_gain_x: float | None
    best_hold_window: str | None
    quick_flip_score: float | None
    longer_hold_score: float | None
    price_sources: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PricePoint:
    timestamp: str | None
    seconds_after_alert: int | None
    price: float
    source_file: str


@dataclass(frozen=True)
class PriceResolution:
    entry_price: float | None
    window_prices: dict[str, float | None]
    max_gain_x: float | None
    max_gain_pct: float | None
    time_to_max_seconds: int | None
    worst_drawdown_pct: float | None
    price_source: str
    source_files: list[str]


class ChannelPerformanceAnalyzer:
    def __init__(
        self,
        selected_channels: list[str],
        market_records: list[dict[str, Any]] | None = None,
        paper_positions: list[dict[str, Any]] | None = None,
        paper_exits: list[dict[str, Any]] | None = None,
    ) -> None:
        self.selected_channels = selected_channels
        self.market_index = self._build_market_index(market_records or [])
        self.paper_by_signal_id = self._build_paper_index(paper_positions or [], paper_exits or [])
        self.paper_executor = PaperExecutor()

    def analyze_alerts(self, alerts: list[dict[str, Any]]) -> list[AlertPerformance]:
        performances = []
        for alert in sorted(alerts, key=self._alert_sort_key):
            if alert.get("channel_name") not in self.selected_channels:
                continue
            if not (alert.get("token_symbol") or alert.get("mint_address")):
                continue
            performances.append(self.analyze_alert(alert))
        return performances

    def analyze_alert(self, alert: dict[str, Any]) -> AlertPerformance:
        resolution = self.resolve_price(alert)
        max_gain_pct = resolution.max_gain_pct
        return AlertPerformance(
            channel_name=str(alert.get("channel_name") or ""),
            token_symbol=alert.get("token_symbol"),
            mint_address=alert.get("mint_address"),
            alert_timestamp=parse_timestamp(alert.get("timestamp") or alert.get("created_at")),
            entry_price=resolution.entry_price,
            max_price_1m=resolution.window_prices.get("1m"),
            max_price_5m=resolution.window_prices.get("5m"),
            max_price_15m=resolution.window_prices.get("15m"),
            max_price_30m=resolution.window_prices.get("30m"),
            max_price_1h=resolution.window_prices.get("1h"),
            max_price_2h=resolution.window_prices.get("2h"),
            max_price_6h=resolution.window_prices.get("6h"),
            max_price_24h=resolution.window_prices.get("24h"),
            max_gain_pct=max_gain_pct,
            max_gain_x=resolution.max_gain_x,
            time_to_max_seconds=resolution.time_to_max_seconds,
            worst_drawdown_pct=resolution.worst_drawdown_pct,
            best_hold_window=self.best_hold_window(resolution.window_prices, resolution.entry_price),
            win_at_25_pct=bool(max_gain_pct is not None and max_gain_pct >= 25.0),
            win_at_50_pct=bool(max_gain_pct is not None and max_gain_pct >= 50.0),
            win_at_100_pct=bool(max_gain_pct is not None and max_gain_pct >= 100.0),
            source_files=resolution.source_files,
            confidence=self._to_float(alert.get("confidence")),
            price_source=resolution.price_source,
        )

    def resolve_price(self, alert: dict[str, Any]) -> PriceResolution:
        real_points = self._market_points_for_alert(alert)
        if real_points:
            return self._resolve_real_prices(real_points)
        return self._resolve_paper_prices(alert)

    def summarize_channels(self, performances: list[AlertPerformance]) -> dict[str, ChannelPerformance]:
        grouped: dict[str, list[AlertPerformance]] = defaultdict(list)
        for performance in performances:
            grouped[performance.channel_name].append(performance)

        summaries = {}
        for channel in self.selected_channels:
            rows = grouped.get(channel, [])
            max_gain_pct = [row.max_gain_pct for row in rows if row.max_gain_pct is not None]
            max_gain_x = [row.max_gain_x for row in rows if row.max_gain_x is not None]
            tokens = {self._token_key(row.token_symbol, row.mint_address) for row in rows}
            tokens.discard("UNKNOWN")
            price_sources = Counter(row.price_source for row in rows)
            hold_windows = self.hold_window_summary(rows)
            best_hold = self._best_hold_from_stats(hold_windows)
            quick_score = self._best_score_for_windows(rows, QUICK_FLIP_WINDOWS)
            longer_score = self._best_score_for_windows(rows, LONGER_HOLD_WINDOWS)
            summaries[channel] = ChannelPerformance(
                channel_name=channel,
                alerts=len(rows),
                tokens=len(tokens),
                win_rate_25_pct=self._rate(row.win_at_25_pct for row in rows),
                win_rate_50_pct=self._rate(row.win_at_50_pct for row in rows),
                win_rate_100_pct=self._rate(row.win_at_100_pct for row in rows),
                average_max_gain_pct=self._round(mean(max_gain_pct), 6) if max_gain_pct else None,
                median_max_gain_pct=self._round(median(max_gain_pct), 6) if max_gain_pct else None,
                average_max_gain_x=self._round(mean(max_gain_x), 6) if max_gain_x else None,
                median_max_gain_x=self._round(median(max_gain_x), 6) if max_gain_x else None,
                best_hold_window=best_hold,
                quick_flip_score=quick_score,
                longer_hold_score=longer_score,
                price_sources=dict(sorted(price_sources.items())),
            )
        return summaries

    def hold_window_summary(self, performances: list[AlertPerformance]) -> dict[str, HoldWindowStats]:
        stats = {}
        for name, seconds in HOLD_WINDOWS:
            prices = []
            wins = []
            for row in performances:
                entry = row.entry_price
                price = self._window_price(row, name)
                if entry is None or entry <= 0 or price is None:
                    continue
                gain_x = price / entry
                prices.append(gain_x)
                wins.append(gain_x >= 1.25)
            gain_pct = [(value - 1.0) * 100.0 for value in prices]
            stats[name] = HoldWindowStats(
                hold_window=name,
                seconds=seconds,
                alerts=len(prices),
                win_rate_25_pct=self._rate(wins),
                average_gain_pct=self._round(mean(gain_pct), 6) if gain_pct else None,
                median_gain_pct=self._round(median(gain_pct), 6) if gain_pct else None,
                average_gain_x=self._round(mean(prices), 6) if prices else None,
            )
        return stats

    def best_tokens(self, performances: list[AlertPerformance], limit: int = 25) -> list[dict[str, Any]]:
        rows = sorted(
            performances,
            key=lambda row: (-(row.max_gain_pct if row.max_gain_pct is not None else -10**9), row.channel_name, row.token_symbol or "", row.mint_address or ""),
        )
        return [row.to_dict() for row in rows[:limit]]

    def worst_tokens(self, performances: list[AlertPerformance], limit: int = 25) -> list[dict[str, Any]]:
        rows = sorted(
            performances,
            key=lambda row: ((row.max_gain_pct if row.max_gain_pct is not None else 10**9), row.channel_name, row.token_symbol or "", row.mint_address or ""),
        )
        return [row.to_dict() for row in rows[:limit]]

    def rankings(self, summaries: dict[str, ChannelPerformance]) -> dict[str, Any]:
        quick = sorted(
            summaries.values(),
            key=lambda row: (-(row.quick_flip_score if row.quick_flip_score is not None else -10**9), row.channel_name),
        )
        longer = sorted(
            summaries.values(),
            key=lambda row: (-(row.longer_hold_score if row.longer_hold_score is not None else -10**9), row.channel_name),
        )
        return {
            "best_quick_flip_channel": quick[0].channel_name if quick and quick[0].quick_flip_score is not None else None,
            "best_longer_hold_channel": longer[0].channel_name if longer and longer[0].longer_hold_score is not None else None,
            "quick_flip_ranking": [
                {"channel_name": row.channel_name, "quick_flip_score": row.quick_flip_score, "alerts": row.alerts} for row in quick
            ],
            "longer_hold_ranking": [
                {"channel_name": row.channel_name, "longer_hold_score": row.longer_hold_score, "alerts": row.alerts} for row in longer
            ],
        }

    def data_quality_report(self, all_alerts: list[dict[str, Any]], performances: list[AlertPerformance]) -> dict[str, Any]:
        selected_alerts = [row for row in all_alerts if row.get("channel_name") in self.selected_channels]
        missing_token = [row for row in selected_alerts if not (row.get("token_symbol") or row.get("mint_address"))]
        price_sources = Counter(row.price_source for row in performances)
        warnings = []
        if price_sources.get("paper_simulated"):
            warnings.append("No complete true historical price window data was found for at least some alerts; paper_simulated replay fields were used.")
        if missing_token:
            warnings.append("Some selected-channel alerts were skipped because they had no token symbol or mint address.")
        for channel in self.selected_channels:
            if not any(row.channel_name == channel for row in performances):
                warnings.append(f"{channel} has no analyzable token alerts in the current local artifacts.")
        return {
            "selected_channels": self.selected_channels,
            "selected_channel_alerts": len(selected_alerts),
            "analyzed_alerts": len(performances),
            "skipped_missing_token_or_mint": len(missing_token),
            "price_sources": dict(sorted(price_sources.items())),
            "real_market_price_points_indexed": sum(len(points) for points in self.market_index.values()),
            "warnings": warnings,
        }

    def _resolve_real_prices(self, points: list[PricePoint]) -> PriceResolution:
        entry_price = points[0].price
        if entry_price <= 0:
            entry_price = None
        window_prices: dict[str, float | None] = {}
        for name, seconds in HOLD_WINDOWS:
            candidates = [point.price for point in points if point.seconds_after_alert is not None and 0 <= point.seconds_after_alert <= seconds]
            window_prices[name] = self._round(max(candidates), 12) if candidates else None
        max_point = max(points, key=lambda point: point.price)
        min_price = min(point.price for point in points)
        max_gain_x = max_point.price / entry_price if entry_price else None
        return PriceResolution(
            entry_price=self._round(entry_price, 12) if entry_price else None,
            window_prices=window_prices,
            max_gain_x=self._round(max_gain_x, 6) if max_gain_x is not None else None,
            max_gain_pct=self._round((max_gain_x - 1.0) * 100.0, 6) if max_gain_x is not None else None,
            time_to_max_seconds=max_point.seconds_after_alert,
            worst_drawdown_pct=self._round((min_price / entry_price - 1.0) * 100.0, 6) if entry_price else None,
            price_source="real_historical",
            source_files=sorted({point.source_file for point in points}),
        )

    def _resolve_paper_prices(self, alert: dict[str, Any]) -> PriceResolution:
        entry_price = 1.0
        path = self.paper_executor.price_path(alert, max_hold_steps=len(HOLD_WINDOWS))
        if len(path) < len(HOLD_WINDOWS) + 1:
            path = [*path, *([path[-1]] * (len(HOLD_WINDOWS) + 1 - len(path)))]
        window_prices = {name: self._round(max(path[: index + 2]), 12) for index, (name, _) in enumerate(HOLD_WINDOWS)}
        max_price = max(path)
        min_price = min(path)
        max_index = path.index(max_price)
        time_to_max_seconds = 0 if max_index == 0 else HOLD_WINDOWS[min(max_index - 1, len(HOLD_WINDOWS) - 1)][1]
        source_files = [str(alert.get("source_file"))] if alert.get("source_file") else []
        signal_id = self.paper_executor.signal_id(alert)
        paper = self.paper_by_signal_id.get(signal_id)
        if paper:
            source_files.extend(paper["source_files"])
        return PriceResolution(
            entry_price=entry_price,
            window_prices=window_prices,
            max_gain_x=self._round(max_price / entry_price, 6),
            max_gain_pct=self._round((max_price / entry_price - 1.0) * 100.0, 6),
            time_to_max_seconds=time_to_max_seconds,
            worst_drawdown_pct=self._round((min_price / entry_price - 1.0) * 100.0, 6),
            price_source="paper_simulated",
            source_files=sorted(set(source_files)),
        )

    def _market_points_for_alert(self, alert: dict[str, Any]) -> list[PricePoint]:
        keys = [value for value in (alert.get("mint_address"), alert.get("token_symbol")) if value]
        if not keys:
            return []
        alert_ts = parse_timestamp(alert.get("timestamp") or alert.get("created_at"))
        points = []
        for key in keys:
            for point in self.market_index.get(str(key), []):
                seconds = point.seconds_after_alert
                if seconds is None and alert_ts and point.timestamp:
                    seconds = self._seconds_between(alert_ts, point.timestamp)
                if seconds is None or 0 <= seconds <= HOLD_WINDOWS[-1][1]:
                    points.append(PricePoint(point.timestamp, seconds, point.price, point.source_file))
        return sorted(points, key=lambda point: (point.seconds_after_alert if point.seconds_after_alert is not None else 10**12, point.price))

    def _build_market_index(self, records: list[dict[str, Any]]) -> dict[str, list[PricePoint]]:
        index: dict[str, list[PricePoint]] = defaultdict(list)
        for record in records:
            price = self._extract_price(record)
            if price is None or price <= 0:
                continue
            timestamp = parse_timestamp(self._first_value(record, ["timestamp", "time", "created_at", "recorded_at", "block_time"]))
            seconds_after = self._to_int(self._first_value(record, ["seconds_after_alert", "age_seconds", "elapsed_seconds", "offset_seconds"]))
            source_file = str(record.get("_source_file") or record.get("source_file") or "unknown")
            point = PricePoint(timestamp, seconds_after, price, source_file)
            for key in (record.get("mint_address"), record.get("mint"), record.get("token_address"), record.get("address"), record.get("token_symbol"), record.get("symbol")):
                if key:
                    index[str(key)].append(point)
        return {key: sorted(points, key=lambda point: (point.timestamp or "", point.seconds_after_alert or 0, point.price)) for key, points in index.items()}

    def _build_paper_index(self, positions: list[dict[str, Any]], exits: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        by_signal: dict[str, dict[str, Any]] = {}
        for row in positions:
            signal_id = row.get("signal_id")
            if signal_id:
                by_signal.setdefault(str(signal_id), {"source_files": ["artifacts/paper_trading/paper_positions.jsonl"]})
        for row in exits:
            signal_id = row.get("signal_id")
            if signal_id:
                by_signal.setdefault(str(signal_id), {"source_files": []})["source_files"].append("artifacts/paper_trading/paper_exits.jsonl")
        return by_signal

    @staticmethod
    def best_hold_window(window_prices: dict[str, float | None], entry_price: float | None) -> str | None:
        if entry_price is None or entry_price <= 0:
            return None
        candidates = [(name, price / entry_price) for name, price in window_prices.items() if price is not None]
        if not candidates:
            return None
        return max(candidates, key=lambda item: (item[1], -dict(HOLD_WINDOWS)[item[0]]))[0]

    def _best_hold_from_stats(self, stats: dict[str, HoldWindowStats]) -> str | None:
        populated = [row for row in stats.values() if row.average_gain_pct is not None]
        if not populated:
            return None
        return max(populated, key=lambda row: (row.average_gain_pct or -10**9, -row.seconds)).hold_window

    def _best_score_for_windows(self, performances: list[AlertPerformance], windows: set[str]) -> float | None:
        values = []
        for row in performances:
            if row.entry_price is None or row.entry_price <= 0:
                continue
            gains = []
            for window in windows:
                price = self._window_price(row, window)
                if price is not None:
                    gains.append(price / row.entry_price)
            if gains:
                values.append(max(gains))
        return self._round(mean(values), 6) if values else None

    @staticmethod
    def _window_price(row: AlertPerformance, window: str) -> float | None:
        return getattr(row, f"max_price_{window}")

    @staticmethod
    def _token_key(symbol: str | None, mint: str | None) -> str:
        return str(mint or symbol or "UNKNOWN")

    @staticmethod
    def _alert_sort_key(alert: dict[str, Any]) -> tuple[str, str, str, str]:
        return (
            str(alert.get("timestamp") or alert.get("created_at") or ""),
            str(alert.get("channel_name") or ""),
            str(alert.get("token_symbol") or ""),
            str(alert.get("mint_address") or alert.get("message_id") or stable_hash(alert)[:16]),
        )

    @staticmethod
    def _rate(values: Any) -> float | None:
        materialized = list(values)
        if not materialized:
            return None
        return round(sum(1 for value in materialized if value) / len(materialized), 6)

    @staticmethod
    def _round(value: float, digits: int = 6) -> float:
        return round(float(value), digits)

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).strip().replace("%", ""))
        except ValueError:
            return None

    @staticmethod
    def _to_int(value: Any) -> int | None:
        number = ChannelPerformanceAnalyzer._to_float(value)
        return int(number) if number is not None else None

    @staticmethod
    def _first_value(record: dict[str, Any], keys: list[str]) -> Any:
        for key in keys:
            if record.get(key) not in (None, ""):
                return record[key]
        return None

    @staticmethod
    def _extract_price(record: dict[str, Any]) -> float | None:
        for key in ("price", "price_usd", "close", "high", "market_cap", "liquidity_usd"):
            value = ChannelPerformanceAnalyzer._to_float(record.get(key))
            if value is not None and value > 0:
                return value
        return None

    @staticmethod
    def _seconds_between(start: str, end: str) -> int | None:
        from datetime import datetime

        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        except ValueError:
            return None
        return int((end_dt - start_dt).total_seconds())


def load_market_records(paths: list[Path], limit: int = 250_000) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted({item for item in paths if item.exists()}):
        for file_path in _iter_data_files(path):
            for record in _read_records(file_path):
                if not isinstance(record, dict):
                    continue
                if not _looks_like_market_record(record):
                    continue
                record = {**record, "_source_file": str(file_path)}
                records.append(record)
                if len(records) >= limit:
                    return records
    return records


def _iter_data_files(path: Path) -> list[Path]:
    if path.is_file() and path.suffix.lower() in {".json", ".jsonl", ".ndjson"}:
        return [path]
    if not path.is_dir():
        return []
    return [item for item in path.rglob("*") if item.suffix.lower() in {".json", ".jsonl", ".ndjson"}]


def _read_records(path: Path) -> list[Any]:
    try:
        if path.suffix.lower() in {".jsonl", ".ndjson"}:
            return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("prices", "price_history", "candles", "ohlcv", "records", "data"):
            if isinstance(data.get(key), list):
                return data[key]
        return [data]
    return []


def _looks_like_market_record(record: dict[str, Any]) -> bool:
    has_token = any(record.get(key) for key in ("mint_address", "mint", "token_address", "address", "token_symbol", "symbol"))
    has_price = any(record.get(key) not in (None, "") for key in ("price", "price_usd", "close", "high", "market_cap", "liquidity_usd"))
    return bool(has_token and has_price)
