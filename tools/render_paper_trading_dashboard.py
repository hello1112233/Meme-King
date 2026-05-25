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
    out_dir = rel("artifacts/paper_trading")
    evaluation = read_json(out_dir / "evaluation_summary.json", default={})
    channel_performance = read_json(out_dir / "channel_performance.json", default={})
    exit_reason_stats = read_json(out_dir / "exit_reason_stats.json", default={})
    strategy_comparison = read_json(out_dir / "strategy_comparison.json", default={})
    html_text = render(evaluation, channel_performance, exit_reason_stats, strategy_comparison)
    (out_dir / "index.html").write_text(html_text, encoding="utf-8")
    print(f"paper_dashboard={out_dir / 'index.html'}")


def render(
    evaluation: dict[str, Any],
    channel_performance: dict[str, Any],
    exit_reason_stats: dict[str, Any],
    strategy_comparison: dict[str, Any],
) -> str:
    overall = evaluation.get("overall", {})
    channel_rows = table_rows(channel_performance, ["trades", "winrate", "expectancy_units", "total_pnl_units", "profit_factor", "max_drawdown_units"])
    exit_rows = table_rows(exit_reason_stats, ["trades", "share", "winrate", "expectancy_units", "total_pnl_units", "profit_factor"])
    strategy_rows = "".join(
        "<tr>"
        f"<td>{esc(row.get('profile'))}</td>"
        f"<td>{row.get('trades')}</td>"
        f"<td>{row.get('winrate')}</td>"
        f"<td>{row.get('expectancy_units')}</td>"
        f"<td>{row.get('total_pnl_units')}</td>"
        f"<td>{row.get('profit_factor')}</td>"
        f"<td>{row.get('max_drawdown_units')}</td>"
        "</tr>"
        for row in strategy_comparison.get("ranking", [])
    )
    winners = trade_rows(evaluation.get("top_winners", []))
    losers = trade_rows(evaluation.get("worst_losers", []))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Meme King Paper Trading</title>
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
    <h1>Meme King Paper Trading Dashboard</h1>
    <p>Simulation-only evaluation of deterministic paper orders, fills, positions, exits, and strategy profiles. No wallet, private key, RPC broadcast, swap, or live execution is present.</p>
  </header>
  <main>
    <section class="stats">
      <div class="stat"><span>Trades</span><strong>{overall.get('trades', 0)}</strong></div>
      <div class="stat"><span>Winrate</span><strong>{overall.get('winrate', 0)}</strong></div>
      <div class="stat"><span>Expectancy</span><strong>{overall.get('expectancy_units', 0)}</strong></div>
      <div class="stat"><span>Max Drawdown</span><strong>{overall.get('max_drawdown_units', 0)}</strong></div>
    </section>
    <h2>Overall Paper Performance</h2>
    <pre>{esc(json.dumps(overall, indent=2, sort_keys=True))}</pre>
    <h2>Per-Channel Performance</h2>
    <div class="scroll"><table><thead><tr><th>Channel</th><th>Trades</th><th>Winrate</th><th>Expectancy</th><th>Total PnL</th><th>Profit Factor</th><th>Max DD</th></tr></thead><tbody>{channel_rows}</tbody></table></div>
    <h2>Exit Reason Breakdown</h2>
    <div class="scroll"><table><thead><tr><th>Reason</th><th>Trades</th><th>Share</th><th>Winrate</th><th>Expectancy</th><th>Total PnL</th><th>Profit Factor</th></tr></thead><tbody>{exit_rows}</tbody></table></div>
    <h2>Strategy Comparison</h2>
    <div class="scroll"><table><thead><tr><th>Profile</th><th>Trades</th><th>Winrate</th><th>Expectancy</th><th>Total PnL</th><th>Profit Factor</th><th>Max DD</th></tr></thead><tbody>{strategy_rows}</tbody></table></div>
    <h2>Top Simulated Winners</h2>
    <div class="scroll"><table><thead><tr><th>Channel</th><th>Token</th><th>PnL Units</th><th>PnL X</th><th>Exit</th></tr></thead><tbody>{winners}</tbody></table></div>
    <h2>Worst Simulated Losers</h2>
    <div class="scroll"><table><thead><tr><th>Channel</th><th>Token</th><th>PnL Units</th><th>PnL X</th><th>Exit</th></tr></thead><tbody>{losers}</tbody></table></div>
    <h2>Risk Notes</h2>
    <p>These results are deterministic lifecycle simulations, not live trading results. Slippage is simulated only inside strategy comparison. The evaluation uses replay artifacts and cannot sign, send, or settle transactions.</p>
  </main>
</body>
</html>
"""


def table_rows(data: dict[str, Any], keys: list[str]) -> str:
    rows = []
    for name, values in data.items():
        cells = "".join(f"<td>{esc(values.get(key))}</td>" for key in keys)
        rows.append(f"<tr><td>{esc(name)}</td>{cells}</tr>")
    return "".join(rows)


def trade_rows(rows: list[dict[str, Any]]) -> str:
    return "".join(
        "<tr>"
        f"<td>{esc(row.get('channel_name'))}</td>"
        f"<td>{esc(row.get('token_symbol') or row.get('mint_address'))}</td>"
        f"<td>{row.get('pnl_units')}</td>"
        f"<td>{row.get('pnl_x')}</td>"
        f"<td>{esc(row.get('exit_reason'))}</td>"
        "</tr>"
        for row in rows
    )


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


if __name__ == "__main__":
    main()

