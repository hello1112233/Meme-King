"""Live trading configuration loader and validator.

All live execution is blocked by default. No private keys are stored in code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ExecutionFlags:
    enable_live_trading: bool = False
    enable_real_wallet: bool = False
    enable_transaction_send: bool = False


@dataclass(frozen=True)
class RiskLimits:
    max_position_sol: float = 0.01
    max_daily_loss_sol: float = 0.05
    max_open_positions: int = 1
    default_slippage_bps: int = 1500
    max_slippage_bps: int = 3000
    priority_fee_microlamports: int = 50000
    jito_tip_lamports: int = 0

    def __post_init__(self) -> None:
        if self.max_position_sol <= 0:
            raise ValueError("max_position_sol must be > 0")
        if self.max_daily_loss_sol <= 0:
            raise ValueError("max_daily_loss_sol must be > 0")
        if self.max_open_positions <= 0:
            raise ValueError("max_open_positions must be > 0")
        if self.default_slippage_bps <= 0 or self.default_slippage_bps > 10_000:
            raise ValueError("default_slippage_bps must be in (0, 10000]")
        if self.max_slippage_bps <= 0 or self.max_slippage_bps > 10_000:
            raise ValueError("max_slippage_bps must be in (0, 10000]")
        if self.max_slippage_bps < self.default_slippage_bps:
            raise ValueError("max_slippage_bps must be >= default_slippage_bps")


@dataclass(frozen=True)
class LiveTradingConfig:
    flags: ExecutionFlags
    risk: RiskLimits
    wallet_keypair_path: str = ""
    helius_api_key: str = ""
    helius_rpc_url: str = ""
    helius_sender_url: str = ""
    jupiter_api_base: str = ""
    pumpportal_ws_url: str = ""
    pumpswap_api_base: str = ""
    pumpfun_api_base: str = ""
    telegram_api_id: str = ""
    telegram_api_hash: str = ""
    telegram_session_name: str = ""


def _env_bool(key: str, default: bool = False) -> bool:
    value = os.getenv(key, "").strip().lower()
    if not value:
        return default
    return value in ("1", "true", "yes", "on")


def _env_float(key: str, default: float) -> float:
    value = os.getenv(key, "").strip()
    return float(value) if value else default


def _env_int(key: str, default: int) -> int:
    value = os.getenv(key, "").strip()
    return int(value) if value else default


def _env_str(key: str, default: str = "") -> str:
    return os.getenv(key, "").strip()


def load_live_trading_config(env_path: Path | None = None) -> LiveTradingConfig:
    """Load configuration from environment variables or a .env file."""
    if env_path is not None and env_path.exists():
        # Simple .env parser (no external deps)
        with env_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if key not in os.environ:
                    os.environ[key] = value

    flags = ExecutionFlags(
        enable_live_trading=_env_bool("ENABLE_LIVE_TRADING"),
        enable_real_wallet=_env_bool("ENABLE_REAL_WALLET"),
        enable_transaction_send=_env_bool("ENABLE_TRANSACTION_SEND"),
    )

    risk = RiskLimits(
        max_position_sol=_env_float("MAX_POSITION_SOL", 0.01),
        max_daily_loss_sol=_env_float("MAX_DAILY_LOSS_SOL", 0.05),
        max_open_positions=_env_int("MAX_OPEN_POSITIONS", 1),
        default_slippage_bps=_env_int("DEFAULT_SLIPPAGE_BPS", 1500),
        max_slippage_bps=_env_int("MAX_SLIPPAGE_BPS", 3000),
        priority_fee_microlamports=_env_int("PRIORITY_FEE_MICROLAMPORTS", 50000),
        jito_tip_lamports=_env_int("JITO_TIP_LAMPORTS", 0),
    )

    return LiveTradingConfig(
        flags=flags,
        risk=risk,
        wallet_keypair_path=_env_str("WALLET_KEYPAIR_PATH"),
        helius_api_key=_env_str("HELIUS_API_KEY"),
        helius_rpc_url=_env_str("HELIUS_RPC_URL"),
        helius_sender_url=_env_str("HELIUS_SENDER_URL"),
        jupiter_api_base=_env_str("JUPITER_API_BASE"),
        pumpportal_ws_url=_env_str("PUMPPORTAL_WS_URL"),
        pumpswap_api_base=_env_str("PUMPSWAP_API_BASE"),
        pumpfun_api_base=_env_str("PUMPFUN_API_BASE"),
        telegram_api_id=_env_str("TELEGRAM_API_ID"),
        telegram_api_hash=_env_str("TELEGRAM_API_HASH"),
        telegram_session_name=_env_str("TELEGRAM_SESSION_NAME"),
    )


def validate_live_trading_config(config: LiveTradingConfig) -> list[str]:
    """Return a list of error messages. Empty list means valid."""
    errors: list[str] = []

    if not config.flags.enable_live_trading:
        errors.append("ENABLE_LIVE_TRADING is false")

    if config.flags.enable_transaction_send and not config.flags.enable_real_wallet:
        errors.append("ENABLE_TRANSACTION_SEND=true requires ENABLE_REAL_WALLET=true")

    if config.flags.enable_real_wallet and not config.wallet_keypair_path:
        errors.append("ENABLE_REAL_WALLET=true requires WALLET_KEYPAIR_PATH")

    if config.wallet_keypair_path and not Path(config.wallet_keypair_path).exists():
        errors.append(f"WALLET_KEYPAIR_PATH does not exist: {config.wallet_keypair_path}")

    if config.risk.max_position_sol > 1.0:
        errors.append(f"MAX_POSITION_SOL too high: {config.risk.max_position_sol} > 1.0")

    if config.risk.max_daily_loss_sol > 1.0:
        errors.append(f"MAX_DAILY_LOSS_SOL too high: {config.risk.max_daily_loss_sol} > 1.0")

    if config.risk.default_slippage_bps > 5000:
        errors.append(f"DEFAULT_SLIPPAGE_BPS too high: {config.risk.default_slippage_bps} > 5000")

    if config.risk.max_slippage_bps > 5000:
        errors.append(f"MAX_SLIPPAGE_BPS too high: {config.risk.max_slippage_bps} > 5000")

    return errors
