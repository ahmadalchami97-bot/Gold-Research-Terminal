"""Levels — "What levels matter?"."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.ui import components as C
from app.ui import plotly_template as P
from app.ui.data import get_data, get_snapshot
from app.ui.theme import PALETTE


def _level_table(levels):
    return pd.DataFrame([{"Price": f"${l.price:,.0f}", "Distance": f"{l.distance_pct:+.1f}%",
                          "Type": l.label, "Source": l.source} for l in levels])


def render() -> None:
    snap = get_snapshot()
    data = get_data()
    lm = snap.levels
    C.header("Levels", "What levels matter — confluence of swings, pivots, MAs, "
                       "Fibonacci, round numbers and volatility bands")

    ns, nr = lm.nearest_support, lm.nearest_resistance
    C.scorecards([
        {"label": "Spot", "value": f"${lm.price:,.0f}"},
        {"label": "Nearest support", "value": f"${ns.price:,.0f}" if ns else "—",
         "sub": f"{ns.distance_pct:+.1f}% · {ns.label}" if ns else "",
         "value_color": PALETTE["bull"]},
        {"label": "Nearest resistance", "value": f"${nr.price:,.0f}" if nr else "—",
         "sub": f"{nr.distance_pct:+.1f}% · {nr.label}" if nr else "",
         "value_color": PALETTE["bear"]},
        {"label": "Mapped levels", "value": str(len(lm.all_levels))},
    ], per_row=4)

    C.header("Annotated price map")
    st.plotly_chart(P.price_chart(data.prices, levels=lm.all_levels, show_ma=(50, 200)),
                    width="stretch")

    left, right = st.columns(2)
    with left:
        C.header("Resistance overhead")
        st.dataframe(_level_table(lm.resistances), hide_index=True, width="stretch")
    with right:
        C.header("Support below")
        st.dataframe(_level_table(lm.supports), hide_index=True, width="stretch")

    C.disclaimer()
