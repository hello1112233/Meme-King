import os
import tempfile
from pathlib import Path

import pytest

from meme_king.live_trading_config import (
    ExecutionFlags,
    LiveTradingConfig,
    RiskLimits,
    load_live_trading_config,
    validate_live_trading_config,
)


def test_default_blocks_trading():
    config = LiveTradingConfig(flags=ExecutionFlags(), risk=RiskLimits())
    assert config.flags.enable_live_trading is False
    assert config.flags.enable_real_wallet is False
    assert config.flags.enable_transaction_send is False


def test_risk_limits_defaults():
    risk = RiskLimits()
    assert risk.max_position_sol == 0.01
    assert risk.max_daily_loss_sol == 0.05
    assert risk.max_open_positions == 1
    assert risk.default_slippage_bps == 1500
    assert risk.max_slippage_bps == 3000


def test_risk_limits_validation():
    with pytest.raises(ValueError):
        RiskLimits(max_position_sol=0)
    with pytest.raises(ValueError):
        RiskLimits(max_daily_loss_sol=-1)
    with pytest.raises(ValueError):
        RiskLimits(max_open_positions=0)
    with pytest.raises(ValueError):
        RiskLimits(default_slippage_bps=0)
    with pytest.raises(ValueError):
        RiskLimits(max_slippage_bps=20_000)
    with pytest.raises(ValueError):
        RiskLimits(default_slippage_bps=3000, max_slippage_bps=2000)


def test_validate_blocks_when_disabled():
    config = LiveTradingConfig(flags=ExecutionFlags(), risk=RiskLimits())
    errors = validate_live_trading_config(config)
    assert "ENABLE_LIVE_TRADING is false" in errors


def test_validate_transaction_send_requires_wallet():
    flags = ExecutionFlags(
        enable_live_trading=True,
        enable_transaction_send=True,
        enable_real_wallet=False,
    )
    config = LiveTradingConfig(flags=flags, risk=RiskLimits())
    errors = validate_live_trading_config(config)
    assert any("ENABLE_TRANSACTION_SEND=true requires ENABLE_REAL_WALLET=true" in e for e in errors)


def test_validate_missing_wallet_path():
    flags = ExecutionFlags(
        enable_live_trading=True,
        enable_real_wallet=True,
        enable_transaction_send=True,
    )
    config = LiveTradingConfig(flags=flags, risk=RiskLimits())
    errors = validate_live_trading_config(config)
    assert any("WALLET_KEYPAIR_PATH" in e for e in errors)


def test_validate_position_too_high():
    flags = ExecutionFlags(enable_live_trading=True)
    risk = RiskLimits(max_position_sol=2.0)
    config = LiveTradingConfig(flags=flags, risk=risk)
    errors = validate_live_trading_config(config)
    assert any("MAX_POSITION_SOL too high" in e for e in errors)


def test_validate_daily_loss_too_high():
    flags = ExecutionFlags(enable_live_trading=True)
    risk = RiskLimits(max_daily_loss_sol=5.0)
    config = LiveTradingConfig(flags=flags, risk=risk)
    errors = validate_live_trading_config(config)
    assert any("MAX_DAILY_LOSS_SOL too high" in e for e in errors)


def test_validate_slippage_too_high():
    flags = ExecutionFlags(enable_live_trading=True)
    risk = RiskLimits(default_slippage_bps=6000, max_slippage_bps=6000)
    config = LiveTradingConfig(flags=flags, risk=risk)
    errors = validate_live_trading_config(config)
    assert any("DEFAULT_SLIPPAGE_BPS too high" in e for e in errors)


def test_load_from_env():
    os.environ["ENABLE_LIVE_TRADING"] = "true"
    os.environ["MAX_POSITION_SOL"] = "0.05"
    config = load_live_trading_config()
    assert config.flags.enable_live_trading is True
    assert config.risk.max_position_sol == 0.05
    # Clean up
    del os.environ["ENABLE_LIVE_TRADING"]
    del os.environ["MAX_POSITION_SOL"]


def test_load_from_env_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
        f.write("ENABLE_LIVE_TRADING=true\n")
        f.write("MAX_OPEN_POSITIONS=3\n")
        f.flush()
        env_path = Path(f.name)

    config = load_live_trading_config(env_path)
    assert config.flags.enable_live_trading is True
    assert config.risk.max_open_positions == 3

    env_path.unlink()
