from meme_king.replay_engine import channel_rankings, channel_statistics, replay


def test_replay_orders_deterministically():
    calls = [
        {"channel_name": "WaveX Call - Multichain", "timestamp": "2026-05-02T00:00:00Z", "message_id": "b", "token_symbol": "B", "replayable": True},
        {"channel_name": "WhaleSignal Meme Coin", "timestamp": "2026-05-01T00:00:00Z", "message_id": "a", "token_symbol": "A", "replayable": True},
    ]

    summary = replay(calls)

    assert summary["timeline"][0]["token"] == "A"
    assert summary["channel_counts"]["WaveX Call - Multichain"] == 1


def test_channel_rankings_include_stats():
    stats = channel_statistics(
        [
            {"channel_name": "WaveX Call - Multichain", "timestamp": "2026-05-02T00:00:00Z", "message_id": "b", "token_symbol": "B", "replayable": True, "historical_max_x": 2.0, "confidence": 0.9}
        ]
    )

    rankings = channel_rankings(stats)

    assert rankings[0]["channel_name"] == "WaveX Call - Multichain"
    assert rankings[0]["winrate_at_1_5x"] == 1.0

