"""Indicator Consensus Dashboard (14 indicators → matrix, %s, score)."""
from __future__ import annotations

import streamlit as st

from app.ui import components as C
from app.ui import plotly_template as P
from app.ui.data import get_snapshot
from app.ui.theme import PALETTE


def render() -> None:
    snap = get_snapshot()
    s = snap.consensus
    C.header("Indicator Consensus",
             "14 technical indicators classified into a 5-state matrix, aggregated "
             "to a bullish / neutral / bearish split and an institutional score")

    score_color = (PALETTE["bull"] if s.institutional_score >= 60 else
                   PALETTE["bear"] if s.institutional_score <= 40 else PALETTE["neutral"])
    C.scorecards([
        {"label": "Institutional score", "value": f"{s.institutional_score:.0f}/100",
         "sub": s.institutional_label, "value_color": score_color},
        {"label": "Bullish", "value": f"{s.bullish_pct:.0f}%", "value_color": PALETTE["bull"]},
        {"label": "Neutral", "value": f"{s.neutral_pct:.0f}%", "value_color": PALETTE["neutral"]},
        {"label": "Bearish", "value": f"{s.bearish_pct:.0f}%", "value_color": PALETTE["bear"]},
    ], per_row=4)

    g, p, b = st.columns([1, 1, 1.3])
    with g:
        C.header("Score")
        st.plotly_chart(P.gauge(s.institutional_score, "Gold technical bias"),
                        width="stretch")
    with p:
        C.header("Split")
        st.plotly_chart(P.consensus_pie(s.bullish_pct, s.neutral_pct, s.bearish_pct),
                        width="stretch")
    with b:
        C.header("Per-indicator score")
        st.plotly_chart(P.consensus_bar(s.readings), width="stretch")

    C.header("Indicator matrix")
    C.consensus_matrix(s)
    C.note("State mapping: Bearish −2 · Slightly Bearish −1 · Neutral 0 · "
           "Slightly Bullish +1 · Bullish +2. Score = mean state mapped to 0–100. "
           "Classification rules are documented in docs/METHODOLOGY.md.")

    C.disclaimer()
