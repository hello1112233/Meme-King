from __future__ import annotations

import json
import re
import sqlite3
from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Any

from .channel_performance_analyzer import HOLD_WINDOWS
from .deterministic import parse_timestamp, sqlite_readonly_uri, stable_hash


DB_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".duckdb", ".ddb"}
SEARCH_ROOTS = [
    Path("~/Desktop/meme_king/data/source_exports/").expanduser(),
    Path("~/Desktop/meme_king/artifacts/").expanduser(),
    Path("~/Desktop/meme_king_google_drive_upload/").expanduser(),
    Path("/Users/macbook/openclaw/data/"),
    Path("/Users/macbook/openclaw/artifacts/"),
    Path("/Users/macbook/openclaw/exports/"),
    Path("/Users/macbook/openclaw/reports/"),
    Path("/Users/macbook/openclaw/observatory/"),
]

MINT_COLUMNS = {"mint", "mint_address", "token_mint", "base_mint", "address", "token_address", "contract_address", "ca"}
SYMBOL_COLUMNS = {"symbol", "token_symbol", "ticker", "base_symbol"}
PRICE_COLUMNS = {"price", "price_usd", "usd_price", "close", "high", "last_price"}
LIQUIDITY_COLUMNS = {"liquidity", "liquidity_usd", "pool_liquidity"}
MARKET_CAP_COLUMNS = {"market_cap", "market_cap_usd", "mc", "mc_usd", "fdv", "fdv_usd"}
VOLUME_COLUMNS = {"volume", "volume_5m", "volume_1h", "volume_24h", "volume_usd"}
TIMESTAMP_COLUMNS = {"timestamp", "created_at", "time", "ts", "block_time", "recorded_at", "inserted_at", "alert_timestamp"}
CHANNEL_COLUMNS = {"channel", "channel_name", "source_channel", "telegram_channel"}
MESSAGE_COLUMNS = {"message", "message_id", "text", "raw_text", "body"}
SIGNAL_COLUMNS = {"signal", "signal_id", "alert", "alert_id"}
SOURCE_COLUMNS = {"source", "source_file", "origin"}
LIFECYCLE_COLUMNS = {"lifecycle", "lifecycle_state", "state", "status", "graduated", "graduation_timestamp", "pool_address"}


def load_selected_channels(config: dict[str, Any]) -> list[str]:
    return [row["canonical_name"] for row in config.get("channels", [])]


def alert_identity(alert: dict[str, Any]) -> str:
    return stable_hash(
        {
            "channel_name": alert.get("channel_name"),
            "message_id": alert.get("message_id"),
            "timestamp": alert.get("timestamp"),
            "created_at": alert.get("created_at"),
            "token_symbol": alert.get("token_symbol"),
            "mint_address": alert.get("mint_address"),
            "source_file": alert.get("source_file"),
        }
    )[:24]


def build_token_universe(calls: list[dict[str, Any]], selected_channels: list[str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str | None, str | None], dict[str, Any]] = {}
    for row in calls:
        channel = row.get("channel_name")
        if channel not in selected_channels:
            continue
        mint = clean_value(row.get("mint_address"))
        symbol = clean_value(row.get("token_symbol"))
        if not (mint or symbol):
            continue
        key = (str(channel), mint, symbol)
        timestamp = alert_timestamp(row)
        existing = grouped.setdefault(
            key,
            {
                "channel_name": channel,
                "mint_address": mint,
                "token_symbol": symbol,
                "first_alert_timestamp": timestamp,
                "alert_count": 0,
                "source_files": set(),
            },
        )
        existing["alert_count"] += 1
        if row.get("source_file"):
            existing["source_files"].add(str(row["source_file"]))
        if timestamp and (existing["first_alert_timestamp"] is None or timestamp < existing["first_alert_timestamp"]):
            existing["first_alert_timestamp"] = timestamp
    rows = []
    for row in grouped.values():
        rows.append({**row, "source_files": sorted(row["source_files"])})
    return sorted(rows, key=lambda row: (row["channel_name"], row.get("mint_address") or "", row.get("token_symbol") or ""))


def universe_mints(universe: list[dict[str, Any]]) -> set[str]:
    return {str(row["mint_address"]) for row in universe if row.get("mint_address")}


