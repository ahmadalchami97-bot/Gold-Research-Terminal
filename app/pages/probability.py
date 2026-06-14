"""Probability & Range — distribution, expected ranges, touch probabilities."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.ui import components as C
from app.ui import plotly_template as P
from app.ui.data import get_snapshot
from app.ui.theme import PALETTE


def render() -> None:
    snap = get_snapshot()
    dist = snap.distribution
    C.header("Probability & Expected Range",
             "Monte Carlo distribution, volatility-scaled ranges and first-passage "
             "touch probabilities")

    C.scorecards([
        {"label": "Realized vol (60d)", "value": f"{dist.sigma_realized*100:.1f}%"},
        {"label": "GARCH 1-day vol", "value": f"{dist.sigma_garch*100:.1f}%"},
        {"label": "Simulated paths", "value": f"{dist.n_paths:,}"},
        {"label": "Seed", "value": str(dist.seed), "sub": "reproducible"},
    ], per_row=4)
    C.note(dist.method)

    left, right = st.columns([1.1, 1])
    with left:
        C.header("Probability fan")
        st.plotly_chart(P.fan_chart(dist.spot, dist.horizons), width="stretch")
    with right:
        C.header("Forward volatility cone")
        st.plotly_chart(P.vol_cone(dist.garch_vol_cone), width="stretch")

    C.header("Expected ranges")
    rows = []
    for h in dist.horizons:
        rows.append({
            "Horizon": h.horizon, "Median": f"${h.median:,.0f}",
            "Expected (25–75%)": f"${h.expected_low:,.0f} – ${h.expected_high:,.0f}",
            "Tail (5–95%)": f"${h.wide_low:,.0f} – ${h.wide_high:,.0f}",
            "P(> spot)": f"{h.prob_above_spot*100:.0f}%",
            "σ (annual)": f"{h.sigma_annual*100:.0f}%"})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    left2, right2 = st.columns([1.2, 1])
    with left2:
        C.header("Terminal distribution")
        labels = {h.horizon: h for h in dist.horizons}
        pick = st.selectbox("Horizon", list(labels.keys()), index=1)
        h = labels[pick]
        st.plotly_chart(
            P.distribution_hist(dist.terminal_samples[pick], dist.spot, h.median,
                                h.expected_low, h.expected_high),
            width="stretch")
    with right2:
        C.header("Touch probabilities")
        trows = []
        for h in dist.horizons:
            for lbl, prob in h.touch_prob.items():
                trows.append({"Horizon": h.horizon, "Level": lbl,
                              "P(touch)": f"{prob*100:.0f}%"})
        st.dataframe(pd.DataFrame(trows), hide_index=True, width="stretch")
        C.note("Probability the path trades through the level at any point before "
               "the horizon (first-passage).")

    C.disclaimer()
