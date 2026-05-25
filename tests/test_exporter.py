import json

from meme_king.channel_registry import ChannelRegistry
from meme_king.schemas import normalize_call


def test_normalize_call_keeps_only_allowlisted_channel():
    registry = ChannelRegistry()
    record = {
        "channel": "GMGN Featured Signals(Lv1) - SOL [T:3847543]",
        "timestamp": "2026-05-16T00:00:00Z",
        "ticker": "KING",
        "score": 0.75,
        "message": "$KING historical call",
    }

    call = normalize_call(record, "fixture.jsonl", registry)

    assert call["channel_name"] == "GMGN Featured Signals(Lv1) - SOL"
    assert call["token_symbol"] == "KING"
    assert call["confidence"] == 0.75


def test_normalize_call_rejects_non_allowlisted_channel():
    registry = ChannelRegistry()
    record = {"channel": "Other Calls", "ticker": "NOPE"}

    assert normalize_call(record, "fixture.jsonl", registry) is None

