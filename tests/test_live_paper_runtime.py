import asyncio
import json
import sqlite3
import tempfile
from pathlib import Path

from meme_king.channel_registry import ChannelRegistry
from meme_king.deterministic import stable_hash
from meme_king.execution_gate import GateConfig, GateDecision
from meme_king.hermes_trade_skill import EntryRule, ExitRule, HermesTradeSkill
from meme_king.paper_executor import FORBIDDEN_EXECUTION_FIELDS, PaperExecutor
from meme_king.strategy_profiles import STRATEGY_PROFILES
from tools.run_live_paper_runtime import (
    LivePaperRuntime,
    ReplayIngestor,
    SQLiteStateStore,
    StubDexScreenerIngestor,
    StubGMGNIngestor,
    StubPumpFunIngestor,
    StubPumpPortalIngestor,
    StubTelegramIngestor,
    normalize_event,
)


def test_normalize_event_deterministic():
    registry = ChannelRegistry()
    event = {
        "source": "telegram",
        "channel_name": "WaveX Call - Multichain",
        "token_symbol": "TEST",
        "confidence": 0.75,
        "timestamp": "2026-05-25T12:00:00Z",
    }
    sig1 = normalize_event(event, registry)
    sig2 = normalize_event(event, registry)
    assert sig1 is not None
    assert sig1["signal_key"] == sig2["signal_key"]
    assert sig1["channel_name"] == "WaveX Call - Multichain"
    assert sig1["token_symbol"] == "TEST"


def test_normalize_event_rejects_unknown_channel():
    registry = ChannelRegistry()
    event = {
        "source": "telegram",
        "channel_name": "Random Scam Channel",
        "token_symbol": "BAD",
        "confidence": 0.9,
    }
    sig = normalize_event(event, registry)
    assert sig is None


def test_normalize_event_maps_stub_sources():
    registry = ChannelRegistry()
    assert normalize_event({"source": "dexscreener", "token_symbol": "X"}, registry)["channel_name"] == "WaveX Call - Multichain"
    assert normalize_event({"source": "gmgn", "token_symbol": "X"}, registry)["channel_name"] == "GMGN Featured Signals(Lv1) - SOL"
    assert normalize_event({"source": "pumpportal", "token_symbol": "X"}, registry)["channel_name"] == "WhaleSignal Meme Coin"
    assert normalize_event({"source": "pumpfun", "token_symbol": "X"}, registry)["channel_name"] == "Twitter @pumpdotfun (alpha)"


def test_sqlite_state_store_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteStateStore(db_path)

        store.save_seen_key("key1")
        store.commit()
        assert "key1" in store.load_seen_keys()

        store.save_cooldown("tok1", 5)
        store.commit()
        assert store.load_cooldowns()["tok1"] == 5

        store.save_token_count("tok1", 3)
        store.commit()
        assert store.load_token_counts()["tok1"] == 3

        store.save_open_position("sig1", "tok1")
        store.commit()
        assert "sig1" in store.load_open_positions()

        store.save_replay_index(42)
        store.commit()
        assert store.last_replay_index() == 42

        store.close()

        # Reopen and verify persistence
        store2 = SQLiteStateStore(db_path)
        assert "key1" in store2.load_seen_keys()
        assert store2.load_cooldowns()["tok1"] == 5
        assert store2.load_token_counts()["tok1"] == 3
        assert "sig1" in store2.load_open_positions()
        assert store2.last_replay_index() == 42
        store2.close()


def test_sqlite_state_store_trim_positions():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteStateStore(db_path)
        for i in range(10):
            store.save_open_position(f"sig{i}", f"tok{i}")
        store.trim_open_positions(5)
        store.commit()
        positions = list(store.load_open_positions())
        assert len(positions) == 5
        store.close()


def test_stub_ingestors_yield_events():
    async def collect(ingestor):
        out = []
        async for ev in ingestor.events():
            out.append(ev)
        return out

    telegram = asyncio.run(collect(StubTelegramIngestor(max_events=3, interval_seconds=0)))
    assert len(telegram) == 3
    assert telegram[0]["source"] == "telegram"

    dex = asyncio.run(collect(StubDexScreenerIngestor(max_events=2, interval_seconds=0)))
    assert len(dex) == 2
    assert dex[0]["source"] == "dexscreener"

    gmgn = asyncio.run(collect(StubGMGNIngestor(max_events=2, interval_seconds=0)))
    assert len(gmgn) == 2
    assert gmgn[0]["source"] == "gmgn"

    pump = asyncio.run(collect(StubPumpPortalIngestor(max_events=1, interval_seconds=0)))
    assert len(pump) == 1

    fun = asyncio.run(collect(StubPumpFunIngestor(max_events=1, interval_seconds=0)))
    assert len(fun) == 1


def test_replay_ingestor():
    calls = [
        {"token_symbol": "A", "channel_name": "WaveX Call - Multichain"},
        {"token_symbol": "B", "channel_name": "WaveX Call - Multichain"},
    ]
    ingestor = ReplayIngestor(calls, interval_seconds=0)
    out = asyncio.run(_collect(ingestor))
    assert len(out) == 2
    assert out[0]["source"] == "replay"


