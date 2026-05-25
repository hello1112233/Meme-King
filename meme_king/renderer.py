from __future__ import annotations

import html
import json
from typing import Any


def render_dashboard(
    replay_summary: dict[str, Any],
    rankings: list[dict[str, Any]],
    statistics: dict[str, Any],
    scorecard: dict[str, Any],
    discovered: dict[str, Any],
    normalized_count: int,
) -> str:
    top_rows = "".join(
        f"<tr><td>{html.escape(row['channel_name'])}</td><td>{row.get('records', 0)}</td><td>{row.get('replayable', 0)}</td><td>{row.get('confidence_ranking')}</td></tr>"
        for row in rankings
    )
    timeline = replay_summary.get("timeline", [])[:200]
    timeline_rows = "".join(
        f"<tr><td>{item.get('replay_index')}</td><td>{html.escape(str(item.get('timestamp') or ''))}</td><td>{html.escape(item.get('channel_name') or '')}</td><td>{html.escape(str(item.get('token') or ''))}</td><td>{html.escape(str(item.get('historical_max_x') or ''))}</td></tr>"
        for item in timeline
    )
    source_rows = "".join(
        f"<tr><td>{html.escape(source.get('relative_path') or source.get('path') or '')}</td><td>{html.escape(source.get('kind') or '')}</td><td>{source.get('size_bytes', '')}</td><td>{source.get('matched_records', '')}</td></tr>"
        for source in discovered.get("sources", [])[:250]
    )
    embedded = html.escape(
        json.dumps(
            {
                "replay_summary": replay_summary,
                "statistics": statistics,
                "scorecard": scorecard,
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Meme King Observatory</title>
  <style>
    :root {{ color-scheme: light; --ink:#172026; --muted:#5b6871; --line:#d9e0e5; --panel:#f6f8f9; --accent:#006d77; --gold:#b7791f; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color:var(--ink); background:#ffffff; }}
    header {{ padding:32px 24px 20px; border-bottom:1px solid var(--line); background:#f9fbfb; }}
    main {{ padding:24px; max-width:1280px; margin:0 auto; }}
    h1 {{ margin:0 0 8px; font-size:34px; letter-spacing:0; }}
    h2 {{ margin:30px 0 12px; font-size:20px; }}
    p {{ color:var(--muted); max-width:900px; }}
    .stats {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap:12px; }}
    .stat {{ border:1px solid var(--line); border-radius:8px; padding:14px; background:var(--panel); }}
    .stat strong {{ display:block; font-size:28px; }}
    table {{ width:100%; border-collapse:collapse; font-size:14px; }}
    th, td {{ border-bottom:1px solid var(--line); padding:9px 8px; text-align:left; vertical-align:top; }}
    th {{ color:#34444d; background:#eef3f4; position:sticky; top:0; }}
    .scroll {{ max-height:460px; overflow:auto; border:1px solid var(--line); border-radius:8px; }}
    code, pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    pre {{ white-space:pre-wrap; background:#102026; color:#eef8f8; padding:16px; border-radius:8px; overflow:auto; }}
    .badge {{ display:inline-block; padding:3px 8px; border:1px solid var(--line); border-radius:999px; color:var(--accent); background:#fff; }}
  </style>
</head>
<body>
  <header>
    <h1>Meme King Observatory</h1>
    <p>Deterministic read-only replay dashboard for four allowlisted historical Telegram/Twitter intelligence channels. No trading, wallets, private keys, swaps, RPC transaction submission, or autonomous execution are present.</p>
    <span class="badge">Hermes CLI style cognition layer</span>
    <span class="badge">Replay only</span>
    <span class="badge">Portable artifacts</span>
  </header>
  <main>
    <section class="stats">
      <div class="stat"><span>Normalized Calls</span><strong>{normalized_count}</strong></div>
      <div class="stat"><span>Replayable Calls</span><strong>{replay_summary.get('replayable_calls', 0)}</strong></div>
      <div class="stat"><span>Discovered Sources</span><strong>{len(discovered.get('sources', []))}</strong></div>
      <div class="stat"><span>Allowed Channels</span><strong>{len(rankings)}</strong></div>
    </section>
    <h2>Top Channels</h2>
    <div class="scroll"><table><thead><tr><th>Channel</th><th>Records</th><th>Replayable</th><th>Confidence Ranking</th></tr></thead><tbody>{top_rows}</tbody></table></div>
    <h2>Replay Timeline</h2>
    <div class="scroll"><table><thead><tr><th>#</th><th>Timestamp</th><th>Channel</th><th>Token</th><th>Historical Max X</th></tr></thead><tbody>{timeline_rows}</tbody></table></div>
    <h2>Signal Clusters</h2>
    <pre>{html.escape(json.dumps({k: v.get('signal_clustering') for k, v in scorecard.get('channels', {}).items()}, indent=2, ensure_ascii=False, sort_keys=True))}</pre>
    <h2>Historical Multipliers</h2>
    <pre>{html.escape(json.dumps({k: v.get('best_multipliers') for k, v in scorecard.get('channels', {}).items()}, indent=2, ensure_ascii=False, sort_keys=True))}</pre>
    <h2>Deterministic Stats</h2>
    <pre>{embedded}</pre>
    <h2>Replay Summaries</h2>
    <pre>{html.escape(json.dumps(replay_summary, indent=2, ensure_ascii=False, sort_keys=True))}</pre>
    <h2>Source Provenance</h2>
    <div class="scroll"><table><thead><tr><th>Source</th><th>Kind</th><th>Bytes</th><th>Matched Records</th></tr></thead><tbody>{source_rows}</tbody></table></div>
    <h2>Cognition Overview</h2>
    <p>The cognition layer ranks channels from replayed historical evidence, token recurrence, clustering, confidence fields, and historical multiplier fields when present. It emits artifacts only; it cannot execute transactions.</p>
  </main>
</body>
</html>
"""

