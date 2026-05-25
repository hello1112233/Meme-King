from meme_king.kill_switch import KillSwitch, KillSwitchState


def test_default_halted():
    ks = KillSwitch()
    assert ks.halted is True
    assert ks.can_trade() is False


def test_release_all_allows_trading():
    ks = KillSwitch()
    ks.release_all()
    assert ks.halted is False
    assert ks.can_trade() is True


def test_halt_adds_reason():
    ks = KillSwitch()
    ks.release_all()
    ks.halt("test_reason")
    assert ks.halted is True
    assert "test_reason" in ks.reasons


def test_release_removes_reason():
    ks = KillSwitch()
    ks.halt("a")
    ks.halt("b")
    ks.release("a")
    assert "a" not in ks.reasons
    assert "b" in ks.reasons


def test_state_serialization():
    ks = KillSwitch()
    ks.halt("daily_loss_limit")
    data = ks.to_dict()
    assert data["halted"] is True
    assert "daily_loss_limit" in data["reasons"]


def test_state_from_dict():
    state = KillSwitchState.from_dict({"halted": False, "reasons": [], "updated_at": "2026-01-01T00:00:00Z"})
    ks = KillSwitch(state)
    assert ks.halted is False


def test_known_reasons_exist():
    assert KillSwitch.REASON_DAILY_LOSS_LIMIT == "daily_loss_limit"
    assert KillSwitch.REASON_MAX_OPEN_POSITIONS == "max_open_positions"
    assert KillSwitch.REASON_MISSING_SOURCE == "missing_source"
    assert KillSwitch.REASON_SOURCE_DEGRADED == "source_degraded"
    assert KillSwitch.REASON_OOS_FAILED == "oos_failed"
    assert KillSwitch.REASON_MANUAL_HALT == "manual_halt"
    assert KillSwitch.REASON_TRANSACTION_SEND_DISABLED == "transaction_send_disabled"
    assert KillSwitch.REASON_LIVE_TRADING_DISABLED == "live_trading_disabled"
