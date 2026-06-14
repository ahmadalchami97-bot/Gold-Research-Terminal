"""Outlook Dashboard — "What is the outlook?" (1W / 1M / 3M)."""
from __future__ import annotations

import html

import streamlit as st

from app.ui import components as C
from app.ui import plotly_template as P
from app.ui.data import get_snapshot
from app.ui.theme import PALETTE, STATE_COLORS


def _card(h) -> str:
    dc = STATE_COLORS.get(h.direction.value, PALETTE["neutral"])
    cc = (PALETTE["bull"] if h.confidence.value == "High" else
          PALETTE["gold"] if h.confidence.value == "Medium" else PALETTE["muted"])
    return f"""
<div class="grt-card" style="border-top:3px solid {dc}">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <span style="font-weight:800;font-size:1.05rem;color:{PALETTE['text']}">{html.escape(h.horizon)}</span>
    {C.pill_html(h.direction.value, dc)}
  </div>
  <div style="margin-top:.7rem"><span class="lbl">Target price</span>
    <div class="val" style="font-size:1.7rem">${h.target_price:,.0f}</div></div>
  <table style="width:100%;margin-top:.5rem;font-size:.86rem">
    <tr><td style="color:{PALETTE['muted']};padding:3px 0">Expected range</td>
        <td style="text-align:right;color:{PALETTE['text']}">${h.expected_low:,.0f} – ${h.expected_high:,.0f}</td></tr>
    <tr><td style="color:{PALETTE['muted']};padding:3px 0">Confidence</td>
        <td style="text-align:right;color:{cc};font-weight:700">{h.confidence.value} · {h.confidence_pct:.0f}%</td></tr>
    <tr><td style="color:{PALETTE['muted']};padding:3px 0">Key driver</td>
        <td style="text-align:right;color:{PALETTE['text']}">{html.escape(h.key_driver)}</td></tr>
    <tr><td style="color:{PALETTE['muted']};padding:3px 0">Invalidation</td>
        <td style="text-align:right;color:{PALETTE['gold_soft']}">${h.invalidation.level:,.0f}</td></tr>
  </table>
  <div class="grt-note" style="margin-top:.5rem;border-top:1px solid {PALETTE['border']};padding-top:.5rem">
    {html.escape(h.invalidation.condition)}</div>
</div>"""


def render() -> None:
    snap = get_snapshot()
    o = snap.outlook
    C.header("Outlook Dashboard",
             "Direction, target, expected range, confidence, key driver and "
             "invalidation across 1-week, 1-month and 3-month horizons")
    C.note("Model central estimates and probabilistic ranges with explicit "
           "invalidation — research outputs, not trade recommendations.")

    cols = st.columns(len(o.horizons))
    for col, h in zip(cols, o.horizons):
        with col:
            st.markdown(_card(h), unsafe_allow_html=True)

    left, right = st.columns([1.15, 1])
    with left:
        C.header("Probability fan")
        st.plotly_chart(P.fan_chart(o.spot, snap.distribution.horizons),
                        width="stretch")
    with right:
        C.header("Rationale")
        for h in o.horizons:
            st.markdown(f"**{h.horizon}** — "
                        f'<span style="color:{STATE_COLORS.get(h.direction.value)}">'
                        f"{h.direction.value}</span>", unsafe_allow_html=True)
            st.markdown(f'<div class="grt-note">{html.escape(h.rationale)}</div>',
                        unsafe_allow_html=True)

    C.disclaimer()
