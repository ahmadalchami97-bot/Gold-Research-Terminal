"""Multi-Timeframe Indicator Consensus (Daily / Weekly / Monthly)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.ui import components as C
from app.ui import plotly_template as P
from app.ui.data import get_snapshot
from app.ui.theme import PALETTE


def render() -> None:
    snap = get_snapshot()
    mtf = snap.consensus_mtf
    C.header("Multi-Timeframe Indicator Consensus",
             "14 indicators classified independently on Daily, Weekly and Monthly "
             "timeframes — so a signal's horizon (short / medium / long term) is explicit")

    # --- timeframe consensus summary ------------------------------------
    C.header("Timeframe consensus")
    g = st.columns(3)
    for col, cs in zip(g, mtf.frames):
        with col:
            st.plotly_chart(P.gauge(cs.institutional_score, f"{cs.timeframe} bias"),
                            width="stretch")
    rows = [{"Horizon": cs.timeframe, "Institutional Score": f"{cs.institutional_score:.0f}/100",
             "Bias": cs.bias} for cs in mtf.frames]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.markdown(
        "<div class='grt-note'>"
        "<b>Daily</b> = short-term trading outlook (days to ~2 weeks) &nbsp;·&nbsp; "
        "<b>Weekly</b> = medium-term outlook (1–3 months) &nbsp;·&nbsp; "
        "<b>Monthly</b> = long-term outlook (3–12 months)</div>", unsafe_allow_html=True)

    # --- the matrix ------------------------------------------------------
    C.header("Indicator matrix")
    C.multi_timeframe_matrix(mtf)

    # --- alignment + outlook linkage ------------------------------------
    align_color = (PALETTE["bull"] if "agree" in mtf.alignment.lower()
                   else PALETTE["gold"] if "diverge" in mtf.alignment.lower()
                   else PALETTE["neutral"])
    st.markdown(
        f"<div class='grt-card' style='border-left:3px solid {align_color};margin-top:.6rem'>"
        f"<b>Cross-timeframe read:</b> {mtf.alignment}</div>", unsafe_allow_html=True)

    C.header("How this feeds the Outlook")
    C.note("1-Week outlook is driven primarily by Daily + Weekly signals · "
           "1-Month outlook by Weekly signals · 3-Month outlook by Monthly + Weekly "
           "signals. When timeframes disagree, the Outlook Dashboard explains the split "
           "per horizon.")
    link = []
    tf_map = {"1 Week": ("daily", "weekly"), "1 Month": ("weekly",),
              "3 Months": ("monthly", "weekly")}
    bias_by_tf = {"daily": mtf.daily.bias, "weekly": mtf.weekly.bias,
                  "monthly": mtf.monthly.bias}
    for h in snap.outlook.horizons:
        used = tf_map.get(h.horizon, ())
        basis = ", ".join(f"{tf} {bias_by_tf[tf].lower()}" for tf in used)
        link.append({"Outlook": h.horizon, "Direction": h.direction.value,
                     "Timeframe basis": basis})
    st.dataframe(pd.DataFrame(link), hide_index=True, width="stretch")

    C.note("State mapping: Bearish −2 · Slightly Bearish −1 · Neutral 0 · "
           "Slightly Bullish +1 · Bullish +2. Score = mean state mapped to 0–100. "
           "Classification rules are documented in docs/METHODOLOGY.md.")

    C.disclaimer()
