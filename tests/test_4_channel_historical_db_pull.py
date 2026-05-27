from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from meme_king.channel_performance_analyzer import ChannelPerformanceAnalyzer
from meme_king.historical_db_extractor import (
    build_token_universe,
    discover_one_database,
    extract_from_inventory,
    join_alerts_to_market,
)


SELECTED = [
    "WhaleSignal Meme Coin",
    "WaveX Call - Multichain",
    "Twitter @pumpdotfun (alpha)",
    "GMGN Featured Signals(Lv1) - SOL",
]


def alert(channel: str, symbol: str, mint: str, timestamp: str = "2026-01-01T00:00:00Z") -> dict[str, object]:
    return {
        "channel_name": channel,
        "message_id": f"{channel}-{symbol}",
        "timestamp": timestamp,
        "created_at": timestamp,
        "token_symbol": symbol,
        "mint_address": mint,
        "source_file": "fixture.jsonl",
        "replayable": True,
    }


def make_sqlite(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE prices (mint_address TEXT, token_symbol TEXT, timestamp TEXT, price_usd REAL, liquidity_usd REAL, channel_name TEXT)"
    )
    connection.execute(
        "CREATE TABLE alerts (channel_name TEXT, message_id TEXT, timestamp TEXT, mint_address TEXT, token_symbol TEXT, raw_text TEXT)"
    )
    connection.execute(
        "CREATE TABLE lifecycle (mint_address TEXT, token_symbol TEXT, lifecycle_state TEXT, graduation_timestamp TEXT, pool_address TEXT)"
    )
    connection.executemany(
        "INSERT INTO prices VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("MintA", "AAA", "2026-01-01T00:00:10Z", 1.0, 100.0, None),
            ("MintA", "AAA", "2026-01-01T00:05:00Z", 2.0, 120.0, None),
            ("MintZ", "ZZZ", "2026-01-01T00:05:00Z", 99.0, 999.0, None),
        ],
    )
    connection.executemany(
        "INSERT INTO alerts VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("WhaleSignal Meme Coin", "m1", "2026-01-01T00:00:00Z", "MintA", "AAA", "allowed"),
            ("Unrelated Channel", "m2", "2026-01-01T00:00:00Z", "MintZ", "ZZZ", "blocked"),
        ],
    )
    connection.executemany(
        "INSERT INTO lifecycle VALUES (?, ?, ?, ?, ?)",
        [
            ("MintA", "AAA", "graduated", "2026-01-01T01:00:00Z", "PoolA"),
            ("MintZ", "ZZZ", "graduated", "2026-01-01T01:00:00Z", "PoolZ"),
        ],
    )
    connection.commit()
    connection.close()


def test_token_universe_only_includes_4_selected_channels() -> None:
    universe = build_token_universe(
        [
            alert("WhaleSignal Meme Coin", "AAA", "MintA"),
            alert("Unrelated Channel", "ZZZ", "MintZ"),
        ],
        SELECTED,
    )

    assert len(universe) == 1
    assert universe[0]["channel_name"] == "WhaleSignal Meme Coin"
    assert universe[0]["mint_address"] == "MintA"


def test_sqlite_extraction_filters_by_mint_symbol_and_channel(tmp_path: Path) -> None:
    db_path = tmp_path / "history.sqlite"
    make_sqlite(db_path)
    inventory = {"databases": [discover_one_database(db_path)]}
    universe = build_token_universe([alert("WhaleSignal Meme Coin", "AAA", "MintA")], SELECTED)

    extracted = extract_from_inventory(universe, inventory, SELECTED)

    assert len(extracted["market_snapshots"]) == 2
    assert {row["mint_address"] for row in extracted["market_snapshots"]} == {"MintA"}
    assert len(extracted["channel_alerts"]) == 1
    assert extracted["channel_alerts"][0]["channel_name"] == "WhaleSignal Meme Coin"
    assert len(extracted["token_lifecycle"]) == 1
    assert extracted["token_lifecycle"][0]["mint_address"] == "MintA"
    assert extracted["summary"]["rows_excluded"] > 0


def test_unrelated_token_rows_are_excluded(tmp_path: Path) -> None:
    db_path = tmp_path / "history.sqlite"
    make_sqlite(db_path)
    inventory = {"databases": [discover_one_database(db_path)]}
    universe = build_token_universe([alert("WaveX Call - Multichain", "AAA", "MintA")], SELECTED)

    extracted = extract_from_inventory(universe, inventory, SELECTED)

    assert all(row.get("mint_address") != "MintZ" for row in extracted["market_snapshots"])
    assert all(row.get("token_symbol") != "ZZZ" for row in extracted["market_snapshots"])


def test_duckdb_extraction_filters_by_mint_symbol_if_installed(tmp_path: Path) -> None:
    duckdb = pytest.importorskip("duckdb")
    db_path = tmp_path / "history.duckdb"
    connection = duckdb.connect(str(db_path))
    connection.execute("CREATE TABLE prices (mint_address VARCHAR, token_symbol VARCHAR, timestamp VARCHAR, price_usd DOUBLE)")
    connection.execute("INSERT INTO prices VALUES ('MintA', 'AAA', '2026-01-01T00:00:10Z', 1.0)")
    connection.execute("INSERT INTO prices VALUES ('MintZ', 'ZZZ', '2026-01-01T00:00:10Z', 99.0)")
    connection.close()
    inventory = {"databases": [discover_one_database(db_path)]}
    universe = build_token_universe([alert("Twitter @pumpdotfun (alpha)", "AAA", "MintA")], SELECTED)

    extracted = extract_from_inventory(universe, inventory, SELECTED)

    assert len(extracted["market_snapshots"]) == 1
    assert extracted["market_snapshots"][0]["mint_address"] == "MintA"


def test_alert_to_market_join_only_uses_selected_channels() -> None:
    calls = [
        alert("WhaleSignal Meme Coin", "AAA", "MintA"),
        alert("Unrelated Channel", "AAA", "MintA"),
    ]
    snapshots = [
        {"mint_address": "MintA", "token_symbol": "AAA", "timestamp": "2026-01-01T00:00:10Z", "price_usd": 1.0, "source_db": "db"},
        {"mint_address": "MintA", "token_symbol": "AAA", "timestamp": "2026-01-01T00:05:00Z", "price_usd": 2.0, "source_db": "db"},
    ]

    joined, summary = join_alerts_to_market(calls, snapshots, SELECTED)

    assert summary["selected_alerts"] == 1
    assert len(joined) == 1
    assert joined[0]["channel_name"] == "WhaleSignal Meme Coin"
    assert joined[0]["max_gain_x"] == 2.0
    assert joined[0]["best_hold_window"] == "5m"


def test_fallback_to_paper_simulated_when_no_price_data() -> None:
    analyzer = ChannelPerformanceAnalyzer(SELECTED, joined_performances=[])

    row = analyzer.analyze_alert(alert("WhaleSignal Meme Coin", "AAA", "MintA"))

    assert row.price_source == "paper_simulated"
