from meme_king.scorecard import build_scorecard


def test_scorecard_computes_channel_metrics():
    scorecard = build_scorecard(
        [
            {"channel_name": "WaveX Call - Multichain", "timestamp": "2026-05-01T00:00:00Z", "token_symbol": "ABC", "historical_max_x": 2.0, "confidence": 0.8},
            {"channel_name": "WaveX Call - Multichain", "timestamp": "2026-05-02T00:00:00Z", "token_symbol": "ABC", "historical_max_x": 1.0, "confidence": 0.6},
        ]
    )

    channel = scorecard["channels"]["WaveX Call - Multichain"]
    assert channel["winrate"] == 0.5
    assert channel["signal_clustering"]["largest_cluster"] == 2