def universe_symbols(universe: list[dict[str, Any]]) -> set[str]:
    return {str(row["token_symbol"]).casefold() for row in universe if row.get("token_symbol")}


def discover_database_files(roots: list[Path] | None = None) -> list[Path]:
    files = []
    for root in roots or SEARCH_ROOTS:
        if not root.exists():
            continue
        if root.is_file() and root.suffix.lower() in DB_SUFFIXES:
            files.append(root)
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in DB_SUFFIXES:
                files.append(path)
    return sorted(set(files))


def detect_db_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".duckdb", ".ddb"}:
        return "duckdb"
    return "sqlite"


def discover_databases(paths: list[Path]) -> dict[str, Any]:
    dbs = []
    totals = {"sqlite": 0, "duckdb": 0, "tables": 0}
    for path in paths:
        db_type = detect_db_type(path)
        totals[db_type] += 1
        inventory = discover_one_database(path, db_type)
        totals["tables"] += len(inventory.get("tables", []))
        dbs.append(inventory)
    return {"databases": dbs, "totals": totals}


def discover_one_database(path: Path, db_type: str | None = None) -> dict[str, Any]:
    db_type = db_type or detect_db_type(path)
    if db_type == "duckdb":
        return discover_duckdb(path)
    return discover_sqlite(path)


def discover_sqlite(path: Path) -> dict[str, Any]:
    tables = []
    error = None
    try:
        connection = sqlite3.connect(sqlite_readonly_uri(path), uri=True)
        cursor = connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        for (table_name,) in cursor.fetchall():
            columns = sqlite_columns(connection, table_name)
            row_count = scalar_count(connection, table_name)
            tables.append(table_inventory(table_name, columns, row_count))
        connection.close()
    except sqlite3.Error as exc:
        error = str(exc)
    return {"path": str(path), "type": "sqlite", "tables": tables, "error": error}


def discover_duckdb(path: Path) -> dict[str, Any]:
    tables = []
    error = None
    try:
        import duckdb  # type: ignore

        connection = duckdb.connect(str(path), read_only=True)
        table_rows = connection.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema NOT IN ('information_schema', 'pg_catalog') ORDER BY table_name"
        ).fetchall()
        for (table_name,) in table_rows:
            columns = duckdb_columns(connection, table_name)
            row_count = duckdb_scalar_count(connection, table_name)
            tables.append(table_inventory(table_name, columns, row_count))
        connection.close()
    except Exception as exc:  # pragma: no cover - depends on optional duckdb runtime
        error = str(exc)
    return {"path": str(path), "type": "duckdb", "tables": tables, "error": error}


def table_inventory(table_name: str, columns: list[dict[str, Any]], row_count: int | None) -> dict[str, Any]:
    names = [column["name"] for column in columns]
    detected = {
        "mint": matching_columns(names, MINT_COLUMNS),
        "token_symbol": matching_columns(names, SYMBOL_COLUMNS),
        "price": matching_columns(names, PRICE_COLUMNS),
        "liquidity": matching_columns(names, LIQUIDITY_COLUMNS),
        "market_cap": matching_columns(names, MARKET_CAP_COLUMNS),
        "volume": matching_columns(names, VOLUME_COLUMNS),
        "timestamp": matching_columns(names, TIMESTAMP_COLUMNS),
        "channel": matching_columns(names, CHANNEL_COLUMNS),
        "message": matching_columns(names, MESSAGE_COLUMNS),
        "signal": matching_columns(names, SIGNAL_COLUMNS),
        "alert": [name for name in names if "alert" in name.casefold()],
        "source": matching_columns(names, SOURCE_COLUMNS),
        "lifecycle": matching_columns(names, LIFECYCLE_COLUMNS),
    }
    return {"name": table_name, "row_count": row_count, "columns": columns, "detected_columns": detected}


def sqlite_columns(connection: sqlite3.Connection, table_name: str) -> list[dict[str, Any]]:
    rows = connection.execute(f"PRAGMA table_info({quote_identifier(table_name)})").fetchall()
    return [{"name": row[1], "type": row[2]} for row in rows]


def duckdb_columns(connection: Any, table_name: str) -> list[dict[str, Any]]:
    rows = connection.execute(f"DESCRIBE {quote_identifier(table_name)}").fetchall()
    return [{"name": row[0], "type": row[1]} for row in rows]


