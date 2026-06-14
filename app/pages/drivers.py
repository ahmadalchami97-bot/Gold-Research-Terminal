"""Drivers & Attribution — "Why is it doing it?"."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.ui import components as C
from app.ui import plotly_template as P
from app.ui.data import get_snapshot


def render() -> None:
    snap = get_snapshot()
    d = snap.drivers
    C.header("Drivers & Attribution",
             "Why gold is moving — multi-factor regression, attribution and correlations")

    if not d.betas:
        C.note("Driver attribution is unavailable for the current dataset "
               "(macro driver series missing).")
        C.disclaimer()
        return

    C.scorecards([
        {"label": "Model R²", "value": f"{d.r_squared*100:.0f}%",
         "sub": f"{d.window_days}-day attribution window"},
        {"label": "Dominant driver", "value": d.dominant_driver.split("(")[0].strip()},
        {"label": "Actual move", "value": f"{d.actual_move_bps:+.0f} bps",
         "value_color": C.metric_color(d.actual_move_bps)},
        {"label": "Explained", "value": f"{d.explained_move_bps:+.0f} bps",
         "value_color": C.metric_color(d.explained_move_bps)},
        {"label": "Residual", "value": f"{d.residual_bps:+.0f} bps",
         "sub": "idiosyncratic"},
    ], per_row=5)

    left, right = st.columns([1, 1.1])
    with left:
        C.header("Move attribution")
        st.plotly_chart(P.attribution_bar(d.betas), width="stretch")
    with right:
        C.header("Factor sensitivities")
        rows = [{"Driver": b.label, "Beta": f"{b.beta:+.3f}", "t-stat": f"{b.t_stat:+.1f}",
                 "ρ 90d": f"{b.corr_90d:+.2f}", "Expected": b.corr_sign_expected,
                 "Contrib (bps)": f"{b.contribution_bps:+.0f}"} for b in d.betas]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        C.note("Beta = sensitivity of daily gold log-return to a unit change in the "
               "driver (% for index/equity log-returns; per percentage-point for yields). "
               "Robust (HC1) t-stats.")

    if d.rolling_corr:
        C.header("Rolling correlations (90-day)")
        tab1, tab2 = st.tabs(["Heatmap", "Lines"])
        with tab1:
            st.plotly_chart(P.corr_heatmap(d.rolling_corr, d.rolling_corr_dates),
                            width="stretch")
        with tab2:
            st.plotly_chart(P.rolling_corr_lines(d.rolling_corr, d.rolling_corr_dates),
                            width="stretch")

    C.disclaimer()
