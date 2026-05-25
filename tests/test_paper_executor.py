from meme_king.paper_executor import PaperExecutor
from tools.run_paper_trading_replay import build_summary


def sample_signal(**overrides):
    signal = {
        "channel_name": "WaveX Call - Multichain",
        "message_id": "msg-1",
        "timestamp": "2026-05-01T00:00:00Z",
        "created_at": "2026-05-01T00:00:00Z",
        "token_symbol": "KING",
        "mint_address": "King111111111111111111111111111111111111111",
        "source_file": "fixture.jsonl",
        "raw_text": "outcome_peak: 2.0 outcome_min: 0.9",
        "historical_max_x": None,
        "confidence": 0.8,
        "replayable": True,
    }
    signal.update(overrides)
    return signal


def test_deterministic_order_id():
    executor = PaperExecutor()
    first = executor.create_entry_order(sample_signal())
    second = executor.create_entry_order(sample_signal())

    assert first.order_id == second.order_id


def test_entry_fill_creation():
    executor = PaperExecutor()
    order = executor.create_entry_order(sample_signal())
    position, fill = executor.simulate_entry(order)

    assert fill.side == "entry"
    assert fill.fill_price == 1.0
    assert position.status == "open"


def test_exit_fill_creation():
    executor = PaperExecutor()
    order = executor.create_entry_order(sample_signal())
    position, _ = executor.simulate_entry(order)
    exit_record, exit_fill, exit_order = executor.simulate_exit(position, sample_signal())

    assert exit_order.side == "exit"
    assert exit_fill.side == "exit"
    assert exit_record.reason == "take_profit"


def test_stop_loss_trigger():
    executor = PaperExecutor()
    signal = sample_signal(raw_text="outcome_peak: 0.9 outcome_min: 0.42", historical_max_x=0.9)
    result = executor.simulate_signal(signal)

    assert result["exit"].reason == "stop_loss"


def test_take_profit_trigger():
    executor = PaperExecutor()
    result = executor.simulate_signal(sample_signal(raw_text="outcome_peak: 3.0 outcome_min: 1.0"))

    assert result["exit"].reason == "take_profit"


def test_no_wallet_private_key_rpc_fields():
    executor = PaperExecutor()
    result = executor.simulate_signal(sample_signal())
    rows = []
    rows.extend(row.to_dict() for row in result["orders"])
    rows.append(result["position"].to_dict())
    rows.extend(row.to_dict() for row in result["fills"])
    rows.append(result["exit"].to_dict())

    forbidden = {"wallet", "private_key", "rpc_url", "sendTransaction", "signed_transaction", "swap"}
    for row in rows:
        assert forbidden.isdisjoint(row.keys())


def test_repeat_run_produces_same_summary():
    executor = PaperExecutor()
    signals = [
        sample_signal(message_id="1", token_symbol="A", raw_text="outcome_peak: 2.0 outcome_min: 0.9"),
        sample_signal(message_id="2", token_symbol="B", raw_text="outcome_peak: 0.9 outcome_min: 0.5", historical_max_x=0.9),
    ]

    def run_once():
        orders = []
        positions = []
        fills = []
        exits = []
        for signal in signals:
            result = executor.simulate_signal(signal)
            orders.extend(order.to_dict() for order in result["orders"])
            positions.append(result["position"].to_dict())
            fills.extend(fill.to_dict() for fill in result["fills"])
            exits.append(result["exit"].to_dict())
        return build_summary(signals, orders, positions, fills, exits, {"channels": {}})

    assert run_once() == run_once()

