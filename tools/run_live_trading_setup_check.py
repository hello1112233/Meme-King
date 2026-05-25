#!/usr/bin/env python3
"""Check live trading setup readiness.

Reads configuration, OOS validation, execution gate, and kill switch state.
Outputs readiness status and missing requirements.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meme_king.deterministic import read_json, rel, write_json
from meme_king.kill_switch import KillSwitch
from meme_king.live_trading_config import load_live_trading_config, validate_live_trading_config


def main() -> None:
    config = load_live_trading_config(rel("config/live_trading.env"))
    config_errors = validate_live_trading_config(config)

    oos = read_json(rel("artifacts/hermes_trade_skill/oos_validation.json"), default={})
    gate_summary = read_json(rel("artifacts/execution_gate/gate_summary.json"), default={})

    kill = KillSwitch()

    if not config.flags.enable_live_trading:
        kill.halt(KillSwitch.REASON_LIVE_TRADING_DISABLED)

    if not config.flags.enable_transaction_send:
        kill.halt(KillSwitch.REASON_TRANSACTION_SEND_DISABLED)

    if not config.flags.enable_real_wallet:
        kill.halt(KillSwitch.REASON_MISSING_WALLET)

    if config_errors:
        for err in config_errors:
            kill.halt(KillSwitch.REASON_CONFIG_INVALID)

    if not oos.get("oos_pass"):
        kill.halt(KillSwitch.REASON_OOS_FAILED)

    if not gate_summary.get("decision_counts", {}).get("APPROVE_FOR_PAPER"):
        kill.halt(KillSwitch.REASON_MISSING_SOURCE)

    missing_items: list[str] = []
    if not config.helius_api_key:
        missing_items.append("HELIUS_API_KEY")
    if not config.helius_rpc_url:
        missing_items.append("HELIUS_RPC_URL")
    if not config.jupiter_api_base:
        missing_items.append("JUPITER_API_BASE")

    if missing_items:
        kill.halt(KillSwitch.REASON_MISSING_SOURCE)

    readiness = determine_readiness(kill, config_errors, missing_items, oos)

    out_dir = rel("artifacts/live_trading_setup")
    out_dir.mkdir(parents=True, exist_ok=True)

    write_json(out_dir / "setup_readiness.json", readiness)
    write_json(out_dir / "risk_limits.json", config.risk.__dict__)
    write_json(out_dir / "kill_switch_state.json", kill.to_dict())
    write_json(out_dir / "missing_items.json", {"missing": missing_items, "config_errors": config_errors})

    print(f"readiness={readiness['status']}")
    print(f"halted={kill.halted}")
    print(f"reasons={kill.reasons}")
    print(f"missing={missing_items}")
    print(f"config_errors={config_errors}")


def determine_readiness(
    kill: KillSwitch,
    config_errors: list[str],
    missing_items: list[str],
    oos: dict[str, Any],
) -> dict[str, Any]:
    if kill.halted:
        if KillSwitch.REASON_LIVE_TRADING_DISABLED in kill.reasons or KillSwitch.REASON_TRANSACTION_SEND_DISABLED in kill.reasons:
            return {"status": "BLOCK_REAL_TRADING", "reasons": kill.reasons}
        if KillSwitch.REASON_OOS_FAILED in kill.reasons or KillSwitch.REASON_CONFIG_INVALID in kill.reasons:
            return {"status": "BLOCK_REAL_TRADING", "reasons": kill.reasons}
        return {"status": "READY_FOR_DRY_RUN_ONLY", "reasons": kill.reasons}

    return {"status": "READY_FOR_LIVE_PAPER", "reasons": []}


if __name__ == "__main__":
    main()
