"""News & Events — macro score, gold classification, what happened / means."""
from __future__ import annotations

import html

import streamlit as st

from app.narrative import get_news_digest
from app.ui import components as C
from app.ui import plotly_template as P
from app.ui.data import get_data, get_snapshot
from app.ui.theme import CLASS_COLORS, PALETTE


def render() -> None:
    data = get_data()
    snap = get_snapshot()
    digest = get_news_digest(data, snap)

    C.header("News & Events",
             "Gold-relevant headlines interpreted into a macro score, per-item "
             "classification and transmission to gold")

    overall_color = CLASS_COLORS.get(digest.overall_classification.value, PALETTE["neutral"])
    C.scorecards([
        {"label": "Macro score", "value": f"{digest.macro_score:+.0f}",
         "sub": "−100 … +100", "value_color": overall_color},
        {"label": "Gold read", "value": digest.overall_classification.value,
         "value_color": overall_color},
        {"label": "Bullish / Bearish", "value": f"{digest.bullish_count} / {digest.bearish_count}",
         "sub": f"{digest.neutral_count} neutral"},
        {"label": "Interpretation", "value": digest.generated_by.title(),
         "sub": "Claude" if digest.generated_by == "claude" else "rule-based lexicon"},
    ], per_row=4)

    g, t = st.columns([1, 2])
    with g:
        st.plotly_chart(P.gauge(digest.macro_score, "Macro score", vmin=-100, vmax=100),
                        width="stretch")
    with t:
        C.header("Macro read")
        st.markdown(digest.summary)

    C.header("Headlines")
    if not digest.items:
        C.note("No gold-relevant headlines available "
               "(live feeds unreachable in this environment; sample feed used offline).")
    for it in digest.items:
        color = CLASS_COLORS.get(it.classification.value, PALETTE["neutral"])
        when = it.published_at.strftime("%Y-%m-%d %H:%M") if it.published_at else ""
        link = (f'<a href="{html.escape(it.url)}" target="_blank" '
                f'style="color:{PALETTE["text"]};text-decoration:none">{html.escape(it.headline)}</a>'
                if it.url else html.escape(it.headline))
        st.markdown(
            f'<div class="grt-card" style="margin-bottom:.55rem;border-left:3px solid {color}">'
            f'<div style="display:flex;justify-content:space-between;gap:1rem">'
            f'<span style="font-weight:600;font-size:.96rem">{link}</span>'
            f'{C.pill_html(it.classification.value, color)}</div>'
            f'<div class="grt-note" style="margin-top:.35rem"><b>What happened:</b> '
            f'{html.escape(it.what_happened)}</div>'
            f'<div class="grt-note"><b>What it means for gold:</b> {html.escape(it.what_it_means)}</div>'
            f'<div style="color:{PALETTE["muted"]};font-size:.72rem;margin-top:.3rem">'
            f'{html.escape(it.source)} · {when}</div></div>', unsafe_allow_html=True)

    C.disclaimer()
