import json
import tempfile
from pathlib import Path

from meme_king.dry_run_executor import DryRunExecutor
from meme_king.live_executor_interface import TradeIntent
from meme_king.live_trading_config import ExecutionFlags, LiveTradingConfig, RiskLimits


def test_dry_run_does_not_send_transactions():
    config = LiveTradingConfig(flags=ExecutionFlags(), risk=RiskLimits())
    with tempfile.TemporaryDirectory() as tmpdir:
        executor = DryRunExecutor(config=config, out_dir=Path(tmpdir))
        intent = TradeIntent(
            signal_id="sig1",
            channel_name="WaveX Call - Multichain",
            token_symbol="TEST",
            mint_address=None,
            side="buy",
            quantity_sol=0.01,
            slippage_bps=1500,
            priority_fee_microlamports=50000,
            jito_tip_lamports=0,
            reason="test",
        )
        quote = executor.build_quote_plan(intent)
        plan = executor.build_transaction_plan(quote)
        result = executor.simulate_transaction(plan)

        assert result.mode == "dry_run"
        assert result.transaction_signature is None
        assert result.success in (True, False)

        with pytest.raises(RuntimeError):
            executor.submit_transaction(plan)


def test_dry_run_produces_artifacts():
    config = LiveTradingConfig(flags=ExecutionFlags(), risk=RiskLimits())
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)
        executor = DryRunExecutor(config=config, out_dir=out_dir)
        intent = TradeIntent(
            signal_id="sig1",
            channel_name="WaveX Call - Multichain",
            token_symbol="TEST",
            mint_address=None,
            side="buy",
            quantity_sol=0.01,
            slippage_bps=1500,
            priority_fee_microlamports=50000,
            jito_tip_lamports=0,
            reason="test",
        )
        executor.execute_intent(intent)
        summary = executor.write_summary()

        assert (out_dir / "dry_run_quotes.jsonl").exists()
        assert (out_dir / "dry_run_transaction_plans.jsonl").exists()
        assert (out_dir / "dry_run_results.jsonl").exists()
        assert (out_dir / "dry_run_summary.json").exists()
        assert summary["quotes_planned"] == 1
        assert summary["transactions_planned"] == 1
        assert summary["live_trading"] is False


def test_dry_run_placeholder_not_real_tx():
    config = LiveTradingConfig(flags=ExecutionFlags(), risk=RiskLimits())
    with tempfile.TemporaryDirectory() as tmpdir:
        executor = DryRunExecutor(config=config, out_dir=Path(tmpdir))
        intent = TradeIntent(
            signal_id="sig1",
            channel_name="WaveX Call - Multichain",
            token_symbol="TEST",
            mint_address=None,
            side="buy",
            quantity_sol=0.01,
            slippage_bps=1500,
            priority_fee_microlamports=50000,
            jito_tip_lamports=0,
            reason="test",
        )
        quote = executor.build_quote_plan(intent)
        plan = executor.build_transaction_plan(quote)
        assert plan.serialized_transaction.startswith("DRY_RUN_PLACEHOLDER_")
        assert plan.signer_required is False


def test_dry_run_no_private_key_in_artifacts():
    config = LiveTradingConfig(
        flags=ExecutionFlags(),
        risk=RiskLimits(),
        wallet_keypair_path="/fake/path.json",
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        executor = DryRunExecutor(config=config, out_dir=Path(tmpdir))
        intent = TradeIntent(
            signal_id="sig1",
            channel_name="WaveX Call - Multichain",
            token_symbol="TEST",
            mint_address=None,
            side="buy",
            quantity_sol=0.01,
            slippage_bps=1500,
            priority_fee_microlamports=50000,
            jito_tip_lamports=0,
            reason="test",
        )
        executor.execute_intent(intent)
        executor.write_summary()

        for path in Path(tmpdir).glob("*.jsonl"):
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    text = json.dumps(row)
                    assert "private_key" not in text.lower()
                    assert "secret" not in text.lower()


import pytest
