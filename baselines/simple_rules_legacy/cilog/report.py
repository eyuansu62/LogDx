"""
HTML report builder. Renders results/report.html with:
- Summary table at the top (compression, preservation)
- One expandable card per sample with side-by-side original vs compressed
- A small bar-chart of per-sample reductions (pure HTML/CSS, no JS libs)
"""

from __future__ import annotations

import html
from typing import Iterable


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>cilog benchmark report</title>
<style>
  :root {{
    --bg: #0d1117;
    --panel: #161b22;
    --panel-2: #1c2128;
    --border: #30363d;
    --text: #e6edf3;
    --muted: #8b949e;
    --accent: #58a6ff;
    --good: #3fb950;
    --warn: #d29922;
    --bad: #f85149;
    --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 24px;
    background: var(--bg);
    color: var(--text);
    font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  h2 {{ font-size: 16px; margin: 28px 0 12px; color: var(--muted); font-weight: 500; text-transform: uppercase; letter-spacing: 0.06em; }}
  h3 {{ font-size: 15px; margin: 0; font-weight: 600; }}
  .sub {{ color: var(--muted); font-size: 13px; margin-bottom: 20px; }}
  .headline {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin: 16px 0 8px;
  }}
  .metric {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px 16px;
  }}
  .metric .label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }}
  .metric .value {{ font-size: 26px; font-weight: 600; margin-top: 4px; font-family: var(--mono); }}
  .metric .hint {{ color: var(--muted); font-size: 12px; margin-top: 4px; }}
  .metric.good .value {{ color: var(--good); }}
  .metric.warn .value {{ color: var(--warn); }}
  .metric.bad .value {{ color: var(--bad); }}

  table {{
    width: 100%;
    border-collapse: collapse;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
    font-size: 13px;
  }}
  th, td {{ padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--border); }}
  th {{ background: var(--panel-2); color: var(--muted); font-weight: 500; text-transform: uppercase; font-size: 11px; letter-spacing: 0.05em; }}
  tr:last-child td {{ border-bottom: none; }}
  td.num {{ font-family: var(--mono); text-align: right; }}
  td.repo {{ font-family: var(--mono); font-size: 12px; color: var(--accent); }}

  .bar {{ display: inline-block; height: 10px; background: var(--good); border-radius: 2px; vertical-align: middle; }}
  .bar-track {{ display: inline-block; width: 120px; height: 10px; background: var(--panel-2); border-radius: 2px; vertical-align: middle; margin-right: 6px; }}
  .bar-track .bar {{ display: block; height: 100%; }}

  .good-text {{ color: var(--good); }}
  .warn-text {{ color: var(--warn); }}
  .bad-text {{ color: var(--bad); }}

  details.sample {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    margin-bottom: 12px;
    overflow: hidden;
  }}
  details.sample > summary {{
    padding: 14px 18px;
    cursor: pointer;
    list-style: none;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
  }}
  details.sample > summary::-webkit-details-marker {{ display: none; }}
  details.sample > summary::before {{
    content: "▸";
    color: var(--muted);
    margin-right: 8px;
    display: inline-block;
    transition: transform 0.15s;
  }}
  details.sample[open] > summary::before {{ transform: rotate(90deg); }}
  .sample-title {{ flex: 1; min-width: 0; }}
  .sample-title h3 {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .sample-title .meta {{ color: var(--muted); font-size: 12px; margin-top: 2px; }}
  .sample-metrics {{ display: flex; gap: 16px; flex-shrink: 0; font-family: var(--mono); font-size: 12px; }}
  .sample-metrics span {{ color: var(--muted); }}
  .sample-metrics strong {{ color: var(--text); }}

  .diff {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    border-top: 1px solid var(--border);
  }}
  .diff > div {{ padding: 0; max-height: 600px; overflow: auto; }}
  .diff > div + div {{ border-left: 1px solid var(--border); }}
  .pane-header {{
    position: sticky; top: 0;
    background: var(--panel-2);
    padding: 8px 14px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
    border-bottom: 1px solid var(--border);
  }}
  pre {{ margin: 0; padding: 12px 14px; font-family: var(--mono); font-size: 12px; white-space: pre-wrap; word-break: break-word; }}

  .missing-signals {{
    padding: 10px 18px;
    background: #2d1e1e;
    border-top: 1px solid var(--border);
    font-size: 12px;
    color: #ffb3b0;
  }}
  .missing-signals code {{ background: rgba(0,0,0,0.3); padding: 1px 5px; border-radius: 3px; }}
  footer {{ color: var(--muted); font-size: 12px; margin-top: 40px; text-align: center; }}
