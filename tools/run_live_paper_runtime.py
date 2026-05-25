#!/usr/bin/env python3
"""Minimal realtime paper ingestion runtime for Meme King.

Collects signals continuously for 7–14 days to build temporal diversity
for Hermes trade skill OOS validation. No real trading.

Design constraints (M1 Mac Mini 8GB):
- Append-only JSONL (never rewrite logs)
- SQLite WAL for state/dedup
- Bounded asyncio.Queue(maxsize=1000) for backpressure
- No large in-memory datasets
- No LLM inference
- Async-friendly ingestor architecture
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from abc import ABC, abstractmethod
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meme_king.channel_registry import ChannelRegistry
from meme_king.deterministic import read_json, read_jsonl, rel, stable_hash, utc_now_iso
from meme_king.execution_gate import ExecutionGate, GateConfig, GateDecision
from meme_king.hermes_trade_skill import EntryRule, ExitRule, HermesTradeSkill
from meme_king.paper_executor import PaperExecutor
from meme_king.strategy_profiles import STRATEGY_PROFILES

MAX_QUEUE_SIZE = 1000
MAX_MEMORY_CACHE = 5000


# ---------------------------------------------------------------------------
# SQLite persistence layer (WAL mode)
# ---------------------------------------------------------------------------

class SQLiteStateStore:
    """Append-only friendly SQLite store with WAL mode."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(db_path), check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS seen_signal_keys (
                signal_key TEXT PRIMARY KEY,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS cooldowns (
                token_key TEXT PRIMARY KEY,
                replay_index INTEGER,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS open_positions (
                signal_id TEXT PRIMARY KEY,
                token_key TEXT,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS token_counts (
                token_key TEXT PRIMARY KEY,
                count INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS replay_index (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_index INTEGER DEFAULT 0
            );
            INSERT OR IGNORE INTO replay_index (id, last_index) VALUES (1, 0);
            """
        )
        self.db.commit()

    def load_seen_keys(self) -> set[str]:
        cursor = self.db.execute("SELECT signal_key FROM seen_signal_keys")
        return {row[0] for row in cursor.fetchall()}

    def save_seen_key(self, signal_key: str) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO seen_signal_keys (signal_key, created_at) VALUES (?, ?)",
            (signal_key, utc_now_iso()),
        )

    def load_cooldowns(self) -> dict[str, int]:
        cursor = self.db.execute("SELECT token_key, replay_index FROM cooldowns")
        return {row[0]: row[1] for row in cursor.fetchall()}

    def save_cooldown(self, token_key: str, replay_index: int) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO cooldowns (token_key, replay_index, updated_at) VALUES (?, ?, ?)",
            (token_key, replay_index, utc_now_iso()),
        )

    def load_open_positions(self) -> deque[str]:
        cursor = self.db.execute("SELECT signal_id FROM open_positions ORDER BY rowid")
        return deque((row[0] for row in cursor.fetchall()), maxlen=MAX_MEMORY_CACHE)

    def save_open_position(self, signal_id: str, token_key: str) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO open_positions (signal_id, token_key, updated_at) VALUES (?, ?, ?)",
            (signal_id, token_key, utc_now_iso()),
        )

    def trim_open_positions(self, max_positions: int) -> None:
        self.db.execute(
            """DELETE FROM open_positions
               WHERE rowid NOT IN (
                   SELECT rowid FROM open_positions ORDER BY rowid DESC LIMIT ?
               )""",
            (max_positions,),
        )

    def load_token_counts(self) -> Counter:
        cursor = self.db.execute("SELECT token_key, count FROM token_counts")
        return Counter({row[0]: row[1] for row in cursor.fetchall()})

    def save_token_count(self, token_key: str, count: int) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO token_counts (token_key, count) VALUES (?, ?)",
            (token_key, count),
        )

    def last_replay_index(self) -> int:
        cursor = self.db.execute("SELECT last_index FROM replay_index WHERE id = 1")
        row = cursor.fetchone()
        return row[0] if row else 0

    def save_replay_index(self, index: int) -> None:
        self.db.execute("UPDATE replay_index SET last_index = ? WHERE id = 1", (index,))

    def commit(self) -> None:
        self.db.commit()

    def close(self) -> None:
        self.db.close()


# ---------------------------------------------------------------------------
# Persistent Execution Gate
# ---------------------------------------------------------------------------

class PersistentExecutionGate:
    """Wraps ExecutionGate with SQLite-backed state for live runtime restarts."""

    def __init__(
        self,
        store: SQLiteStateStore,
        scorecard: dict[str, Any] | None = None,
        strategy_comparison: dict[str, Any] | None = None,
        profile: Any | None = None,
        config: GateConfig | None = None,
        registry: ChannelRegistry | None = None,
    ) -> None:
        self.store = store
        self.gate = ExecutionGate(scorecard, strategy_comparison, profile, config, registry)
        self._restore_state()
        self.replay_index = store.last_replay_index()

    def _restore_state(self) -> None:
        self.gate.seen_signal_keys = self.store.load_seen_keys()
        self.gate.cooldowns = self.store.load_cooldowns()
        self.gate.open_positions = self.store.load_open_positions()
        self.gate.token_counts = self.store.load_token_counts()

    def review(self, signal: dict[str, Any]) -> Any:
        self.replay_index += 1
        review = self.gate.review(signal, self.replay_index)
        # Persist mutated state
        self.store.save_replay_index(self.replay_index)
        self.store.save_seen_key(self.gate.signal_key(signal))
        token_key = self.gate.token_key(signal)
        self.store.save_cooldown(token_key, self.replay_index)
        self.store.save_token_count(token_key, self.gate.token_counts[token_key])
        if review.decision == GateDecision.APPROVE_FOR_PAPER.value:
            self.store.save_open_position(review.signal_id, token_key)
            self.store.trim_open_positions(self.gate.config.max_open_paper_positions)
        self.store.commit()
        return review


# ---------------------------------------------------------------------------
# Ingestors (async-friendly, stub implementations for minimal footprint)
# ---------------------------------------------------------------------------

class Ingestor(ABC):
    @abstractmethod
    async def events(self) -> AsyncIterator[dict[str, Any]]:
        """Yield raw events."""
        ...


class StubTelegramIngestor(Ingestor):
    def __init__(self, max_events: int = 10, interval_seconds: float = 0.1) -> None:
        self.max_events = max_events
        self.interval_seconds = interval_seconds

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        for i in range(self.max_events):
            await asyncio.sleep(self.interval_seconds)
            yield {
                "source": "telegram",
                "channel_name": "WaveX Call - Multichain",
                "message_id": f"tg_{i}",
                "timestamp": utc_now_iso(),
                "token_symbol": f"MOCK{i}",
                "mint_address": None,
                "confidence": 0.75,
                "raw_text": "clean signal",
            }


class StubDexScreenerIngestor(Ingestor):
    def __init__(self, max_events: int = 5, interval_seconds: float = 0.2) -> None:
        self.max_events = max_events
        self.interval_seconds = interval_seconds

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        for i in range(self.max_events):
            await asyncio.sleep(self.interval_seconds)
            yield {
                "source": "dexscreener",
                "token_symbol": f"DEX{i}",
                "mint_address": f"Dex{i}111111111111111111111111111111111111111",
                "market_cap": 50000 + i * 1000,
                "liquidity_usd": 10000 + i * 500,
                "confidence": 0.6,
                "raw_text": "liquidity verified",
                "timestamp": utc_now_iso(),
            }


class StubPumpPortalIngestor(Ingestor):
    def __init__(self, max_events: int = 3, interval_seconds: float = 0.3) -> None:
        self.max_events = max_events
        self.interval_seconds = interval_seconds

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        for i in range(self.max_events):
            await asyncio.sleep(self.interval_seconds)
            yield {
                "source": "pumpportal",
                "token_symbol": f"PUMP{i}",
                "mint_address": None,
                "confidence": 0.55,
                "raw_text": "new launch",
                "timestamp": utc_now_iso(),
            }


class StubGMGNIngestor(Ingestor):
    def __init__(self, max_events: int = 3, interval_seconds: float = 0.3) -> None:
        self.max_events = max_events
        self.interval_seconds = interval_seconds

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        for i in range(self.max_events):
            await asyncio.sleep(self.interval_seconds)
            yield {
                "source": "gmgn",
                "token_symbol": f"GMGN{i}",
                "mint_address": None,
                "confidence": 0.8,
                "raw_text": "meets confidence heuristics",
                "timestamp": utc_now_iso(),
            }


class StubPumpFunIngestor(Ingestor):
    def __init__(self, max_events: int = 2, interval_seconds: float = 0.5) -> None:
        self.max_events = max_events
        self.interval_seconds = interval_seconds

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        for i in range(self.max_events):
            await asyncio.sleep(self.interval_seconds)
            yield {
                "source": "pumpfun",
                "token_symbol": f"GRAD{i}",
                "mint_address": None,
                "confidence": 0.65,
                "raw_text": "graduation event",
                "timestamp": utc_now_iso(),
            }


class ReplayIngestor(Ingestor):
    """Replays existing normalized calls as a mock live feed."""

    def __init__(self, calls: list[dict[str, Any]], interval_seconds: float = 0.01) -> None:
        self.calls = calls
        self.interval_seconds = interval_seconds

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        for call in self.calls:
            await asyncio.sleep(self.interval_seconds)
            yield {**call, "source": "replay"}


# ---------------------------------------------------------------------------
# Normalizer
# ---------------------------------------------------------------------------

def normalize_event(event: dict[str, Any], registry: ChannelRegistry) -> dict[str, Any] | None:
    """Convert a raw ingestor event into the normalized signal format."""
    channel_name = event.get("channel_name")
    if not channel_name:
        source = event.get("source", "unknown")
        # Map known stub sources to allowlisted channels
        if source == "dexscreener":
            channel_name = "WaveX Call - Multichain"
        elif source == "gmgn":
            channel_name = "GMGN Featured Signals(Lv1) - SOL"
        elif source == "pumpportal":
            channel_name = "WhaleSignal Meme Coin"
        elif source == "pumpfun":
            channel_name = "Twitter @pumpdotfun (alpha)"
        elif source == "telegram":
            channel_name = "WaveX Call - Multichain"
        else:
            match = registry.match(source)
            if match:
                channel_name = match.canonical_name

    if not channel_name:
        return None

    # Reject non-allowlisted channels
    if channel_name not in registry.allowed_names():
        return None

    token = event.get("token_symbol") or event.get("ticker")
    mint = event.get("mint_address") or event.get("token_address")
    confidence = event.get("confidence") or event.get("score") or event.get("historical_score")

    signal_key = stable_hash(
        {
            "channel_name": channel_name,
            "token": token,
            "mint": mint,
            "timestamp": event.get("timestamp"),
            "source": event.get("source"),
        }
    )

    return {
        "signal_key": signal_key,
        "source": event.get("source", "unknown"),
        "channel_name": channel_name,
        "token_symbol": token,
        "mint_address": mint,
        "confidence": confidence,
        "raw_text": str(event.get("raw_text", "")),
        "timestamp": event.get("timestamp") or utc_now_iso(),
        "message_id": event.get("message_id") or signal_key[:16],
        "historical_max_x": event.get("historical_max_x"),
        "replayable": bool(token or mint),
        "liquidity_usd": event.get("liquidity_usd"),
        "market_cap": event.get("market_cap"),
    }


# ---------------------------------------------------------------------------
# Live Paper Runtime
# ---------------------------------------------------------------------------

class LivePaperRuntime:
    """Minimal realtime paper ingestion runtime."""

    def __init__(
        self,
        ingestors: list[Ingestor],
        out_dir: Path,
        db_path: Path,
        max_events: int | None = None,
        duration_seconds: float | None = None,
    ) -> None:
        self.ingestors = ingestors
        self.out_dir = out_dir
        self.db_path = db_path
        self.max_events = max_events
        self.duration_seconds = duration_seconds
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
        self.event_count = 0
        self.start_time: float | None = None

        self.out_dir.mkdir(parents=True, exist_ok=True)

        self.registry = ChannelRegistry()
        self.store = SQLiteStateStore(db_path)

        scorecard = read_json(rel("artifacts/channel_scorecard.json"), default={"channels": {}})
        strategy_comparison = read_json(
            rel("artifacts/paper_trading/strategy_comparison.json"), default={}
        )
        self.channel_performance = read_json(
            rel("artifacts/paper_trading/channel_performance.json"), default={}
        )
        profile = STRATEGY_PROFILES["balanced"]
        config = GateConfig(confidence_threshold=profile.min_confidence)

        self.gate = PersistentExecutionGate(
            self.store,
            scorecard=scorecard,
            strategy_comparison=strategy_comparison,
            profile=profile,
            config=config,
            registry=self.registry,
        )

        self.skill = self._load_skill()
        self.executor = PaperExecutor(
            take_profit_x=profile.take_profit_x,
            stop_loss_x=profile.stop_loss_x,
            max_hold_steps=profile.max_hold_steps,
        )

        self.signals_file = self.out_dir / "live_signals.jsonl"
        self.gate_file = self.out_dir / "live_gate_decisions.jsonl"
        self.positions_file = self.out_dir / "live_paper_positions.jsonl"

    def _load_skill(self) -> HermesTradeSkill:
        rules = read_json(rel("artifacts/hermes_trade_skill/skill_rules.json"), default={})
        entry = rules.get("entry_rule") or {}
        exit_r = rules.get("exit_rule") or {}
        return HermesTradeSkill(
            EntryRule(
                min_confidence=float(entry.get("min_confidence", 0.0)),
                allowed_channels=list(entry.get("allowed_channels", [])),
                max_signal_age=int(entry.get("max_signal_age", 999999999)),
                strategy_profile=str(entry.get("strategy_profile", "balanced")),
                cooldown_seconds=int(entry.get("cooldown_seconds", 0)),
                duplicate_window_seconds=int(entry.get("duplicate_window_seconds", 0)),
                min_channel_winrate=float(entry.get("min_channel_winrate", 0.0)),
                min_channel_trades=int(entry.get("min_channel_trades", 25)),
            ),
            ExitRule(
                stop_loss_pct=float(exit_r.get("stop_loss_pct", 0.3)),
                take_profit_pct=float(exit_r.get("take_profit_pct", 0.5)),
                max_hold_seconds=int(exit_r.get("max_hold_seconds", 7200)),
            ),
        )

    async def _produce(self, ingestor: Ingestor) -> None:
        async for event in ingestor.events():
            if self._should_stop():
                break
            try:
                await asyncio.wait_for(self.queue.put(event), timeout=1.0)
            except asyncio.TimeoutError:
                # Backpressure: queue full, drop event
                pass

    def _should_stop(self) -> bool:
        if self.max_events is not None and self.event_count >= self.max_events:
            return True
        if self.duration_seconds is not None and self.start_time is not None:
            elapsed = asyncio.get_event_loop().time() - self.start_time
            if elapsed >= self.duration_seconds:
                return True
        return False

    async def _consume(self) -> None:
        while not self._should_stop():
            try:
                event = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            self.event_count += 1
            await self._process_event(event)
            self.queue.task_done()

    async def _process_event(self, event: dict[str, Any]) -> None:
        signal = normalize_event(event, self.registry)
        if not signal:
            return

        self._append_jsonl(self.signals_file, signal)

        review = self.gate.review(signal)
        self._append_jsonl(self.gate_file, review.to_dict())

        if review.decision != GateDecision.APPROVE_FOR_PAPER.value:
            return

        perf = self.channel_performance.get(signal["channel_name"], {})
        enriched = {
            **signal,
            "gate_decision_id": review.decision_id,
            "gate_reasons": review.reasons,
            "channel_winrate": float(perf.get("winrate") or 0.0),
            "channel_trades": int(perf.get("trades") or 0),
        }

        skill_decision = self.skill.decide_entry(enriched)
        if skill_decision.decision != "ENTER_PAPER":
            return

        enriched["skill_decision"] = skill_decision.decision
        enriched["skill_reasons"] = skill_decision.reasons
        enriched["skill_decision_id"] = skill_decision.decision_id

        result = self.executor.simulate_signal(enriched)
        if result:
            self._append_jsonl(self.positions_file, result["position"].to_dict())

    def _append_jsonl(self, path: Path, row: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    def _count_jsonl(self, path: Path) -> int:
        if not path.exists():
            return 0
        count = 0
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
        return count

    async def run(self) -> None:
        self.start_time = asyncio.get_event_loop().time()
        producers = [asyncio.create_task(self._produce(ing)) for ing in self.ingestors]
        consumer = asyncio.create_task(self._consume())

        await asyncio.gather(*producers)
        await self.queue.join()
        consumer.cancel()
        try:
            await consumer
        except asyncio.CancelledError:
            pass

        self._write_daily_summary()
        self.store.close()

        print(f"live_events={self.event_count}")
        print(f"live_signals={self._count_jsonl(self.signals_file)}")
        print(f"live_gate_decisions={self._count_jsonl(self.gate_file)}")
        print(f"live_paper_positions={self._count_jsonl(self.positions_file)}")
        print(f"live_daily_summary={self.out_dir / 'live_daily_summary.json'}")

    def _write_daily_summary(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        signals_count = self._count_jsonl(self.signals_file)
        gate_count = self._count_jsonl(self.gate_file)
        positions_count = self._count_jsonl(self.positions_file)

        summary = {
            "date": today,
            "mode": "live_paper_collection_only",
            "live_trading": False,
            "wallets": False,
            "rpc_broadcast": False,
            "total_events_processed": self.event_count,
            "signals_logged": signals_count,
            "gate_decisions_logged": gate_count,
            "paper_positions_logged": positions_count,
            "ingestors": [type(ing).__name__ for ing in self.ingestors],
        }

        summary_path = self.out_dir / "live_daily_summary.json"
        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False, sort_keys=True)
            f.write("\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Meme King live paper ingestion runtime")
    parser.add_argument("--out-dir", type=str, default="artifacts/live_paper")
    parser.add_argument("--db-path", type=str, default="artifacts/live_paper/live_state.db")
    parser.add_argument("--max-events", type=int, default=None)
    parser.add_argument("--duration-seconds", type=float, default=None)
    parser.add_argument("--mock-mode", action="store_true", default=False,
                        help="Use stub ingestors for testing")
    parser.add_argument("--replay-calls", action="store_true", default=False,
                        help="Replay existing normalized_calls.jsonl as mock feed")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    db_path = Path(args.db_path)

    ingestors: list[Ingestor] = []

    if args.replay_calls:
        calls = read_jsonl(rel("artifacts/normalized_calls.jsonl"))
        ingestors.append(ReplayIngestor(calls[:1000], interval_seconds=0.001))
    elif args.mock_mode:
        ingestors = [
            StubTelegramIngestor(max_events=8, interval_seconds=0.05),
            StubDexScreenerIngestor(max_events=4, interval_seconds=0.05),
            StubPumpPortalIngestor(max_events=2, interval_seconds=0.05),
            StubGMGNIngestor(max_events=2, interval_seconds=0.05),
            StubPumpFunIngestor(max_events=1, interval_seconds=0.05),
        ]
    else:
        # Default to mock mode when no real ingestors are configured
        ingestors = [
            StubTelegramIngestor(max_events=5, interval_seconds=0.1),
        ]

    runtime = LivePaperRuntime(
        ingestors=ingestors,
        out_dir=out_dir,
        db_path=db_path,
        max_events=args.max_events,
        duration_seconds=args.duration_seconds,
    )

    asyncio.run(runtime.run())


if __name__ == "__main__":
    main()
