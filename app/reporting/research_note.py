"""Compile a snapshot + narrative + news into an exportable research note."""
from __future__ import annotations

from app.config import APP_NAME, DISCLAIMER
from app.schemas import NarrativeBlock, NewsDigest, TerminalSnapshot


def _blocks_map(blocks: list[NarrativeBlock]) -> dict[str, str]:
    return {b.title: b.body for b in blocks}


def build_markdown(snap: TerminalSnapshot, blocks: list[NarrativeBlock],
                   digest: NewsDigest | None) -> str:
    bm = _blocks_map(blocks)
    ms = snap.market_state
    rets = {r.horizon: r.pct for r in ms.returns}
    mode = snap.provenance.mode if snap.provenance else "?"
    src = blocks[0].source if blocks else "deterministic"

    lines = [
        f"# {APP_NAME} — Research Note",
        f"*As of {snap.as_of.strftime('%Y-%m-%d')} · Data: {mode} · "
        f"Narrative: {src}*", "",
        "## Executive summary", bm.get("Executive summary", ""), "",
        "## Snapshot", "",
        f"- **Spot:** ${ms.price:,.0f} ({ms.change_pct_1d:+.2f}% today)",
        f"- **Returns:** 1M {rets.get('1M', float('nan')):+.1f}% · "
        f"YTD {rets.get('YTD', float('nan')):+.1f}% · 1Y {rets.get('1Y', float('nan')):+.1f}%",
        f"- **Realized volatility:** {ms.annualized_vol:.0f}% ({snap.regime.vol_regime})",
        f"- **Technical bias:** {snap.consensus.institutional_score:.0f}/100 "
        f"({snap.consensus.institutional_label})",
        f"- **Dominant driver:** {snap.drivers.dominant_driver}",
    ]
    if digest:
        lines.append(f"- **Macro news score:** {digest.macro_score:+.0f}/100 "
                     f"({digest.overall_classification.value})")
    lines += ["", "## Outlook", "",
              "| Horizon | Direction | Target | Expected range | Confidence | Key driver | Invalidation |",
              "|---|---|---|---|---|---|---|"]
    for h in snap.outlook.horizons:
        lines.append(
            f"| {h.horizon} | {h.direction.value} | ${h.target_price:,.0f} | "
            f"${h.expected_low:,.0f}–${h.expected_high:,.0f} | "
            f"{h.confidence.value} ({h.confidence_pct:.0f}%) | {h.key_driver} | "
            f"${h.invalidation.level:,.0f} |")

    for title in ["What gold is doing", "Why it is doing it", "What changed",
                  "Outlook", "Risks & invalidation"]:
        if title in bm:
            lines += ["", f"## {title}", bm[title]]

    lines += ["", "## Key levels", ""]
    ns, nr = snap.levels.nearest_support, snap.levels.nearest_resistance
    if nr:
        lines.append(f"- **Nearest resistance:** ${nr.price:,.0f} ({nr.distance_pct:+.1f}%, {nr.label})")
    if ns:
        lines.append(f"- **Nearest support:** ${ns.price:,.0f} ({ns.distance_pct:+.1f}%, {ns.label})")

    rk = snap.risk
    lines += ["", "## Risk", "",
              f"- **VaR 95% (1d):** {rk.var_95_1d_pct:.1f}% · CVaR {rk.cvar_95_1d_pct:.1f}%",
              f"- **Max drawdown (1y):** {rk.max_drawdown_1y_pct:.1f}%",
              f"- **Bull invalidation:** ${rk.bull_invalidation.level:,.0f}",
              f"- **Bear invalidation:** ${rk.bear_invalidation.level:,.0f}"]
    for t in rk.triggers:
        lines.append(f"- **{t.name}** ({t.severity}): {t.condition}")

    if digest and digest.items:
        lines += ["", "## News", "", digest.summary, ""]
        for it in digest.items[:8]:
            lines.append(f"- **[{it.classification.value}]** {it.headline} — {it.what_it_means}")

    lines += ["", "---", f"*{DISCLAIMER}*"]
    return "\n".join(lines)


_HTML_CSS = """
body{font-family:'Segoe UI',Helvetica,Arial,sans-serif;color:#1c2330;max-width:820px;
  margin:32px auto;padding:0 22px;line-height:1.5}
h1{font-size:24px;margin:0 0 2px} h2{font-size:15px;text-transform:uppercase;
  letter-spacing:.05em;color:#9a7b34;border-bottom:1px solid #e3e6ec;padding-bottom:4px;
  margin:26px 0 10px} .meta{color:#6b7280;font-size:13px;margin-bottom:6px}
table{border-collapse:collapse;width:100%;font-size:13px;margin:6px 0}
th,td{border:1px solid #e3e6ec;padding:6px 9px;text-align:left}
th{background:#f6f4ef;color:#6b5524} ul{margin:6px 0;padding-left:20px}
.pill{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;font-weight:600}
.bull{background:#e4f6ee;color:#1f8a5b}.bear{background:#fbe7e5;color:#b23a33}
.neutral{background:#eef0f3;color:#5b6472}
.disc{color:#8a93a3;font-size:11px;border-top:1px solid #e3e6ec;margin-top:26px;padding-top:8px}
"""