</style>
</head>
<body>

<h1>CI Log Compression Benchmark</h1>
<div class="sub">Tokenizer: {tokenizer}. Samples: {n_samples}. Generated by cilog-bench.</div>

<div class="headline">
  <div class="metric {token_class}">
    <div class="label">Token reduction</div>
    <div class="value">{token_reduction_pct:.1f}%</div>
    <div class="hint">{total_orig_tokens:,} → {total_comp_tokens:,} tokens</div>
  </div>
  <div class="metric {byte_class}">
    <div class="label">Byte reduction</div>
    <div class="value">{byte_reduction_pct:.1f}%</div>
    <div class="hint">{total_orig_bytes_h} → {total_comp_bytes_h}</div>
  </div>
  <div class="metric {preservation_class}">
    <div class="label">Signal preservation</div>
    <div class="value">{preservation_pct:.1f}%</div>
    <div class="hint">{preserved_signals}/{total_signals} distinctive signals</div>
  </div>
  <div class="metric">
    <div class="label">Avg compression time</div>
    <div class="value">{avg_ms:.1f}ms</div>
    <div class="hint">per sample, single-threaded Python</div>
  </div>
</div>

<h2>Per-sample results</h2>
<table>
  <thead>
    <tr>
      <th>Source</th>
      <th>Job</th>
      <th class="num">Orig tokens</th>
      <th class="num">Compressed</th>
      <th>Reduction</th>
      <th>Signals kept</th>
      <th class="num">Time</th>
    </tr>
  </thead>
  <tbody>
    {table_rows}
  </tbody>
</table>

<h2>Side-by-side inspection</h2>
{sample_cards}

<footer>
  Benchmark harness built to quickly validate whether CI-log compression is worth a full Rust MVP.
  Source data cached under <code>results/raw/</code>. Compressed outputs under <code>results/compressed/</code>.
</footer>