def scalar_count(connection: sqlite3.Connection, table_name: str) -> int | None:
    try:
        return int(connection.execute(f"SELECT COUNT(*) FROM {quote_identifier(table_name)}").fetchone()[0])
    except sqlite3.Error:
        return None


def duckdb_scalar_count(connection: Any, table_name: str) -> int | None:
    try:
        return int(connection.execute(f"SELECT COUNT(*) FROM {quote_identifier(table_name)}").fetchone()[0])
    except Exception:
        return None


def extract_from_inventory(
    universe: list[dict[str, Any]],
    inventory: dict[str, Any],
    selected_channels: list[str],
) -> dict[str, Any]:
    mints = universe_mints(universe)
    symbols = universe_symbols(universe)
    outputs = {"market_snapshots": [], "channel_alerts": [], "token_lifecycle": []}
    summary = {
        "sqlite_dbs_found": 0,
        "duckdb_dbs_found": 0,
        "tables_scanned": 0,
        "tables_with_matches": 0,
        "source_rows_scanned": 0,
        "rows_extracted": 0,
        "rows_excluded": 0,
        "errors": [],
    }
    for db in inventory.get("databases", []):
        db_type = db.get("type")
        if db_type == "sqlite":
            summary["sqlite_dbs_found"] += 1
            extracted = extract_sqlite_database(Path(db["path"]), db, mints, symbols, selected_channels)
        elif db_type == "duckdb":
            summary["duckdb_dbs_found"] += 1
            extracted = extract_duckdb_database(Path(db["path"]), db, mints, symbols, selected_channels)
        else:
            continue
        merge_extraction(outputs, summary, extracted)
    return {**outputs, "summary": summary}


def extract_sqlite_database(
    path: Path,
    db_inventory: dict[str, Any],
    mints: set[str],
    symbols: set[str],
    selected_channels: list[str],
) -> dict[str, Any]:
    return _extract_database(path, db_inventory, mints, symbols, selected_channels, "sqlite")


def extract_duckdb_database(
    path: Path,
    db_inventory: dict[str, Any],
    mints: set[str],
    symbols: set[str],
    selected_channels: list[str],
) -> dict[str, Any]:
    return _extract_database(path, db_inventory, mints, symbols, selected_channels, "duckdb")


def _extract_database(
    path: Path,
    db_inventory: dict[str, Any],
    mints: set[str],
    symbols: set[str],
    selected_channels: list[str],
    db_type: str,
) -> dict[str, Any]:
    outputs = {"market_snapshots": [], "channel_alerts": [], "token_lifecycle": []}
    summary = {"tables_scanned": 0, "tables_with_matches": 0, "source_rows_scanned": 0, "rows_extracted": 0, "rows_excluded": 0, "errors": []}
    connection = None
    try:
        if db_type == "sqlite":
            connection = sqlite3.connect(sqlite_readonly_uri(path), uri=True)
            connection.row_factory = sqlite3.Row
        else:
            import duckdb  # type: ignore

            connection = duckdb.connect(str(path), read_only=True)
        for table in db_inventory.get("tables", []):
            summary["tables_scanned"] += 1
            row_count = table.get("row_count") or 0
            summary["source_rows_scanned"] += row_count
            rows = select_allowlisted_rows(connection, db_type, table, mints, symbols, selected_channels)
            if not rows:
                summary["rows_excluded"] += row_count
                continue
            summary["tables_with_matches"] += 1
            summary["rows_excluded"] += max(row_count - len(rows), 0)
            for row in rows:
                classified = classify_row(str(path), table["name"], table, row)
                for key, value in classified.items():
                    if value:
                        outputs[key].append(value)
                        summary["rows_extracted"] += 1
    except Exception as exc:
        summary["errors"].append({"source_db": str(path), "error": str(exc)})
    finally:
        if connection is not None:
            connection.close()
    return {**outputs, "summary": summary}


