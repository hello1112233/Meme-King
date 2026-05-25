from meme_king.hermes_trade_skill import EntryRule, ExitRule, HermesTradeSkill
from tools.validate_hermes_trade_skill_oos import (
    check_channel_holdout,
    check_duplicate_collapse,
    check_shuffled_replay,
    check_time_split,
    compute_winrate_bool,
    token_key,
)


def row(overrides: dict | None = None) -> dict:
    base = {
        "created_at": "2026-05-25T12:00:00Z",
        "channel_name": "WaveX Call - Multichain",
        "token_symbol": "TKN",
        "mint_address": "Mint111111111111111111111111111111111111111",
        "message_id": "1",
        "confidence": 0.7,
        "channel_winrate": 0.95,
        "channel_trades": 100,
        "duplicate": False,
        "cooldown_active": False,
        "signal_age_seconds": 0,
        "raw_text": "clean",
        "pnl_units": 0.5,
        "win": True,
    }
    if overrides:
        base.update(overrides)
    return base


def test_compute_winrate_bool():
    assert compute_winrate_bool([True, True, False, False]) == 0.5
    assert compute_winrate_bool([]) == 0.0
    assert compute_winrate_bool([True] * 10) == 1.0


def test_token_key():
    assert token_key({"token_symbol": "ABC"}) == "ABC"
    assert token_key({"mint_address": "xyz"}) == "xyz"
    assert token_key({"token_symbol": "ABC", "mint_address": "xyz"}) == "ABC"
    assert token_key({}) == ""


def test_time_split_deterministic():
    rows = [
        row({"created_at": "2026-05-25T10:00:00Z", "win": True}),
        row({"created_at": "2026-05-25T11:00:00Z", "win": True}),
        row({"created_at": "2026-05-25T12:00:00Z", "win": False}),
        row({"created_at": "2026-05-25T13:00:00Z", "win": True}),
        row({"created_at": "2026-05-25T14:00:00Z", "win": True}),
        row({"created_at": "2026-05-25T15:00:00Z", "win": True}),
        row({"created_at": "2026-05-25T16:00:00Z", "win": True}),
        row({"created_at": "2026-05-25T17:00:00Z", "win": False}),
        row({"created_at": "2026-05-25T18:00:00Z", "win": True}),
        row({"created_at": "2026-05-25T19:00:00Z", "win": True}),
    ]
    result = check_time_split(rows)
    # 70/30 split -> 7 train, 3 test
    assert result["train_count"] == 7
    assert result["test_count"] == 3
    # test set wins: last 3 are True, False, True -> 2/3
    assert abs(result["test_winrate"] - 2 / 3) < 1e-6
    # Deterministic: same input must yield same output
    result2 = check_time_split(rows)
    assert result == result2


def test_time_split_passes_threshold():
    rows = [row({"created_at": f"2026-05-25T{i:02d}:00:00Z", "win": True}) for i in range(100)]
    result = check_time_split(rows)
    assert result["test_winrate"] == 1.0
    assert result["passed"] is True


def test_duplicate_token_collapse():
    rows = [
        row({"token_symbol": "A", "win": True}),
        row({"token_symbol": "A", "win": False}),
        row({"token_symbol": "B", "win": True}),
        row({"token_symbol": "B", "win": False}),
        row({"token_symbol": "C", "win": True}),
    ]
    result = check_duplicate_collapse(rows)
    assert result["original_count"] == 5
    assert result["collapsed_count"] == 3
    # first A is True, first B is True, C is True -> 3/3
    assert result["collapsed_winrate"] == 1.0
    assert result["passed"] is True


def test_duplicate_token_collapse_fails():
    rows = [
        row({"token_symbol": "A", "win": True}),
        row({"token_symbol": "A", "win": True}),
        row({"token_symbol": "B", "win": False}),
        row({"token_symbol": "B", "win": False}),
    ]
    result = check_duplicate_collapse(rows)
    assert result["collapsed_count"] == 2
    assert result["collapsed_winrate"] == 0.5
    assert result["passed"] is False


def test_channel_holdout_pass():
    rows = [
        row({"channel_name": "WaveX Call - Multichain"}),
        row({"channel_name": "WaveX Call - Multichain"}),
        row({"channel_name": "GMGN Featured Signals(Lv1) - SOL"}),
    ]
    result = check_channel_holdout(rows)
    assert abs(result["largest_share"] - 2 / 3) < 1e-6
    assert result["passed"] is True


def test_channel_holdout_fail():
    rows = [row({"channel_name": "WaveX Call - Multichain"}) for _ in range(96)]
    rows.append(row({"channel_name": "GMGN Featured Signals(Lv1) - SOL"}))
    result = check_channel_holdout(rows)
    assert abs(result["largest_share"] - 96 / 97) < 1e-6
    assert result["largest_share"] > 0.95
    assert result["passed"] is False


def test_shuffled_replay_consistency():
    skill = HermesTradeSkill(
        EntryRule(
            min_confidence=0.5,
            allowed_channels=["WaveX Call - Multichain"],
            max_signal_age=3600,
            strategy_profile="balanced",
            cooldown_seconds=0,
            duplicate_window_seconds=0,
            min_channel_winrate=0.0,
            min_channel_trades=25,
        ),
        ExitRule(stop_loss_pct=0.3, take_profit_pct=0.5, max_hold_seconds=7200),
    )
    rows = [row({"token_symbol": f"T{i}"}) for i in range(20)]
    result = check_shuffled_replay(rows, skill)
    assert result["count_match"] is True
    assert result["original_count"] == result["replay_count"]
    assert result["passed"] is True


def test_shuffled_replay_idempotent():
    """Skill is stateless; shuffling must not change outcomes."""
    skill = HermesTradeSkill(
        EntryRule(
            min_confidence=0.5,
            allowed_channels=["WaveX Call - Multichain"],
            max_signal_age=3600,
            strategy_profile="balanced",
            cooldown_seconds=0,
            duplicate_window_seconds=0,
            min_channel_winrate=0.0,
            min_channel_trades=25,
        ),
        ExitRule(stop_loss_pct=0.3, take_profit_pct=0.5, max_hold_seconds=7200),
    )
    rows = [row({"token_symbol": f"T{i}"}) for i in range(50)]
    result = check_shuffled_replay(rows, skill)
    assert result["count_match"] is True
    assert result["original_count"] == result["replay_count"] == 50
    assert result["passed"] is True
