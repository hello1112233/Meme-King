#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meme_king.deterministic import read_json, rel


def main() -> None:
    out_dir = rel("artifacts/execution_gate")
    summary = read_json(out_dir / "gate_summary.json", default={})
    (out_dir / "index.html").write_text(render(summary), encoding="utf-8")
    print(f"gate_dashboard={out_dir / 'index.html'}")


def render(summary: dict[str, Any]) -> str:
    counts = summary.get("decision_counts", {})
    reason_rows = "".join(
        f"<tr><td>{esc(reason)}</td><td>{count}</td></tr>"
        for reason, count in summary.get("top_block_reasons", [])
    )
    channel_rows = "".join(
        "<tr>"
        f"<td>{esc(channel)}</td>"
        f"<td>{row.get('total', 0)}</td>"
        f"<td>{row.get('approved', 0)}</td>"
        f"<td>{row.get('blocked', 0)}</td>"
        f"<td>{row.get('watch_only', 0)}</td>"
        f"<td>{row.get('needs_more_data', 0)}</td>"
        f"<td>{row.get('approval_rate', 0)}</td>"
        "</tr>"
        for channel, row in summary.get("channel_approval_rates", {}).items()
    )
    suspicious_rows = "".join(
        "<tr>"
        f"<td>{esc(row.get('channel_name'))}</td>"
        f"<td>{esc(row.get('token_symbol') or row.get('mint_address'))}</td>"
        f"<td>{esc(', '.join(row.get('reasons', [])))}</td>"
        "</tr>"
        for row in summary.get("suspicious_signal_examples", [])
    )
    duplicate = summary.get("duplicate_cooldown_counts", {})
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Meme King Execution Gate</title>
  <style>
    :root {{ --ink:#172026; --muted:#5d6872; --line:#d7dee4; --panel:#f7f9fa; --accent:#006d77; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color:var(--ink); background:#fff; }}
    header {{ padding:28px 24px 18px; background:#f8fbfb; border-bottom:1px solid var(--line); }}
    main {{ max-width:1280px; margin:0 auto; padding:24px; }}
    h1 {{ margin:0 0 8px; font-size:32px; letter-spacing:0; }}
    h2 {{ margin:30px 0 12px; font-size:20px; }}
    p {{ color:var(--muted); max-width:920px; }}
    .stats {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(180px,1fr)); gap:12px; }}
    .stat {{ border:1px solid var(--line); background:var(--panel); border-radius:8px; padding:14px; }}
    .stat strong {{ display:block; font-size:26px; }}
    .scroll {{ max-height:460px; overflow:auto; border:1px solid var(--line); border-radius:8px; }}
    table {{ width:100%; border-collapse:collapse; font-size:14px; }}
    th,td {{ padding:8px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
    th {{ background:#eef3f4; color:#35464f; position:sticky; top:0; }}
    pre {{ background:#112026; color:#edf7f7; padding:16px; border-radius:8px; overflow:auto; }}
  </style>
</head>
<body>
  <header>
    <h1>Meme King Execution Gate</h1>
    <p>Paper-only risk gate using the balanced profile as the default reference. It reviews replay signals for paper approval, blocking, watch-only handling, or missing-data status. No wallet, private key, RPC broadcast, swap, or live execution is present.</p>
  </header>
  <main>
    <section class="stats">
      <div class="stat"><span>Total Decisions</span><strong>{summary.get('total_decisions', 0)}</strong></div>
      <div class="stat"><span>Approved</span><strong>{counts.get('APPROVE_FOR_PAPER', 0)}</strong></div>
      <div class="stat"><span>Blocked</span><strong>{counts.get('BLOCK_FOR_RISK', 0)}</strong></div>
      <div class="stat"><span>Watch / More Data</span><strong>{counts.get('WATCH_ONLY', 0)} / {counts.get('NEEDS_MORE_DATA', 0)}</strong></div>
    </section>
    <h2>Gate Summary</h2>
    <pre>{esc(json.dumps(summary.get('decision_counts', {}), indent=2, sort_keys=True))}</pre>
    <h2>Top Block Reasons</h2>
    <div class="scroll"><table><thead><tr><th>Reason</th><th>Count</th></tr></thead><tbody>{reason_rows}</tbody></table></div>
    <h2>Channel-Level Approval Rates</h2>
    <div class="scroll"><table><thead><tr><th>Channel</th><th>Total</th><th>Approved</th><th>Blocked</th><th>Watch</th><th>Needs Data</th><th>Approval Rate</th></tr></thead><tbody>{channel_rows}</tbody></table></div>
    <h2>Duplicate / Cooldown Counts</h2>
    <pre>{esc(json.dumps(duplicate, indent=2, sort_keys=True))}</pre>
    <h2>Suspicious Signal Examples</h2>
    <div class="scroll"><table><thead><tr><th>Channel</th><th>Token</th><th>Reasons</th></tr></thead><tbody>{suspicious_rows}</tbody></table></div>
    <h2>Risk Guardrail Notes</h2>
    <p>The gate blocks duplicate signals, active cooldowns, suspicious rug/scam text, unsupported channels, high recurrence, open-position pressure, and balanced-profile incompatibility. Low-confidence or unsupported historical context is routed to watch-only or needs-more-data instead of paper approval.</p>
  </main>
</body>
</html>
"""


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


if __name__ == "__main__":
    main()

