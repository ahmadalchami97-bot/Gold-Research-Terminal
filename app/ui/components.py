"""Reusable institutional UI components rendered as styled HTML."""
from __future__ import annotations

import html

import streamlit as st

from app.config import APP_NAME, APP_TAGLINE, DISCLAIMER
from app.schemas import DataProvenance, TimeframeConsensus
from app.ui.theme import PALETTE, STATE_COLORS, state_color


def header(title: str, sub: str | None = None) -> None:
    st.markdown(f'<div class="grt-h">{html.escape(title)}</div>', unsafe_allow_html=True)
    if sub:
        st.markdown(f'<div class="grt-sub">{html.escape(sub)}</div>', unsafe_allow_html=True)


def pill_html(text: str, color: str) -> str:
    return (f'<span class="grt-pill" style="background:{color}22;color:{color};'
            f'border:1px solid {color}55">{html.escape(text)}</span>')


def state_pill(label: str) -> str:
    return pill_html(label, state_color(label))


def hero(provenance: DataProvenance | None, as_of_label: str) -> None:
    badge = data_badge_html(provenance)
    st.markdown(
        f'<div class="grt-hero"><span class="name">Gold <span class="accent">'
        f'Research Terminal</span></span><span class="tag">{html.escape(APP_TAGLINE)}'
        f'</span></div><div style="margin:.3rem 0 .2rem 0">{badge}'
        f'<span class="grt-badge" style="margin-left:.4rem">As of {html.escape(as_of_label)}'
        f'</span></div>', unsafe_allow_html=True)


def data_badge_html(provenance: DataProvenance | None) -> str:
    if provenance is None:
        return ""
    live = provenance.mode == "live"
    color = PALETTE["bull"] if live else PALETTE["gold"]
    label = "LIVE DATA" if live else "CACHED / SAMPLE"
    return pill_html(label, color)


def scorecard_html(label: str, value: str, sub: str | None = None,
                   sub_color: str | None = None, value_color: str | None = None) -> str:
    vc = f"color:{value_color}" if value_color else ""
    sub_html = ""
    if sub:
        sc = sub_color or PALETTE["muted"]
        sub_html = f'<div class="sub" style="color:{sc}">{html.escape(sub)}</div>'
    return (f'<div class="grt-card"><div class="lbl">{html.escape(label)}</div>'
            f'<div class="val" style="{vc}">{value}</div>{sub_html}</div>')


def scorecards(items: list[dict], per_row: int = 4) -> None:
    """Render a grid of scorecards. Each item: label, value, sub?, sub_color?, value_color?"""
    for start in range(0, len(items), per_row):
        row = items[start:start + per_row]
        cols = st.columns(len(row))
        for col, item in zip(cols, row):
            with col:
                st.markdown(scorecard_html(**item), unsafe_allow_html=True)


def metric_color(value: float) -> str:
    return PALETTE["bull"] if value > 0 else PALETTE["bear"] if value < 0 else PALETTE["muted"]


def _state_cell(state_value: str) -> str:
    color = STATE_COLORS.get(state_value, PALETTE["neutral"])
    return (f'<td style="text-align:center;padding:5px 10px;white-space:nowrap">'
            f'<span style="color:{color};font-weight:600;font-size:.8rem">'
            f'&#9679; {html.escape(state_value)}</span></td>')


def multi_timeframe_matrix(mtf: TimeframeConsensus) -> None:
    """Render Indicator × {Daily, Weekly, Monthly} with a colored state per cell."""
    frames = [("Daily", mtf.daily), ("Weekly", mtf.weekly), ("Monthly", mtf.monthly)]
    per = {tf: {r.name: r for r in cs.readings} for tf, cs in frames}
    names = [r.name for r in mtf.daily.readings]
    category = {r.name: r.category for r in mtf.daily.readings}

    head = "".join(
        f'<th style="padding:6px 12px;text-align:center;font-size:.74rem;'
        f'color:{PALETTE["gold"]};border-bottom:1px solid {PALETTE["border"]}">{tf}</th>'
        for tf, _ in frames)
    rows = []
    for name in names:
        cells = "".join(_state_cell(per[tf][name].state.value) for tf, _ in frames)
        rows.append(
            f'<tr><td style="padding:5px 10px;white-space:nowrap">'
            f'<span style="color:{PALETTE["text"]};font-weight:600">{html.escape(name)}</span>'
            f'<span style="color:{PALETTE["muted"]};font-size:.72rem"> · {html.escape(category[name])}'
            f'</span></td>{cells}</tr>')
    table = (
        f'<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;'
        f'background:{PALETTE["panel"]};border:1px solid {PALETTE["border"]};border-radius:8px">'
        f'<thead><tr><th style="text-align:left;padding:6px 10px;font-size:.74rem;'
        f'color:{PALETTE["muted"]};border-bottom:1px solid {PALETTE["border"]}">Indicator</th>'
        f'{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
    st.markdown(table, unsafe_allow_html=True)


def note(text: str) -> None:
    st.markdown(f'<div class="grt-note">{html.escape(text)}</div>', unsafe_allow_html=True)


def disclaimer() -> None:
    st.markdown(f'<div class="grt-disc"><b>{html.escape(APP_NAME)}</b> — {html.escape(DISCLAIMER)}'
                f'</div>', unsafe_allow_html=True)


def provenance_table(provenance: DataProvenance | None) -> None:
    if provenance is None or not provenance.series:
        return
    import pandas as pd
    rows = [{"Series": s.key, "Source": s.source,
             "Mode": "live" if s.ok else "cached",
             "As of": s.as_of.strftime("%Y-%m-%d") if s.as_of else "—",
             "Detail": s.detail} for s in provenance.series]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