def select_allowlisted_rows(
    connection: Any,
    db_type: str,
    table: dict[str, Any],
    mints: set[str],
    symbols: set[str],
    selected_channels: list[str],
) -> list[dict[str, Any]]:
    detected = table.get("detected_columns", {})
    batches = []
    for column in detected.get("mint", []):
        batches.extend(batched_filters(column, sorted(mints), lower=False))
    for column in detected.get("token_symbol", []):
        batches.extend(batched_filters(column, sorted(symbols), lower=True))
    for column in detected.get("channel", []):
        batches.extend(batched_filters(column, selected_channels, lower=False))
    if not batches:
        return []
    selected: list[dict[str, Any]] = []
    seen = set()
    for filter_sql, params in batches:
        query = f"SELECT * FROM {quote_identifier(table['name'])} WHERE {filter_sql}"
        if db_type == "sqlite":
            rows = [dict(row) for row in connection.execute(query, params).fetchall()]
        else:
            result = connection.execute(query, params)
            columns = [item[0] for item in result.description]
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
        for row in rows:
            fingerprint = json.dumps(row, sort_keys=True, default=str)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            selected.append(row)
    return selected


def batched_filters(column: str, values: list[str], lower: bool, batch_size: int = 500) -> list[tuple[str, list[Any]]]:
    values = [value for value in values if value]
    if not values:
        return []
    filters = []
    for index in range(0, len(values), batch_size):
        batch = values[index : index + batch_size]
        placeholders = ", ".join(["?"] * len(batch))
        if lower:
            filters.append((f"lower(CAST({quote_identifier(column)} AS VARCHAR)) IN ({placeholders})", batch))
        else:
            filters.append((f"CAST({quote_identifier(column)} AS VARCHAR) IN ({placeholders})", batch))
    return filters


def classify_row(source_db: str, source_table: str, table: dict[str, Any], row: dict[str, Any]) -> dict[str, dict[str, Any] | None]:
    detected = table.get("detected_columns", {})
    has_market = any(detected.get(key) for key in ("price", "liquidity", "market_cap", "volume"))
    has_alert = bool(detected.get("message") or detected.get("signal") or detected.get("alert"))
    has_lifecycle = bool(detected.get("lifecycle"))
    return {
        "market_snapshots": market_snapshot(source_db, source_table, row) if has_market else None,
        "channel_alerts": channel_alert(source_db, source_table, row) if has_alert else None,
        "token_lifecycle": lifecycle_row(source_db, source_table, row) if has_lifecycle else None,
    }


def market_snapshot(source_db: str, source_table: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_db": source_db,
        "source_table": source_table,
        "mint_address": first_value(row, ["mint_address", "mint", "token_mint", "base_mint", "address", "token_address", "contract_address", "ca"]),
        "token_symbol": first_value(row, ["token_symbol", "symbol", "ticker", "base_symbol"]),
        "timestamp": parse_timestamp(first_value(row, ["timestamp", "created_at", "time", "ts", "block_time", "recorded_at", "inserted_at"])),
        "price_usd": to_float(first_value(row, ["price_usd", "usd_price", "price", "close", "high", "last_price"])),
        "liquidity_usd": to_float(first_value(row, ["liquidity_usd", "liquidity", "pool_liquidity"])),
        "market_cap_usd": to_float(first_value(row, ["market_cap_usd", "market_cap", "mc_usd", "mc", "fdv_usd", "fdv"])),
        "volume_5m": to_float(first_value(row, ["volume_5m"])),
        "volume_1h": to_float(first_value(row, ["volume_1h"])),
        "volume_24h": to_float(first_value(row, ["volume_24h", "volume"])),
        "pair_address": first_value(row, ["pair_address", "pair", "pool_address"]),
        "dex": first_value(row, ["dex", "exchange"]),
        "chain": first_value(row, ["chain", "network"]),
        "raw": row,
    }


def channel_alert(source_db: str, source_table: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_db": source_db,
        "source_table": source_table,
        "channel_name": first_value(row, ["channel_name", "channel", "source_channel", "telegram_channel"]),
        "message_id": first_value(row, ["message_id", "id", "alert_id", "signal_id"]),
        "timestamp": parse_timestamp(first_value(row, ["timestamp", "created_at", "time", "ts", "alert_timestamp", "inserted_at"])),
        "mint_address": first_value(row, ["mint_address", "mint", "token_mint", "base_mint", "address", "token_address", "contract_address", "ca"]),
        "token_symbol": first_value(row, ["token_symbol", "symbol", "ticker", "base_symbol"]),
        "raw_text": first_value(row, ["raw_text", "text", "message", "body"]),
        "raw": row,
    }


