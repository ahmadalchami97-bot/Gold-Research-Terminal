"""Regime & Change Detection — "What changed?"."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.ui import components as C
from app.ui import plotly_template as P
from app.ui.data import get_snapshot
from app.ui.theme import PALETTE


def render() -> None:
    snap = get_snapshot()
    r = snap.regime
    C.header("Regime & Change Detection",
             "What changed — volatility, trend and correlation regimes, and structural breaks")

    decoupled_color = PALETTE["bear"] if r.decoupled else PALETTE["bull"]
    C.scorecards([
        {"label": "Volatility regime", "value": r.vol_regime,
         "sub": f"{r.vol_percentile:.0f}th percentile"},
        {"label": "Trend regime", "value": r.trend_regime.split("(")[0].strip()},
        {"label": "Real-yield ρ (60d)",
         "value": f"{r.real_yield_corr_60d:+.2f}" if r.real_yield_corr_60d == r.real_yield_corr_60d else "—",
         "sub": f"1y {r.real_yield_corr_long:+.2f}" if r.real_yield_corr_long == r.real_yield_corr_long else ""},
        {"label": "Coupling", "value": "Decoupled" if r.decoupled else "Coupled",
         "value_color": decoupled_color},
    ], per_row=4)

    left, right = st.columns([1, 1])
    with left:
        C.header("What changed")
        for b in r.what_changed:
            st.markdown(f"- {b}")
        C.note(r.correlation_regime)
    with right:
        C.header("Volatility percentile")
        st.plotly_chart(P.gauge(r.vol_percentile, "Realized-vol percentile (2y)",
                                suffix=""), width="stretch")

    C.header("Detected change points")
    if r.change_points:
        rows = [{"Date": cp.date, "Metric": cp.metric, "Description": cp.description}
                for cp in r.change_points]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        C.note("No material structural breaks detected in recent sessions.")

    C.disclaimer()