</body>
</html>
"""


def _human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024
    return f"{n:.1f}TB"


def _reduction_class(pct: float) -> str:
    if pct >= 70:
        return "good"
    if pct >= 40:
        return "warn"
    return "bad"


def _preservation_class(pct: float) -> str:
    if pct >= 95:
        return "good"
    if pct >= 80:
        return "warn"
    return "bad"


def _bar(pct: float) -> str:
    pct = max(0, min(100, pct))
    color = "var(--good)" if pct >= 70 else ("var(--warn)" if pct >= 40 else "var(--bad)")
    return f'<span class="bar-track"><span class="bar" style="width: {pct:.0f}%; background: {color};"></span></span>'


def build_report(results, compressed_outputs, raw_outputs, tokenizer) -> str:
    n = len(results)
    total_orig_tokens = sum(r.original_tokens for r in results)
    total_comp_tokens = sum(r.compressed_tokens for r in results)
    total_orig_bytes = sum(r.original_bytes for r in results)
    total_comp_bytes = sum(r.compressed_bytes for r in results)
    token_red = 100 * (1 - total_comp_tokens / total_orig_tokens) if total_orig_tokens else 0
    byte_red = 100 * (1 - total_comp_bytes / total_orig_bytes) if total_orig_bytes else 0

    total_sig = sum(r.signal_report.total_signals for r in results if r.signal_report)
    kept_sig = sum(r.signal_report.preserved_signals for r in results if r.signal_report)
    preservation_pct = 100 * kept_sig / total_sig if total_sig else 100.0

    avg_ms = sum(r.elapsed_ms for r in results) / n if n else 0

    # Table rows
    rows = []
    for r in results:
        sr = r.signal_report
        sig_pct = (sr.preservation_rate * 100) if sr else 100.0
        sig_class = _preservation_class(sig_pct)
        rows.append(
            f"<tr>"
            f"<td class='repo'>{html.escape(r.repo)}</td>"
            f"<td>{html.escape(r.job_name[:60])}</td>"
            f"<td class='num'>{r.original_tokens:,}</td>"
            f"<td class='num'>{r.compressed_tokens:,}</td>"
            f"<td>{_bar(r.token_reduction_pct)}"
            f"<span class='{_reduction_class(r.token_reduction_pct)}-text'>{r.token_reduction_pct:.1f}%</span></td>"
            f"<td><span class='{sig_class}-text'>"
            f"{sr.preserved_signals if sr else 0}/{sr.total_signals if sr else 0} "
            f"({sig_pct:.0f}%)</span></td>"
            f"<td class='num'>{r.elapsed_ms:.0f}ms</td>"
            f"</tr>"
        )
    table_rows = "\n".join(rows)

    # Sample cards
    cards = []
    for r in results:
        raw = raw_outputs.get(r.source, "")
        compressed = compressed_outputs.get(r.source, "")
        sr = r.signal_report
        sig_pct = (sr.preservation_rate * 100) if sr else 100.0

        # Truncate pane contents for render safety (large logs can hit MBs)
        RAW_TRUNC = 200_000
        raw_display = raw if len(raw) <= RAW_TRUNC else raw[:RAW_TRUNC] + f"\n\n... [truncated, {len(raw) - RAW_TRUNC:,} more bytes] ..."

        missing_html = ""
        if sr and sr.missing_by_type:
            items = []
            for sig_type, sigs in sr.missing_by_type.items():
                preview = ", ".join(f"<code>{html.escape(s[:80])}</code>" for s in sigs[:3])
                if len(sigs) > 3:
                    preview += f" <span style='color:var(--muted)'>(+{len(sigs) - 3} more)</span>"
                items.append(f"<strong>{sig_type}:</strong> {preview}")
            missing_html = (
                f"<div class='missing-signals'>⚠ Missing signals: " + " &nbsp;•&nbsp; ".join(items) + "</div>"
            )

        cards.append(
            f"<details class='sample'>"
            f"<summary>"
            f"<div class='sample-title'>"
            f"<h3>{html.escape(r.repo)} — {html.escape(r.job_name)}</h3>"
            f"<div class='meta'>{html.escape(r.source)}</div>"
            f"</div>"
            f"<div class='sample-metrics'>"
            f"<span>tokens:</span> <strong>{r.original_tokens:,} → {r.compressed_tokens:,}</strong>"
            f" &nbsp; <span>reduction:</span> <strong class='{_reduction_class(r.token_reduction_pct)}-text'>{r.token_reduction_pct:.1f}%</strong>"
            f" &nbsp; <span>signals:</span> <strong class='{_preservation_class(sig_pct)}-text'>{sig_pct:.0f}%</strong>"
            f"</div>"
            f"</summary>"
            f"{missing_html}"
            f"<div class='diff'>"
            f"<div><div class='pane-header'>Original ({r.original_lines:,} lines, {_human_bytes(r.original_bytes)})</div>"
            f"<pre>{html.escape(raw_display)}</pre></div>"
            f"<div><div class='pane-header'>Compressed ({r.compressed_lines:,} lines, {_human_bytes(r.compressed_bytes)})</div>"
            f"<pre>{html.escape(compressed)}</pre></div>"
            f"</div>"
            f"</details>"
        )
    sample_cards = "\n".join(cards)

    return HTML_TEMPLATE.format(
        tokenizer=html.escape(tokenizer),
        n_samples=n,
        token_class=_reduction_class(token_red),
        byte_class=_reduction_class(byte_red),
        preservation_class=_preservation_class(preservation_pct),
        token_reduction_pct=token_red,
        byte_reduction_pct=byte_red,
        total_orig_tokens=total_orig_tokens,
        total_comp_tokens=total_comp_tokens,
        total_orig_bytes_h=_human_bytes(total_orig_bytes),
        total_comp_bytes_h=_human_bytes(total_comp_bytes),
        preservation_pct=preservation_pct,
        preserved_signals=kept_sig,
        total_signals=total_sig,
        avg_ms=avg_ms,
        table_rows=table_rows,
        sample_cards=sample_cards,
    )