def lifecycle_row(source_db: str, source_table: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_db": source_db,
        "source_table": source_table,
        "mint_address": first_value(row, ["mint_address", "mint", "token_mint", "base_mint", "address", "token_address", "contract_address", "ca"]),
        "token_symbol": first_value(row, ["token_symbol", "symbol", "ticker", "base_symbol"]),
        "lifecycle_state": first_value(row, ["lifecycle_state", "lifecycle", "state", "status", "graduated"]),
        "graduation_timestamp": parse_timestamp(first_value(row, ["graduation_timestamp", "graduated_at"])),
        "pool_address": first_value(row, ["pool_address", "pair_address", "pool"]),
        "raw": row,
    }


def join_alerts_to_market(calls: list[dict[str, Any]], snapshots: list[dict[str, Any]], selected_channels: list[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_key = index_snapshots(snapshots)
    joined = []
    selected_alerts = 0
    skipped_no_token = 0
    skipped_no_timestamp = 0
    for alert in sorted(calls, key=lambda row: (str(row.get("timestamp") or row.get("created_at") or ""), str(row.get("channel_name") or ""))):
        if alert.get("channel_name") not in selected_channels:
            continue
        selected_alerts += 1
        mint = clean_value(alert.get("mint_address"))
        symbol = clean_value(alert.get("token_symbol"))
        if not (mint or symbol):
            skipped_no_token += 1
            continue
        alert_ts = alert_timestamp(alert)
        if not alert_ts:
            skipped_no_timestamp += 1
            continue
        candidates = candidates_for_alert(by_key, alert_ts, mint, symbol)
        performance = alert_market_performance(alert, alert_ts, candidates)
        if performance:
            joined.append(performance)
    summary = {
        "selected_alerts": selected_alerts,
        "snapshots_available": len(snapshots),
        "alert_market_joins": len(joined),
        "skipped_no_token": skipped_no_token,
        "skipped_no_timestamp": skipped_no_timestamp,
        "unjoined_alerts": selected_alerts - skipped_no_token - skipped_no_timestamp - len(joined),
    }
    return joined, summary


def candidates_for_alert(indexed: dict[str, list[tuple[Any, dict[str, Any]]]], alert_ts: str, mint: str | None, symbol: str | None) -> list[dict[str, Any]]:
    parsed = parse_datetime(alert_ts)
    if parsed is None:
        return []
    keys = [mint] if mint and indexed.get(mint) else []
    if not keys and symbol:
        symbol_key = symbol.casefold()
        if indexed.get(symbol_key):
            keys = [symbol_key]
    candidates = []
    start = parsed
    end = parsed + timedelta(seconds=HOLD_WINDOWS[-1][1])
    for key in keys:
        rows = indexed.get(key, [])
        timestamps = [item[0] for item in rows]
        left = bisect_left(timestamps, start)
        right = bisect_right(timestamps, end)
        candidates.extend(snapshot for _, snapshot in rows[left:right])
    return candidates


def alert_market_performance(alert: dict[str, Any], alert_ts: str, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    points = []
    for snapshot in candidates:
        timestamp = parse_timestamp(snapshot.get("timestamp"))
        price = to_float(snapshot.get("price_usd"))
        if not timestamp or price is None or price <= 0:
            continue
        seconds = seconds_between(alert_ts, timestamp)
        if seconds is None or seconds < 0 or seconds > HOLD_WINDOWS[-1][1]:
            continue
        points.append((seconds, price, snapshot))
    if not points:
        return None
    points.sort(key=lambda item: (item[0], item[1]))
    entry_seconds, entry_price, entry_snapshot = points[0]
    windows = {}
    for name, seconds in HOLD_WINDOWS:
        prices = [price for point_seconds, price, _ in points if point_seconds <= seconds]
        windows[f"max_price_{name}"] = max(prices) if prices else None
    max_seconds, max_price, max_snapshot = max(points, key=lambda item: item[1])
    _, min_price, _ = min(points, key=lambda item: item[1])
    max_gain_x = max_price / entry_price
    best_hold = best_hold_window(windows, entry_price)
    return {
        "alert_key": alert_identity(alert),
        "channel_name": alert.get("channel_name"),
        "message_id": alert.get("message_id"),
        "alert_timestamp": alert_ts,
        "mint_address": alert.get("mint_address"),
        "token_symbol": alert.get("token_symbol"),
        "entry_price": entry_price,
        "entry_seconds_after_alert": entry_seconds,
        **windows,
        "max_gain_pct": (max_gain_x - 1.0) * 100.0,
        "max_gain_x": max_gain_x,
        "time_to_max_seconds": max_seconds,
        "worst_drawdown_pct": (min_price / entry_price - 1.0) * 100.0,
        "best_hold_window": best_hold,
        "price_source": "historical_market_4ch",
        "source_files": sorted({entry_snapshot.get("source_db"), max_snapshot.get("source_db")} - {None}),
    }


def index_snapshots(snapshots: list[dict[str, Any]]) -> dict[str, list[tuple[Any, dict[str, Any]]]]:
    indexed: dict[str, list[tuple[Any, dict[str, Any]]]] = defaultdict(list)
    for snapshot in snapshots:
        parsed = parse_datetime(parse_timestamp(snapshot.get("timestamp")))
        if parsed is None:
            continue
        mint = clean_value(snapshot.get("mint_address"))
        symbol = clean_value(snapshot.get("token_symbol"))
        if mint:
            indexed[mint].append((parsed, snapshot))
        if symbol:
            indexed[symbol.casefold()].append((parsed, snapshot))
    return {key: sorted(rows, key=lambda item: item[0]) for key, rows in indexed.items()}


def best_hold_window(windows: dict[str, float | None], entry_price: float) -> str | None:
    candidates = []
    for name, _ in HOLD_WINDOWS:
        price = windows.get(f"max_price_{name}")
        if price is not None:
            candidates.append((name, price / entry_price))
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[1], -dict(HOLD_WINDOWS)[item[0]]))[0]


def merge_extraction(outputs: dict[str, list[dict[str, Any]]], summary: dict[str, Any], extracted: dict[str, Any]) -> None:
    for key in ("market_snapshots", "channel_alerts", "token_lifecycle"):
        outputs[key].extend(extracted.get(key, []))
    extracted_summary = extracted.get("summary", {})
    for key in ("tables_scanned", "tables_with_matches", "source_rows_scanned", "rows_extracted", "rows_excluded"):
        summary[key] += extracted_summary.get(key, 0)
    summary["errors"].extend(extracted_summary.get("errors", []))


def matching_columns(names: list[str], aliases: set[str]) -> list[str]:
    matches = []
    for name in names:
        lowered = name.casefold()
        if lowered in aliases or any(alias in lowered for alias in aliases):
            matches.append(name)
    return matches


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def first_value(row: dict[str, Any], keys: list[str]) -> Any:
    lowered = {key.casefold(): key for key in row}
    for key in keys:
        actual = lowered.get(key.casefold())
        if actual and row.get(actual) not in (None, ""):
            return row[actual]
    return None


def clean_value(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def alert_timestamp(row: dict[str, Any]) -> str | None:
    direct = parse_timestamp(row.get("timestamp"))
    if direct:
        return direct
    raw_text = str(row.get("raw_text") or "")
    for pattern in (
        r"['\"]ts['\"]\s*:\s*(\d{10,13})",
        r"['\"]alert_time['\"]\s*:\s*(\d{10,13})",
        r"['\"]other_alert_time['\"]\s*:\s*(\d{10,13})",
    ):
        match = re.search(pattern, raw_text)
        if match:
            return parse_timestamp(match.group(1))
    return parse_timestamp(row.get("created_at"))


def to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip().replace("$", "").replace(",", ""))
    except ValueError:
        return None


def seconds_between(start: str, end: str) -> int | None:
    start_dt = parse_datetime(start)
    end_dt = parse_datetime(end)
    if start_dt is None or end_dt is None:
        return None
    return int((end_dt - start_dt).total_seconds())


def parse_datetime(value: str | None) -> Any:
    if not value:
        return None
    from datetime import datetime

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def json_dumpable_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [json.loads(json.dumps(row, default=str)) for row in rows]
