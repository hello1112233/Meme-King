from __future__ import annotations

import re
from typing import Any

from .channel_registry import ChannelMatch, ChannelRegistry, find_channel_in_record
from .deterministic import parse_timestamp, stable_hash, utc_now_iso


MINT_RE = re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b")
SYMBOL_RE = re.compile(r"(?:\$|ticker['\"]?:\s*['\"]?|symbol['\"]?:\s*['\"]?)([A-Za-z0-9_]{2,16})")


def first_value(record: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


def text_blob(record: dict[str, Any]) -> str:
    parts = []
    for key in ("raw_text", "text", "message", "body", "recommendation", "reason", "reject_reason", "caveat", "bypass_reason"):
        value = record.get(key)
        if value not in (None, ""):
            parts.append(str(value))
    if not parts:
        parts.append(str(record))
    return "\n".join(parts)


def extract_symbol(record: dict[str, Any], raw_text: str) -> str | None:
    value = first_value(record, ["token_symbol", "symbol", "ticker", "base_symbol", "name"])
    if value not in (None, "", "UNKNOWN"):
        return str(value).strip().lstrip("$")[:32]
    match = SYMBOL_RE.search(raw_text)
    return match.group(1).upper() if match else None


def extract_mint(record: dict[str, Any], raw_text: str) -> str | None:
    value = first_value(record, ["mint_address", "mint", "token_address", "address", "ca", "contract_address"])
    if value not in (None, ""):
        return str(value).strip()
    match = MINT_RE.search(raw_text)
    return match.group(0) if match else None


def normalize_call(record: dict[str, Any], source_file: str, registry: ChannelRegistry) -> dict[str, Any] | None:
    match: ChannelMatch | None = find_channel_in_record(record, registry)
    if not match:
        return None
    raw_text = text_blob(record)
    timestamp = parse_timestamp(first_value(record, ["timestamp", "created_at", "recorded_at", "time", "unix", "received_at", "inserted_at"]))
    confidence = first_value(record, ["confidence", "score", "confidence_score"])
    max_x = first_value(record, ["historical_max_x", "max_x", "peak_x", "avg_peak", "best_multiplier", "multiplier"])
    winrate = first_value(record, ["historical_winrate", "winrate", "wr", "win_rate"])
    historical_score = first_value(record, ["historical_score", "score", "quality_score"])
    normalized = {
        "channel_name": match.canonical_name,
        "channel_id": match.channel_id,
        "message_id": first_value(record, ["message_id", "id", "event_id", "deterministic_id"]),
        "timestamp": timestamp,
        "token_symbol": extract_symbol(record, raw_text),
        "mint_address": extract_mint(record, raw_text),
        "chain": first_value(record, ["chain", "network", "mode_chain"]) or infer_chain(match.canonical_name, raw_text),
        "raw_text": raw_text,
        "source_file": source_file,
        "confidence": to_float(confidence),
        "historical_score": to_float(historical_score),
        "historical_winrate": to_float(winrate),
        "historical_max_x": to_float(max_x),
        "replayable": bool(timestamp or extract_symbol(record, raw_text) or extract_mint(record, raw_text)),
        "created_at": utc_now_iso(),
    }
    if not normalized["message_id"]:
        normalized["message_id"] = stable_hash({k: normalized[k] for k in ("channel_name", "timestamp", "token_symbol", "mint_address", "raw_text")})[:16]
    return normalized


def infer_chain(channel_name: str, raw_text: str) -> str | None:
    text = f"{channel_name} {raw_text}".casefold()
    if "sol" in text or "pump" in text:
        return "solana"
    if "multichain" in text:
        return "multichain"
    return None


def to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("%", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    number = float(match.group(0))
    if "%" in str(value) and number > 1:
        return number / 100
    return number

