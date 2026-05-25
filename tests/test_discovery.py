import json

from meme_king.channel_registry import ChannelRegistry
from tools.discover_old_meme_queen_data import discover


def test_discovery_finds_candidate_jsonl(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    source = data_dir / "signals.jsonl"
    source.write_text(json.dumps({"channel": "WaveX Call - Multichain [T:25176]", "ticker": "TEST"}) + "\n", encoding="utf-8")

    sources = discover(tmp_path, ChannelRegistry())

    assert len(sources) == 1
    assert sources[0]["matched_records"] == 1