async def _collect(ingestor):
    return [ev async for ev in ingestor.events()]


def test_live_runtime_gate_integration():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir) / "out"
        db_path = Path(tmpdir) / "state.db"
        ingestors = [StubTelegramIngestor(max_events=5, interval_seconds=0)]
        runtime = LivePaperRuntime(
            ingestors=ingestors,
            out_dir=out_dir,
            db_path=db_path,
            max_events=20,
        )
        asyncio.run(runtime.run())

        # Files should exist
        assert (out_dir / "live_signals.jsonl").exists()
        assert (out_dir / "live_gate_decisions.jsonl").exists()
        assert (out_dir / "live_paper_positions.jsonl").exists()
        assert (out_dir / "live_daily_summary.json").exists()

        # Daily summary must declare paper-only mode
        summary = json.loads((out_dir / "live_daily_summary.json").read_text())
        assert summary["live_trading"] is False
        assert summary["wallets"] is False
        assert summary["rpc_broadcast"] is False
        assert summary["mode"] == "live_paper_collection_only"


def test_live_runtime_no_execution_fields():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir) / "out"
        db_path = Path(tmpdir) / "state.db"
        ingestors = [StubTelegramIngestor(max_events=10, interval_seconds=0)]
        runtime = LivePaperRuntime(
            ingestors=ingestors,
            out_dir=out_dir,
            db_path=db_path,
            max_events=20,
        )
        asyncio.run(runtime.run())

        # Verify no forbidden fields appear in any JSONL output
        for path in out_dir.glob("*.jsonl"):
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    keys = set(row.keys())
                    assert keys.isdisjoint(FORBIDDEN_EXECUTION_FIELDS), f"Forbidden keys found in {path.name}: {keys & FORBIDDEN_EXECUTION_FIELDS}"


def test_live_runtime_duplicate_filtering():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir) / "out"
        db_path = Path(tmpdir) / "state.db"
        # Feed duplicate events
        raw = [
            {"source": "telegram", "channel_name": "WaveX Call - Multichain", "token_symbol": "DUP", "confidence": 0.8, "timestamp": "2026-05-25T12:00:00Z"},
            {"source": "telegram", "channel_name": "WaveX Call - Multichain", "token_symbol": "DUP", "confidence": 0.8, "timestamp": "2026-05-25T12:00:00Z"},
        ]
        ingestors = [ReplayIngestor(raw, interval_seconds=0)]
        runtime = LivePaperRuntime(
            ingestors=ingestors,
            out_dir=out_dir,
            db_path=db_path,
            max_events=10,
        )
        asyncio.run(runtime.run())

        # The gate should deduplicate; signals file should have both (pre-gate),
        # but gate decisions should only have one APPROVE (or one decision total for the duplicate)
        gate_lines = list((out_dir / "live_gate_decisions.jsonl").open("r"))
        # First event gets a decision, second is blocked as duplicate
        decisions = [json.loads(l) for l in gate_lines if l.strip()]
        assert len(decisions) <= 2
        reasons = [r for d in decisions for r in d.get("reasons", [])]
        assert "DUPLICATE_SIGNAL" in reasons or len(decisions) == 1


def test_live_runtime_paper_trade_generation():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir) / "out"
        db_path = Path(tmpdir) / "state.db"
        # High-confidence clean event that should pass gate + skill
        raw = [
            {"source": "telegram", "channel_name": "WaveX Call - Multichain", "token_symbol": "WIN", "confidence": 0.9, "raw_text": "clean", "timestamp": "2026-05-25T12:00:00Z"},
        ]
        ingestors = [ReplayIngestor(raw, interval_seconds=0)]
        runtime = LivePaperRuntime(
            ingestors=ingestors,
            out_dir=out_dir,
            db_path=db_path,
            max_events=10,
        )
        asyncio.run(runtime.run())

        positions = list((out_dir / "live_paper_positions.jsonl").open("r"))
        assert len(positions) >= 1
        pos = json.loads(positions[0])
        assert pos["status"] == "closed"
        assert "entry_price" in pos
        assert "channel_name" in pos


def test_live_runtime_rolling_summary():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir) / "out"
        db_path = Path(tmpdir) / "state.db"
        ingestors = [StubTelegramIngestor(max_events=3, interval_seconds=0)]
        runtime = LivePaperRuntime(
            ingestors=ingestors,
            out_dir=out_dir,
            db_path=db_path,
            max_events=10,
        )
        asyncio.run(runtime.run())

        summary_path = out_dir / "live_daily_summary.json"
        assert summary_path.exists()
        summary = json.loads(summary_path.read_text())
        assert "signals_logged" in summary
        assert "gate_decisions_logged" in summary
        assert "paper_positions_logged" in summary
        assert "total_events_processed" in summary
        assert summary["ingestors"] == ["StubTelegramIngestor"]
