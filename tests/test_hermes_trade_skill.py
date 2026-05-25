from meme_king.hermes_trade_skill import EntryRule, ExitRule, HermesTradeSkill
from tools.train_hermes_trade_skill import train


def skill():
    return HermesTradeSkill(
        EntryRule(
            min_confidence=0.5,
            allowed_channels=["WaveX Call - Multichain"],
            max_signal_age=3600,
            strategy_profile="balanced",
            cooldown_seconds=0,
            duplicate_window_seconds=0,
            min_channel_winrate=0.8,
            min_channel_trades=25,
        ),
        ExitRule(stop_loss_pct=0.3, take_profit_pct=0.5, max_hold_seconds=7200),
    )


def setup(**overrides):
    row = {
        "channel_name": "WaveX Call - Multichain",
        "token_symbol": "KING",
        "mint_address": "King111111111111111111111111111111111111111",
        "message_id": "1",
        "confidence": 0.7,
        "channel_winrate": 0.95,
        "channel_trades": 100,
        "duplicate": False,
        "cooldown_active": False,
        "signal_age_seconds": 0,
        "raw_text": "clean",
        "pnl_units": 0.5,
    }
    row.update(overrides)
    return row


def test_deterministic_rule_selection():
    rows = [setup(), setup(message_id="2")]
    first = train(rows, {}, {"profiles": {"balanced": {"profile": {}}}})
    second = train(rows, {}, {"profiles": {"balanced": {"profile": {}}}})

    assert first["entry_rule"] == second["entry_rule"]
    assert first["summary"] == second["summary"]


def test_skip_risky_text():
    decision = skill().decide_entry(setup(raw_text="rug warning"))

    assert decision.decision == "SKIP"
    assert "risk_keyword" in decision.reasons


def test_approve_clean_setup():
    decision = skill().decide_entry(setup())

    assert decision.decision == "ENTER_PAPER"


def test_hold_decision():
    decision = skill().decide_exit(setup(current_x=1.1, hold_seconds=60))

    assert decision.decision == "HOLD"


def test_take_profit_exit():
    decision = skill().decide_exit(setup(current_x=1.5, hold_seconds=60))

    assert decision.decision == "EXIT_TAKE_PROFIT"


def test_stop_loss_exit():
    decision = skill().decide_exit(setup(current_x=0.7, hold_seconds=60))

    assert decision.decision == "EXIT_STOP_LOSS"


def test_timeout_exit():
    decision = skill().decide_exit(setup(current_x=1.1, hold_seconds=7200))

    assert decision.decision == "EXIT_TIMEOUT"


def test_no_wallet_private_key_rpc_fields():
    decision = skill().decide_entry(setup()).to_dict()
    forbidden = {"wallet", "private_key", "rpc_url", "sendTransaction", "signed_transaction", "swap"}

    assert forbidden.isdisjoint(decision.keys())

