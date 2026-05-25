from meme_king.execution_gate import ExecutionGate, GateDecision, GateReason


def scorecard():
    return {"channels": {"WaveX Call - Multichain": {"replay_frequency": 100}}}


def signal(**overrides):
    row = {
        "channel_name": "WaveX Call - Multichain",
        "message_id": "1",
        "timestamp": "2026-05-01T00:00:00Z",
        "token_symbol": "KING",
        "mint_address": "King111111111111111111111111111111111111111",
        "source_file": "fixture",
        "raw_text": "clean call",
        "confidence": 0.7,
        "replayable": True,
    }
    row.update(overrides)
    return row


def test_deterministic_decision_id():
    first = ExecutionGate(scorecard=scorecard()).review(signal())
    second = ExecutionGate(scorecard=scorecard()).review(signal())

    assert first.decision_id == second.decision_id


def test_allowlisted_channel_approval():
    review = ExecutionGate(scorecard=scorecard()).review(signal())

    assert review.decision == GateDecision.APPROVE_FOR_PAPER.value


def test_non_allowlisted_block():
    review = ExecutionGate(scorecard=scorecard()).review(signal(channel_name="Other Channel"))

    assert review.decision == GateDecision.BLOCK_FOR_RISK.value
    assert GateReason.CHANNEL_NOT_ALLOWLISTED.value in review.reasons


def test_low_confidence_watch():
    review = ExecutionGate(scorecard=scorecard()).review(signal(confidence=0.2))

    assert review.decision == GateDecision.WATCH_ONLY.value
    assert GateReason.LOW_CONFIDENCE.value in review.reasons


def test_missing_confidence_needs_more_data():
    row = signal()
    row["confidence"] = None
    review = ExecutionGate(scorecard=scorecard()).review(row)

    assert review.decision == GateDecision.NEEDS_MORE_DATA.value
    assert GateReason.MISSING_CONFIDENCE.value in review.reasons


def test_duplicate_signal_block():
    gate = ExecutionGate(scorecard=scorecard())
    gate.review(signal(), replay_index=1)
    review = gate.review(signal(), replay_index=10)

    assert review.decision == GateDecision.BLOCK_FOR_RISK.value
    assert GateReason.DUPLICATE_SIGNAL.value in review.reasons


def test_cooldown_block():
    gate = ExecutionGate(scorecard=scorecard())
    gate.review(signal(message_id="1"), replay_index=1)
    review = gate.review(signal(message_id="2"), replay_index=3)

    assert review.decision == GateDecision.BLOCK_FOR_RISK.value
    assert GateReason.COOLDOWN_ACTIVE.value in review.reasons


def test_suspicious_rug_keyword_block():
    review = ExecutionGate(scorecard=scorecard()).review(signal(raw_text="rug risk detected"))

    assert review.decision == GateDecision.BLOCK_FOR_RISK.value
    assert GateReason.SUSPICIOUS_TEXT.value in review.reasons


def test_balanced_profile_default():
    gate = ExecutionGate(scorecard=scorecard())

    assert gate.profile.name == "balanced"
    assert gate.config.confidence_threshold == 0.45


def test_no_wallet_private_key_rpc_fields():
    review = ExecutionGate(scorecard=scorecard()).review(signal()).to_dict()

    forbidden = {"wallet", "private_key", "rpc_url", "sendTransaction", "signed_transaction", "swap"}
    assert forbidden.isdisjoint(review.keys())

