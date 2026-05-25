from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .deterministic import read_json, rel


TOP4_CHANNELS = [
    {
        "canonical_name": "WhaleSignal Meme Coin",
        "channel_id": None,
        "aliases": ["WhaleSignal Meme Coin", "WhaleSignal", "Whale Signal Meme Coin", "whalesignal"],
    },
    {
        "canonical_name": "WaveX Call - Multichain",
        "channel_id": "T:25176",
        "aliases": ["WaveX Call - Multichain [T:25176]", "WaveX Call - Multichain", "WaveX", "wavex"],
    },
    {
        "canonical_name": "Twitter @pumpdotfun (alpha)",
        "channel_id": None,
        "aliases": ["Twitter @pumpdotfun (α)", "Twitter @pumpdotfun (alpha)", "@pumpdotfun", "pumpdotfun"],
    },
    {
        "canonical_name": "GMGN Featured Signals(Lv1) - SOL",
        "channel_id": "T:3847543",
        "aliases": [
            "GMGN Featured Signals(Lv1) - SOL [T:3847543]",
            "GMGN Featured Signals(Lv1) - SOL",
            "GMGN Lv1 SOL",
            "GMGN Featured Signals Lv1 SOL",
        ],
    },
]


def compact_name(value: str) -> str:
    text = value.casefold().replace("α", "alpha")
    text = re.sub(r"\[t:\d+\]", "", text)
    text = re.sub(r"[^a-z0-9@]+", "", text)
    return text


@dataclass(frozen=True)
class ChannelMatch:
    canonical_name: str
    channel_id: str | None
    matched_alias: str


class ChannelRegistry:
    def __init__(self, config_path: Path | None = None) -> None:
        data = read_json(config_path or rel("config/top4_channels.json"), default={"channels": TOP4_CHANNELS})
        self.channels: list[dict[str, Any]] = data.get("channels", TOP4_CHANNELS)
        self._aliases: list[tuple[str, dict[str, Any], str]] = []
        for channel in self.channels:
            values = [channel["canonical_name"], *(channel.get("aliases") or [])]
            if channel.get("channel_id"):
                values.append(channel["channel_id"])
            for alias in values:
                self._aliases.append((compact_name(str(alias)), channel, str(alias)))

    def match(self, value: Any) -> ChannelMatch | None:
        if value is None:
            return None
        text = str(value)
        compact = compact_name(text)
        for alias_compact, channel, alias in self._aliases:
            if alias_compact and alias_compact in compact:
                return ChannelMatch(channel["canonical_name"], channel.get("channel_id"), alias)
        topic = re.search(r"T:\d+", text)
        if topic:
            topic_text = topic.group(0)
            for channel in self.channels:
                if channel.get("channel_id") == topic_text:
                    return ChannelMatch(channel["canonical_name"], topic_text, topic_text)
        return None

    def allowed_names(self) -> set[str]:
        return {channel["canonical_name"] for channel in self.channels}

    def to_config(self) -> dict[str, Any]:
        return {
            "purpose": "Read-only allowlist for Meme King historical replay. All other channels are rejected.",
            "channels": self.channels,
        }


def find_channel_in_record(record: dict[str, Any], registry: ChannelRegistry) -> ChannelMatch | None:
    keys = [
        "channel",
        "channel_name",
        "source_channel",
        "first_channel",
        "confirmer_channel",
        "caller_channel",
        "topic_id",
        "source",
        "source_detail",
    ]
    for key in keys:
        if key in record:
            match = registry.match(record.get(key))
            if match:
                return match
    for value in record.values():
        if isinstance(value, str):
            match = registry.match(value)
            if match:
                return match
    return None

