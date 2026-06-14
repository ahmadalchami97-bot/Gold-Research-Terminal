"""Gold Research Terminal — Streamlit entry point.

Institutional gold research, outlook and probability analytics. Multi-page app
wired with st.navigation; each page is a thin renderer over the pure analytics
engines in app/engines.
"""
from __future__ import annotations

import streamlit as st

from app.config import get_settings
from app.ui.theme import apply_page_config, inject_css

apply_page_config()
inject_css()

from app.pages import (drivers, indicator_consensus, levels, market_state, news,  # noqa: E402
                       outlook, overview, probability, regime, research_note, risk)


def _sidebar() -> None:
    s = get_settings()
    st.sidebar.markdown("### 🪙 Gold Research Terminal")
    try:
        from app.ui.data import get_data
        prov = get_data().provenance
        from app.ui.components import data_badge_html
        st.sidebar.markdown(data_badge_html(prov), unsafe_allow_html=True)
    except Exception as exc:  # noqa: BLE001
        st.sidebar.caption(f"Data status unavailable: {exc}")

    st.sidebar.markdown("**Capabilities**")
    st.sidebar.caption(
        f"- Data mode: `{s.data_mode}`\n"
        f"- Live feeds: Yahoo (keyless), FRED {'on' if s.fred_enabled else 'off'}\n"
        f"- Narrative: {'Claude' if s.claude_enabled else 'deterministic'}\n"
        f"- News API: {'on' if s.newsapi_enabled else 'RSS only'}")

    if st.sidebar.button("🔄 Refresh data", width="stretch"):
        st.cache_data.clear()
        st.rerun()

    st.sidebar.caption(
        "Research & decision-support only — not investment advice. "
        "Figures are model estimates from public data and documented methodology.")


def main() -> None:
    _sidebar()
    nav = st.navigation({
        "Overview": [
            st.Page(overview.render, title="Executive Overview", icon="📊",
                    url_path="overview", default=True),
        ],
        "Diagnosis": [
            st.Page(market_state.render, title="Market State", icon="📈", url_path="market-state"),
            st.Page(drivers.render, title="Drivers & Attribution", icon="🧭", url_path="drivers"),
            st.Page(regime.render, title="Regime & Change", icon="🔀", url_path="regime"),
            st.Page(levels.render, title="Levels", icon="📐", url_path="levels"),
        ],
        "Forward view": [
            st.Page(outlook.render, title="Outlook Dashboard", icon="🎯", url_path="outlook"),
            st.Page(probability.render, title="Probability & Range", icon="🎲", url_path="probability"),
            st.Page(indicator_consensus.render, title="Indicator Consensus", icon="🧮",
                    url_path="consensus"),
        ],
        "Risk & flow": [
            st.Page(risk.render, title="Risk & Invalidation", icon="⚠️", url_path="risk"),
            st.Page(news.render, title="News & Events", icon="📰", url_path="news"),
        ],
        "Output": [
            st.Page(research_note.render, title="Research Note", icon="📝", url_path="research-note"),
        ],
    })
    nav.run()


main()
