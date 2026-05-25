from meme_king.channel_registry import ChannelRegistry


def test_allowlist_accepts_top4_aliases():
    registry = ChannelRegistry()
    assert registry.match("WaveX Call - Multichain [T:25176]").canonical_name == "WaveX Call - Multichain"
    assert registry.match("Twitter @pumpdotfun (α)").canonical_name == "Twitter @pumpdotfun (alpha)"
    assert registry.match("GMGN Featured Signals(Lv1) - SOL [T:3847543]").canonical_name == "GMGN Featured Signals(Lv1) - SOL"
    assert registry.match("WhaleSignal Meme Coin").canonical_name == "WhaleSignal Meme Coin"


def test_allowlist_rejects_other_channels():
    registry = ChannelRegistry()
    assert registry.match("Solana Degen Hub [T:671]") is None
    assert registry.match("GMGN Featured Signals(Lv2) - SOL [T:4437230]") is None

