#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meme_king.deterministic import read_json, read_jsonl, rel


OUT_DIR = rel("artifacts/channel_performance_4ch")


def main() -> None:
    token_rows = read_jsonl(OUT_DIR / "token_performance.jsonl")
    channel_summary = read_json(OUT_DIR / "channel_summary.json", default={"channels": {}})
    hold_summary = read_json(OUT_DIR / "hold_window_summary.json", default={})
    best_tokens = read_json(OUT_DIR / "best_tokens.json", default={"tokens": []}).get("tokens", [])
    worst_tokens = read_json(OUT_DIR / "worst_tokens.json", default={"tokens": []}).get("tokens", [])
    data_quality = read_json(OUT_DIR / "data_quality_report.json", default={})
    html_text = render(token_rows, channel_summary, hold_summary, best_tokens, worst_tokens, data_quality)
    (OUT_DIR / "index.html").write_text(html_text, encoding="utf-8")
    print(f"channel_performance_dashboard={OUT_DIR / 'index.html'}")


def render(
    token_rows: list[dict[str, Any]],
    channel_summary: dict[str, Any],
    hold_summary: dict[str, Any],
    best_tokens: list[dict[str, Any]],
    worst_tokens: list[dict[str, Any]],
    data_quality: dict[str, Any],
) -> str:
    channels = channel_summary.get("channels", {})
    source_text = ", ".join(f"{key}: {value}" for key, value in data_quality.get("price_sources", {}).items()) or "none"
    warnings = data_quality.get("warnings", [])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Meme King Four-Channel Performance</title>
  <style>
    :root {{ --ink:#182126; --muted:#596873; --line:#d8e0e5; --panel:#f6f8f7; --head:#edf3f1; --accent:#0f766e; --warn:#9a3412; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color:var(--ink); background:#fff; }}
    header {{ padding:28px 24px 18px; background:#f7faf9; border-bottom:1px solid var(--line); }}
    main {{ max-width:1320px; margin:0 auto; padding:24px; }}
    h1 {{ margin:0 0 8px; font-size:32px; letter-spacing:0; }}
    h2 {{ margin:30px 0 12px; font-size:20px; letter-spacing:0; }}
    p {{ color:var(--muted); max-width:980px; }}
    .stats {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(190px,1fr)); gap:12px; }}
    .stat {{ border:1px solid var(--line); background:var(--panel); border-radius:8px; padding:14px; min-height:84px; }}
    .stat span {{ color:var(--muted); display:block; font-size:13px; }}
    .stat strong {{ display:block; font-size:24px; margin-top:5px; word-break:break-word; }}
    .scroll {{ max-height:520px; overflow:auto; border:1px solid var(--line); border-radius:8px; }}
    table {{ width:100%; border-collapse:collapse; font-size:14px; }}
    th,td {{ padding:8px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
    th {{ background:var(--head); color:#31434b; position:sticky; top:0; }}
    .warn {{ border:1px solid #fed7aa; background:#fff7ed; color:var(--warn); border-radius:8px; padding:12px 14px; margin:8px 0; }}
    code {{ background:#edf3f1; padding:2px 5px; border-radius:4px; }}
  </style>
</head>
<body>
  <header>
    <h1>Meme King Four-Channel Historical Performance</h1>
    <p>Read-only analysis of local historical artifacts for the four allowlisted channels. No wallet, private key, swap, or transaction path is used.</p>
  </header>
  <main>
    <section class="stats">
      <div class="stat"><span>Total Alerts Analyzed</span><strong>{len(token_rows)}</strong></div>
      <div class="stat"><span>Total Tokens Analyzed</span><strong>{len({token_key(row) for row in token_rows})}</strong></div>
      <div class="stat"><span>Price Source</span><strong>{esc(source_text)}</strong></div>
      <div class="stat"><span>Best Quick Flip</span><strong>{esc(channel_summary.get('best_quick_flip_channel'))}</strong></div>
      <div class="stat"><span>Best Longer Hold</span><strong>{esc(channel_summary.get('best_longer_hold_channel'))}</strong></div>
    </section>

    <h2>Per-Channel Win Rate</h2>
    <div class="scroll">{channel_table(channels)}</div>

    <h2>Best Hold Time By Channel</h2>
    <div class="scroll">{hold_table(hold_summary.get('per_channel', {}))}</div>

    <h2>Quick Flip Ranking</h2>
    <div class="scroll">{ranking_table(channel_summary.get('quick_flip_ranking', []), 'quick_flip_score')}</div>

    <h2>Longer Hold Ranking</h2>
    <div class="scroll">{ranking_table(channel_summary.get('longer_hold_ranking', []), 'longer_hold_score')}</div>

    <h2>Per-Token Max Gains</h2>
    <div class="scroll">{token_table(token_rows[:500])}</div>

    <h2>Best Alerts</h2>
    <div class="scroll">{token_table(best_tokens)}</div>

    <h2>Worst Alerts</h2>
    <div class="scroll">{token_table(worst_tokens)}</div>

    <h2>Data Quality Warnings</h2>
    {warning_blocks(warnings)}
    <p>Results marked <code>paper_simulated</code> are deterministic replay estimates from local paper/historical fields, not true market tick or candle history.</p>
  </main>
</body>
</html>
"""


def channel_table(channels: dict[str, Any]) -> str:
    rows = []
    for name, row in channels.items():
        rows.append(
            "<tr>"
            f"<td>{esc(name)}</td>"
            f"<td>{row.get('alerts')}</td>"
            f"<td>{row.get('tokens')}</td>"
            f"<td>{pct(row.get('win_rate_25_pct'))}</td>"
            f"<td>{pct(row.get('win_rate_50_pct'))}</td>"
            f"<td>{pct(row.get('win_rate_100_pct'))}</td>"
            f"<td>{num(row.get('average_max_gain_pct'))}</td>"
            f"<td>{num(row.get('median_max_gain_pct'))}</td>"
            f"<td>{esc(row.get('best_hold_window'))}</td>"
            f"<td>{esc(json.dumps(row.get('price_sources', {}), sort_keys=True))}</td>"
            "</tr>"
        )
    return "<table><thead><tr><th>Channel</th><th>Alerts</th><th>Tokens</th><th>Win 25%</th><th>Win 50%</th><th>Win 100%</th><th>Avg Max %</th><th>Median Max %</th><th>Best Hold</th><th>Sources</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def hold_table(per_channel: dict[str, Any]) -> str:
    rows = []
    for channel, windows in per_channel.items():
        best = best_hold(windows)
        for name, row in windows.items():
            rows.append(
                "<tr>"
                f"<td>{esc(channel)}</td>"
                f"<td>{esc(name)}</td>"
                f"<td>{row.get('alerts')}</td>"
                f"<td>{pct(row.get('win_rate_25_pct'))}</td>"
                f"<td>{num(row.get('average_gain_pct'))}</td>"
                f"<td>{num(row.get('median_gain_pct'))}</td>"
                f"<td>{'yes' if name == best else ''}</td>"
                "</tr>"
            )
    return "<table><thead><tr><th>Channel</th><th>Hold</th><th>Alerts</th><th>Win 25%</th><th>Avg Gain %</th><th>Median Gain %</th><th>Best</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def ranking_table(rows: list[dict[str, Any]], key: str) -> str:
    body = "".join(
        "<tr>"
        f"<td>{index}</td>"
        f"<td>{esc(row.get('channel_name'))}</td>"
        f"<td>{num(row.get(key))}</td>"
        f"<td>{row.get('alerts')}</td>"
        "</tr>"
        for index, row in enumerate(rows, start=1)
    )
    return f"<table><thead><tr><th>Rank</th><th>Channel</th><th>{esc(key)}</th><th>Alerts</th></tr></thead><tbody>{body}</tbody></table>"


def token_table(rows: list[dict[str, Any]]) -> str:
    body = "".join(
        "<tr>"
        f"<td>{esc(row.get('channel_name'))}</td>"
        f"<td>{esc(row.get('token_symbol') or row.get('mint_address'))}</td>"
        f"<td>{num(row.get('max_gain_pct'))}</td>"
        f"<td>{num(row.get('max_gain_x'))}</td>"
        f"<td>{esc(row.get('best_hold_window'))}</td>"
        f"<td>{row.get('time_to_max_seconds')}</td>"
        f"<td>{num(row.get('worst_drawdown_pct'))}</td>"
        f"<td>{esc(row.get('price_source'))}</td>"
        "</tr>"
        for row in rows
    )
    return "<table><thead><tr><th>Channel</th><th>Token</th><th>Max Gain %</th><th>Max X</th><th>Best Hold</th><th>Time To Max Sec</th><th>Worst DD %</th><th>Source</th></tr></thead><tbody>" + body + "</tbody></table>"


def warning_blocks(warnings: list[str]) -> str:
    if not warnings:
        return "<p>No data quality warnings.</p>"
    return "".join(f"<div class=\"warn\">{esc(warning)}</div>" for warning in warnings)


def best_hold(windows: dict[str, Any]) -> str | None:
    populated = [row for row in windows.values() if row.get("average_gain_pct") is not None]
    if not populated:
        return None
    best = max(populated, key=lambda row: row.get("average_gain_pct") or -10**9)
    return best.get("hold_window")


def token_key(row: dict[str, Any]) -> str:
    return str(row.get("mint_address") or row.get("token_symbol") or "UNKNOWN")


def pct(value: Any) -> str:
    if value is None:
        return ""
    return f"{float(value) * 100:.2f}%"


def num(value: Any) -> str:
    if value is None:
        return ""
    return f"{float(value):.4f}"


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


if __name__ == "__main__":
    main()