def _cls(name: str) -> str:
    return {"Bullish": "bull", "Bearish": "bear"}.get(name, "neutral")


def build_html(snap: TerminalSnapshot, blocks: list[NarrativeBlock],
               digest: NewsDigest | None) -> str:
    """Self-contained, print-ready HTML note (browser → Print → PDF)."""
    import html as _h

    bm = _blocks_map(blocks)
    ms = snap.market_state
    mode = snap.provenance.mode if snap.provenance else "?"
    src = blocks[0].source if blocks else "deterministic"

    def esc(t: str) -> str:
        return _h.escape(str(t))

    out = [f"<!DOCTYPE html><html><head><meta charset='utf-8'>",
           f"<title>{esc(APP_NAME)} — Research Note</title><style>{_HTML_CSS}</style></head><body>",
           f"<h1>{esc(APP_NAME)} — Research Note</h1>",
           f"<div class='meta'>As of {snap.as_of.strftime('%Y-%m-%d')} · Data: {esc(mode)} · "
           f"Narrative: {esc(src)}</div>",
           "<h2>Executive summary</h2>", f"<p>{esc(bm.get('Executive summary', ''))}</p>",
           "<h2>Snapshot</h2><ul>",
           f"<li><b>Spot:</b> ${ms.price:,.0f} ({ms.change_pct_1d:+.2f}% today)</li>",
           f"<li><b>Realized volatility:</b> {ms.annualized_vol:.0f}% ({esc(snap.regime.vol_regime)})</li>",
           f"<li><b>Technical bias:</b> {snap.consensus.institutional_score:.0f}/100 "
           f"({esc(snap.consensus.institutional_label)})</li>",
           f"<li><b>Dominant driver:</b> {esc(snap.drivers.dominant_driver)}</li>"]
    if digest:
        out.append(f"<li><b>Macro news score:</b> {digest.macro_score:+.0f}/100 "
                   f"({esc(digest.overall_classification.value)})</li>")
    out.append("</ul>")

    out.append("<h2>Outlook</h2><table><tr><th>Horizon</th><th>Direction</th><th>Target</th>"
               "<th>Expected range</th><th>Confidence</th><th>Key driver</th><th>Invalidation</th></tr>")
    for h in snap.outlook.horizons:
        out.append(
            f"<tr><td>{esc(h.horizon)}</td><td><span class='pill {_cls(h.direction.value)}'>"
            f"{esc(h.direction.value)}</span></td><td>${h.target_price:,.0f}</td>"
            f"<td>${h.expected_low:,.0f}–${h.expected_high:,.0f}</td>"
            f"<td>{esc(h.confidence.value)} ({h.confidence_pct:.0f}%)</td>"
            f"<td>{esc(h.key_driver)}</td><td>${h.invalidation.level:,.0f}</td></tr>")
    out.append("</table>")

    for title in ["What gold is doing", "Why it is doing it", "What changed",
                  "Risks & invalidation"]:
        if title in bm:
            out += [f"<h2>{esc(title)}</h2>", f"<p>{esc(bm[title])}</p>"]

    rk = snap.risk
    out += ["<h2>Risk &amp; invalidation levels</h2><ul>",
            f"<li><b>VaR 95% (1d):</b> {rk.var_95_1d_pct:.1f}% · CVaR {rk.cvar_95_1d_pct:.1f}%</li>",
            f"<li><b>Max drawdown (1y):</b> {rk.max_drawdown_1y_pct:.1f}%</li>",
            f"<li><b>Bull invalidation:</b> ${rk.bull_invalidation.level:,.0f}</li>",
            f"<li><b>Bear invalidation:</b> ${rk.bear_invalidation.level:,.0f}</li></ul>"]

    if digest and digest.items:
        out += ["<h2>News</h2>", f"<p>{esc(digest.summary)}</p><ul>"]
        for it in digest.items[:8]:
            out.append(f"<li><span class='pill {_cls(it.classification.value)}'>"
                       f"{esc(it.classification.value)}</span> {esc(it.headline)} — "
                       f"{esc(it.what_it_means)}</li>")
        out.append("</ul>")

    out += [f"<div class='disc'>{esc(DISCLAIMER)}</div></body></html>"]
    return "\n".join(out)
