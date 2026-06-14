"""Executive Overview — the one-screen summary."""
from __future__ import annotations

import streamlit as st

from app.narrative import get_narrative
from app.ui import components as C
from app.ui import plotly_template as P
from app.ui.data import get_snapshot
from app.ui.theme import PALETTE


def render() -> None:
    snap = get_snapshot()
    ms, c = snap.market_state, snap.consensus
    C.hero(snap.provenance, snap.as_of.strftime("%Y-%m-%d"))

    rets = {r.horizon: r.pct for r in ms.returns}
    near = snap.outlook.horizons[0]
    cards = [
        {"label": "Spot (USD/oz)", "value": f"${ms.price:,.0f}",
         "sub": f"{ms.change_pct_1d:+.2f}% today", "sub_color": C.metric_color(ms.change_pct_1d)},
        {"label": "1-Month", "value": f"{(rets.get('1M') or 0):+.1f}%",
         "value_color": C.metric_color(rets.get('1M') or 0)},
        {"label": "YTD", "value": f"{(rets.get('YTD') or 0):+.1f}%",
         "value_color": C.metric_color(rets.get('YTD') or 0)},
        {"label": "Realized vol", "value": f"{ms.annualized_vol:.0f}%",
         "sub": f"{snap.regime.vol_regime} regime"},
        {"label": "Technical bias", "value": f"{c.institutional_score:.0f}",
         "sub": c.institutional_label,
         "value_color": P.STATE_COLORS.get("Bullish") if c.institutional_score >= 60
         else P.STATE_COLORS.get("Bearish") if c.institutional_score <= 40 else PALETTE["neutral"]},
        {"label": "1-Week view", "value": near.direction.value,
         "sub": f"target ${near.target_price:,.0f}",
         "value_color": P.STATE_COLORS.get(near.direction.value, PALETTE["neutral"])},
    ]
    C.scorecards(cards, per_row=6)

    blocks = get_narrative(snap)
    by_title = {b.title: b for b in blocks}
    src = blocks[0].source if blocks else "deterministic"
    C.header("Research summary", f"Narrative engine: {src}")
    if "Executive summary" in by_title:
        st.markdown(by_title["Executive summary"].body)

    left, right = st.columns(2)
    order = ["What gold is doing", "Why it is doing it", "What changed",
             "Outlook", "Risks & invalidation"]
    present = [t for t in order if t in by_title]
    for i, title in enumerate(present):
        target = left if i % 2 == 0 else right
        with target:
            st.markdown(f"**{title}**")
            st.markdown(f'<div class="grt-note">{by_title[title].body}</div>',
                        unsafe_allow_html=True)

    C.header("Cross-horizon outlook")
    oc, fc = st.columns([1.05, 1])
    with oc:
        import pandas as pd
        rows = [{"Horizon": h.horizon, "Direction": h.direction.value,
                 "Target": f"${h.target_price:,.0f}",
                 "Range": f"${h.expected_low:,.0f}–${h.expected_high:,.0f}",
                 "Conf.": h.confidence.value} for h in snap.outlook.horizons]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        ns, nr = snap.levels.nearest_support, snap.levels.nearest_resistance
        C.scorecards([
            {"label": "Nearest support", "value": f"${ns.price:,.0f}" if ns else "—",
             "sub": f"{ns.distance_pct:+.1f}% · {ns.label}" if ns else "",
             "value_color": PALETTE["bull"]},
            {"label": "Nearest resistance", "value": f"${nr.price:,.0f}" if nr else "—",
             "sub": f"{nr.distance_pct:+.1f}% · {nr.label}" if nr else "",
             "value_color": PALETTE["bear"]},
        ], per_row=2)
    with fc:
        st.plotly_chart(P.fan_chart(snap.distribution.spot, snap.distribution.horizons),
                        width="stretch")

    C.disclaimer()
