"""Risk & Invalidation — "What could invalidate the thesis?"."""
from __future__ import annotations

import html

import streamlit as st

from app.ui import components as C
from app.ui.data import get_snapshot
from app.ui.theme import PALETTE

_SEV = {"High": PALETTE["bear"], "Medium": PALETTE["gold"], "Low": PALETTE["muted"]}


def render() -> None:
    snap = get_snapshot()
    rk = snap.risk
    C.header("Risk & Invalidation",
             "Tail risk, drawdown analogs and the explicit conditions that would "
             "negate the thesis")

    C.scorecards([
        {"label": "VaR 95% (1d)", "value": f"{rk.var_95_1d_pct:.1f}%", "value_color": PALETTE["bear"]},
        {"label": "CVaR 95% (1d)", "value": f"{rk.cvar_95_1d_pct:.1f}%", "value_color": PALETTE["bear"]},
        {"label": "VaR 99% (1d)", "value": f"{rk.var_99_1d_pct:.1f}%"},
        {"label": "VaR 95% (1m)", "value": f"{rk.var_95_1m_pct:.1f}%"},
        {"label": "Max DD (1y)", "value": f"{rk.max_drawdown_1y_pct:.1f}%", "value_color": PALETTE["bear"]},
    ], per_row=5)

    C.header("Invalidation levels")
    C.scorecards([
        {"label": "Bull thesis fails below", "value": f"${rk.bull_invalidation.level:,.0f}",
         "sub": rk.bull_invalidation.condition, "value_color": PALETTE["bear"]},
        {"label": "Bear thesis fails above", "value": f"${rk.bear_invalidation.level:,.0f}",
         "sub": rk.bear_invalidation.condition, "value_color": PALETTE["bull"]},
    ], per_row=2)

    C.header("Risk triggers")
    if rk.triggers:
        for t in rk.triggers:
            color = _SEV.get(t.severity, PALETTE["muted"])
            st.markdown(
                f'<div class="grt-card" style="margin-bottom:.5rem">'
                f'{C.pill_html(t.severity, color)} '
                f'<b style="color:{PALETTE["text"]};margin-left:.4rem">{html.escape(t.name)}</b>'
                f'<div style="margin-top:.3rem;color:{PALETTE["gold_soft"]};font-size:.86rem">'
                f'Trigger: {html.escape(t.condition)}</div>'
                f'<div class="grt-note" style="margin-top:.2rem">{html.escape(t.rationale)}</div>'
                f'</div>', unsafe_allow_html=True)
    else:
        C.note("No elevated risk triggers flagged.")

    if rk.correlation_breakdown:
        C.note("⚠ Real-yield decoupling active — the usual macro anchor has weakened.")
    for n in rk.notes:
        C.note(n)

    C.disclaimer()
