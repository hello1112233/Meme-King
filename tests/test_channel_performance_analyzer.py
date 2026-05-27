from __future__ import annotations

from meme_king.channel_performance_analyzer import ChannelPerformanceAnalyzer


CHANNELS = ["Alpha", "Beta"]


def signal(
    *,
    channel: str = "Alpha",
    symbol: str = "AAA",
    mint: str | None = "MintAAA",
    max_x: float | None = 2.0,
    confidence: float = 0.8,
) -> dict[str, object]:
    return {
        "channel_name": channel,
        "message_id": f"{channel}-{symbol}-{mint}",
        "timestamp": "2026-01-01T00:00:00Z",
        "token_symbol": symbol,
        "mint_address": mint,
        "historical_max_x": max_x,
        "confidence": confidence,
        "replayable": True,
        "source_file": "fixture.json",
    }


def test_max_gain_percentage_and_x_calculation() -> None:
    analyzer = ChannelPerformanceAnalyzer(CHANNELS)

    row = analyzer.analyze_alert(signal(max_x=2.5))

    assert row.entry_price == 1.0
    assert row.max_gain_x == 2.5
    assert row.max_gain_pct == 150.0
    assert row.win_at_25_pct is True
    assert row.win_at_50_pct is True
    assert row.win_at_100_pct is True


def test_time_to_max_and_hold_window_selection() -> None:
    analyzer = ChannelPerformanceAnalyzer(CHANNELS)

    row = analyzer.analyze_alert(signal(max_x=1.8))

    assert row.time_to_max_seconds == 300
    assert row.best_hold_window == "5m"
    assert row.max_price_5m == 1.8


def test_hold_window_selection_prefers_earliest_equal_peak() -> None:
    analyzer = ChannelPerformanceAnalyzer(CHANNELS)
    window = analyzer.best_hold_window(
        {
            "1m": 1.1,
            "5m": 1.8,
            "15m": 1.8,
            "30m": 1.8,
            "1h": 1.8,
            "2h": 1.8,
            "6h": 1.8,
            "24h": 1.8,
        },
        1.0,
    )

    assert window == "5m"


def test_per_channel_aggregation() -> None:
    analyzer = ChannelPerformanceAnalyzer(CHANNELS)
    rows = analyzer.analyze_alerts(
        [
            signal(channel="Alpha", symbol="AAA", mint="MintAAA", max_x=2.0),
            signal(channel="Alpha", symbol="BBB", mint="MintBBB", max_x=1.1),
            signal(channel="Beta", symbol="CCC", mint="MintCCC", max_x=1.3),
        ]
    )

    summary = analyzer.summarize_channels(rows)

    assert summary["Alpha"].alerts == 2
    assert summary["Alpha"].tokens == 2
    assert summary["Alpha"].win_rate_25_pct == 0.5
    assert summary["Alpha"].average_max_gain_pct == 55.0
    assert summary["Beta"].win_rate_25_pct == 1.0


def test_missing_price_data_uses_paper_simulated_source() -> None:
    analyzer = ChannelPerformanceAnalyzer(CHANNELS)

    row = analyzer.analyze_alert(signal(max_x=None, confidence=0.0))

    assert row.price_source == "paper_simulated"
    assert row.max_gain_x == 1.0
    assert row.max_gain_pct == 0.0
    assert row.worst_drawdown_pct == -18.0


def test_real_market_prices_when_available() -> None:
    analyzer = ChannelPerformanceAnalyzer(
        CHANNELS,
        market_records=[
            {
                "mint_address": "MintAAA",
                "seconds_after_alert": 0,
                "price": 1.0,
                "_source_file": "prices.jsonl",
            },
            {
                "mint_address": "MintAAA",
                "seconds_after_alert": 120,
                "price": 1.6,
                "_source_file": "prices.jsonl",
            },
        ],
    )

    row = analyzer.analyze_alert(signal(max_x=9.0))

    assert row.price_source == "real_historical"
    assert row.max_gain_x == 1.6
    assert row.max_gain_pct == 60.0
    assert row.time_to_max_seconds == 120


def test_deterministic_output_order() -> None:
    analyzer = ChannelPerformanceAnalyzer(CHANNELS)
    alerts = [
        signal(channel="Beta", symbol="CCC", mint="MintCCC", max_x=1.3),
        signal(channel="Alpha", symbol="BBB", mint="MintBBB", max_x=1.1),
        signal(channel="Alpha", symbol="AAA", mint="MintAAA", max_x=2.0),
    ]

    first = [row.to_dict() for row in analyzer.analyze_alerts(alerts)]
    second = [row.to_dict() for row in analyzer.analyze_alerts(list(reversed(alerts)))]

    assert first == second
