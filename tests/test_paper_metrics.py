from meme_king.paper_metrics import (
    compute_channel_performance,
    compute_drawdown,
    compute_expectancy,
    compute_profit_factor,
    compute_winrate,
    summarize_trades,
)


def test_winrate():
    assert compute_winrate([1.0, -1.0, 0.5, 0.0]) == 0.5


def test_drawdown():
    assert compute_drawdown([2.0, -1.0, -3.0, 1.0]) == -4.0


def test_expectancy():
    assert compute_expectancy([1.0, -0.5, 0.5]) == 0.333333


def test_profit_factor():
    assert compute_profit_factor([2.0, -1.0, 1.0, -0.5]) == 2.0


def test_per_channel_stats():
    trades = [
        {"channel_name": "A", "pnl_units": 1.0, "pnl_x": 2.0},
        {"channel_name": "A", "pnl_units": -0.5, "pnl_x": 0.5},
        {"channel_name": "B", "pnl_units": 0.25, "pnl_x": 1.25},
    ]

    stats = compute_channel_performance(trades)

    assert stats["A"]["trades"] == 2
    assert stats["A"]["winrate"] == 0.5
    assert stats["B"]["total_pnl_units"] == 0.25


def test_deterministic_output():
    trades = [
        {"channel_name": "B", "pnl_units": 0.333333333, "pnl_x": 1.333333333, "exit_reason": "take_profit"},
        {"channel_name": "A", "pnl_units": -0.111111111, "pnl_x": 0.888888889, "exit_reason": "stop_loss"},
    ]

    first = summarize_trades(trades)
    second = summarize_trades(list(trades))

    assert first == second
    assert first["expectancy_units"] == 0.111111

