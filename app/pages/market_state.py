"""Market State — "What is gold doing?"."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.ui import components as C
from app.ui import plotly_template as P
from app.ui.data import get_data, get_snapshot


def render() -> None:
    snap = get_snapshot()
    data = get_data()
    ms = snap.market_state
    C.header("Market State", "What is gold doing — price action, trend, volatility and range")

    C.scorecards([
        {"label": "Spot", "value": f"${ms.price:,.0f}",
         "sub": f"{ms.change_pct_1d:+.2f}% today", "sub_color": C.metric_color(ms.change_pct_1d)},
        {"label": "ATR (14)", "value": f"{ms.atr_pct:.2f}%"},
        {"label": "From ATH", "value": f"{ms.drawdown_from_ath_pct:+.1f}%",
         "sub": f"ATH ${ms.ath:,.0f}", "value_color": C.metric_color(ms.drawdown_from_ath_pct)},
        {"label": "52w range", "value": f"{ms.pct_of_52w_range:.0f}%",
         "sub": f"${ms.low_52w:,.0f}–${ms.high_52w:,.0f}"},
        {"label": "Gold/Silver", "value": f"{ms.gold_silver_ratio:.1f}" if ms.gold_silver_ratio else "—"},
    ], per_row=5)

    C.header("Returns")
    C.scorecards([
        {"label": r.horizon, "value": f"{r.pct:+.1f}%" if r.pct is not None else "—",
         "value_color": C.metric_color(r.pct or 0)} for r in ms.returns], per_row=7)

    left, right = st.columns([1.6, 1])
    with left:
        C.header("Price & moving averages")
        st.plotly_chart(P.price_chart(data.prices, levels=None, show_ma=(50, 200)),
                        width="stretch")
    with right:
        C.header("Trend posture")
        C.note(ms.trend_state)
        ma_rows = [{"MA": f"{m.window}DMA", "Value": f"${m.value:,.0f}",
                    "Px vs MA": f"{m.pct_distance:+.1f}%",
                    "Posture": "Above" if m.above else "Below"} for m in ms.moving_averages]
        st.dataframe(pd.DataFrame(ma_rows), hide_index=True, width="stretch")
        C.header("Realized volatility")
        vol_rows = [{"Window": k, "Annualized": f"{v:.1f}%"} for k, v in ms.realized_vol.items()]
        st.dataframe(pd.DataFrame(vol_rows), hide_index=True, width="stretch")

    C.disclaimer()
