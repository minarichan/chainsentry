"""Self-contained HTML security report."""

from __future__ import annotations

import html
from pathlib import Path

from scanner.models import ScanResult, Severity

SEVERITY_COLOR = {
    Severity.CRITICAL: "#7f1d1d",
    Severity.HIGH: "#dc2626",
    Severity.MEDIUM: "#ea580c",
    Severity.LOW: "#ca8a04",
    Severity.INFO: "#2563eb",
}


def _verdict_color(verdict: str) -> str:
    return {
        "issues": "#dc2626",
        "review": "#ea580c",
        "notes": "#ca8a04",
        "clean": "#059669",
        "failed": "#64748b",
    }.get(verdict, "#64748b")


def _snippet_html(finding) -> str:
    if not finding.snippet:
        return ""
    start = finding.snippet_start_line or 1
    hit = finding.location.line
    rows = []
    for offset, raw in enumerate(finding.snippet.splitlines()):
        number = start + offset
        cls = " hit" if number == hit else ""
        rows.append(
            f'<div class="snip-line{cls}"><span class="n">{number}</span>'
            f"<code>{html.escape(raw) if raw else ' '}</code></div>"
        )
    return f'<pre class="snippet">{"".join(rows)}</pre>'


def render_html(result: ScanResult) -> str:
    card = result.scorecard
    contracts = ", ".join(c.name for c in result.contracts) or "Unknown"
    findings_html = []
    for finding in result.findings:
        color = SEVERITY_COLOR[finding.severity]
        findings_html.append(
            f"""
            <article class="finding">
              <header>
                <span class="sev" style="background:{color}">{html.escape(finding.severity.value.upper())}</span>
                <span class="id">{html.escape(finding.id)}</span>
                <span class="swc">{html.escape(finding.classification)}</span>
              </header>
              <h3>{html.escape(finding.title)}</h3>
              <p class="meta">{html.escape(finding.contract or "—")} · {html.escape(finding.location.file or "—")} · {html.escape(finding.function or "—")} · Line {finding.location.line} · Confidence {finding.confidence}%</p>
              <p>{html.escape(finding.description)}</p>
              {_snippet_html(finding)}
              <p class="rec"><strong>Recommendation.</strong> {html.escape(finding.recommendation)}</p>
            </article>
            """
        )

    surfaces_html = []
    for surface in result.surfaces:
        risk_color = {"HIGH": "#dc2626", "MEDIUM": "#ea580c", "LOW": "#059669"}.get(surface.risk, "#64748b")
        flags = "".join(f"<li>{html.escape(note)}</li>" for note in surface.notes)
        surfaces_html.append(
            f"""
            <tr>
              <td><code>{html.escape(surface.name)}()</code></td>
              <td>{html.escape(surface.visibility)}</td>
              <td>{html.escape(surface.mutability)}</td>
              <td><span class="sev" style="background:{risk_color}">{html.escape(surface.risk)}</span></td>
              <td><ul class="flags">{flags}</ul></td>
            </tr>
            """
        )

    categories_html = "".join(
        f"""
        <div class="cat">
          <span>{html.escape(cat.name)}</span>
          <strong>{cat.finding_count} hit{'s' if cat.finding_count != 1 else ''}</strong>
        </div>
        """
        for cat in card.categories
    )

    onchain = ""
    if result.onchain:
        oc = result.onchain
        signals = "".join(f"<li>{html.escape(s)}</li>" for s in oc.signals) or "<li>None</li>"
        onchain = f"""
        <section>
          <h2>On-chain analysis</h2>
          <p>Address <code>{html.escape(oc.address)}</code> · {html.escape(oc.network)} · Verified: {"yes" if oc.verified else "no"}</p>
          <ul>
            <li>Transactions: {oc.transaction_count if oc.transaction_count is not None else "n/a"}</li>
            <li>Unique users: {oc.unique_users if oc.unique_users is not None else "n/a"}</li>
            <li>ETH balance: {html.escape(oc.eth_balance or "n/a")}</li>
            <li>Owner: {html.escape(oc.owner or "n/a")}</li>
          </ul>
          <p>Security signals</p>
          <ul>{signals}</ul>
        </section>
        """

    errors = ""
    if result.compiler_errors:
        items = "".join(f"<li><pre>{html.escape(e)}</pre></li>" for e in result.compiler_errors)
        errors = f"<section class='errors'><h2>Compiler errors</h2><ul>{items}</ul></section>"

    proxy_line = ""
    if result.source_role == "implementation" and result.implementation_address:
        impl_name = html.escape(result.analyzed_name or "implementation")
        proxy_line = (
            f"<p>Proxy <code>{html.escape(result.address or '')}</code> — analyzed "
            f"<strong>{impl_name}</strong> at "
            f"<code>{html.escape(result.implementation_address)}</code>.</p>"
        )
    elif result.source_role == "proxy_fallback":
        proxy_line = f"<p>{html.escape(result.proxy_note or 'Proxy detected; scanned proxy source.')}</p>"

    color = _verdict_color(card.verdict)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Security Report — {html.escape(contracts)}</title>
  <style>
    :root {{
      --bg: #071018;
      --panel: #0e1a24;
      --line: #1e3344;
      --text: #e7f0f5;
      --muted: #8aa0ae;
      --accent: #3ee0b4;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    main {{ max-width: 960px; margin: 0 auto; padding: 48px 24px 80px; }}
    h1 {{ font-size: 28px; letter-spacing: 0.08em; text-transform: uppercase; margin: 0 0 8px; }}
    .kicker {{ color: var(--accent); font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 12px; letter-spacing: 0.18em; }}
    .hero {{
      display: grid;
      grid-template-columns: 220px 1fr;
      gap: 32px;
      background: var(--panel);
      border: 1px solid var(--line);
      padding: 28px;
      margin: 28px 0;
    }}
    .verdict {{
      font-size: 28px;
      font-weight: 700;
      line-height: 1.15;
      color: {color};
    }}
    .verdict small {{
      display: block;
      margin-top: 10px;
      font-size: 12px;
      font-weight: 400;
      color: var(--muted);
      letter-spacing: 0;
    }}
    .counts span {{ margin-right: 16px; color: var(--muted); }}
    .cats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 16px; }}
    .cat {{ display: flex; justify-content: space-between; border: 1px solid var(--line); padding: 8px 12px; font-size: 14px; }}
    h2 {{ margin-top: 40px; font-size: 18px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--accent); }}
    .finding {{ border: 1px solid var(--line); background: #0b1620; padding: 22px 20px; margin: 28px 0; }}
    .finding header {{ display: flex; gap: 10px; align-items: center; }}
    .sev {{ color: white; font-size: 11px; padding: 2px 8px; letter-spacing: 0.08em; }}
    .id, .swc, code {{ font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 12px; color: var(--muted); }}
    .meta {{ color: var(--muted); font-size: 13px; }}
    .rec {{ color: #cde7db; }}
    pre.snippet {{
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 12px;
      background: #071018;
      border: 1px solid var(--line);
      padding: 10px 0;
      overflow-x: auto;
      line-height: 1.45;
    }}
    pre.snippet .snip-line {{ display: flex; gap: 12px; padding: 0 12px; }}
    pre.snippet .snip-line.hit {{ background: #1a2a22; color: #d5f0e0; }}
    pre.snippet .n {{ color: var(--muted); min-width: 2.5em; text-align: right; user-select: none; }}
    pre.snippet code {{ flex: 1; color: inherit; font: inherit; white-space: pre; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px 8px; text-align: left; vertical-align: top; }}
    ul.flags {{ margin: 0; padding-left: 16px; color: var(--muted); }}
    .errors pre {{ white-space: pre-wrap; color: #fca5a5; }}
  </style>
</head>
<body>
  <main>
    <p class="kicker">ChainSentry</p>
    <h1>Security Report</h1>
    <p>Contract: <strong>{html.escape(contracts)}</strong> · File: {html.escape(result.filename)} · Network: {html.escape(result.network)} · solc {html.escape(result.solc_version)}</p>
    {proxy_line}
    {errors}
    <section class="hero">
      <div class="verdict">{html.escape(card.verdict_label)}<small>Heuristic AST scan. Severity mix is the report — not a calibrated 0–100 rating.</small></div>
      <div>
        <h2 style="margin-top:0">Severity mix</h2>
        <p class="counts">
          <span>Critical {card.critical}</span>
          <span>High {card.high}</span>
          <span>Medium {card.medium}</span>
          <span>Low {card.low}</span>
          <span>Info {card.info}</span>
        </p>
        <div class="cats">{categories_html}</div>
      </div>
    </section>
    <section>
      <h2>Findings ({len(result.findings)})</h2>
      {''.join(findings_html) or '<p>No issues detected by current detectors.</p>'}
    </section>
    <section>
      <h2>Function attack surface</h2>
      <table>
        <thead><tr><th>Function</th><th>Visibility</th><th>Mutability</th><th>Risk</th><th>Notes</th></tr></thead>
        <tbody>{''.join(surfaces_html)}</tbody>
      </table>
    </section>
    {onchain}
  </main>
</body>
</html>
"""


def write_html_report(result: ScanResult, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_html(result), encoding="utf-8")
    return output
