"""Institutional dark theme: palette, state colors, CSS, page config."""
from __future__ import annotations

import streamlit as st

from app.config import APP_NAME

# Core palette (kept in sync with the CSS block below and the Plotly template).
PALETTE = {
    "bg": "#0E1117",
    "panel": "#171B24",
    "panel2": "#1E2430",
    "border": "#2A3140",
    "grid": "#232A36",
    "text": "#E6E8EC",
    "muted": "#8B93A7",
    "gold": "#C8A15A",
    "gold_soft": "#D8B87E",
    "bull": "#2FB67A",
    "bull_soft": "#3FCB8C",
    "bear": "#E0564E",
    "bear_soft": "#F06A62",
    "neutral": "#9AA3B2",
    "blue": "#5B8DEF",
}

# 5-state indicator / direction colors (diverging bear→bull).
STATE_COLORS = {
    "Bearish": "#E0564E",
    "Slightly Bearish": "#E89A6B",
    "Neutral": "#9AA3B2",
    "Slightly Bullish": "#7FC59B",
    "Bullish": "#2FB67A",
    # direction synonyms
    "Neutral-Bearish": "#E89A6B",
    "Neutral-Bullish": "#7FC59B",
}

CLASS_COLORS = {"Bullish": "#2FB67A", "Neutral": "#9AA3B2", "Bearish": "#E0564E"}


def state_color(label: str) -> str:
    return STATE_COLORS.get(label, PALETTE["neutral"])


def sentiment_color(value: float, neutral_band: float = 0.0) -> str:
    if value > neutral_band:
        return PALETTE["bull"]
    if value < -neutral_band:
        return PALETTE["bear"]
    return PALETTE["neutral"]


_CSS = """
<style>
/* tighten the default Streamlit frame */
.block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1500px; }
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }

html, body, [class*="css"] { font-family: 'Inter','Segoe UI',system-ui,sans-serif; }

/* section headers */
.grt-h { font-size: 1.02rem; font-weight: 700; letter-spacing: .04em;
  text-transform: uppercase; color: #C8A15A; border-bottom: 1px solid #2A3140;
  padding-bottom: .35rem; margin: 1.3rem 0 .8rem 0; }
.grt-sub { color: #8B93A7; font-size: .86rem; margin: -.3rem 0 .9rem 0; }

/* scorecards */
.grt-card { background: #171B24; border: 1px solid #2A3140; border-radius: 10px;
  padding: .85rem 1rem; height: 100%; }
.grt-card .lbl { color: #8B93A7; font-size: .72rem; text-transform: uppercase;
  letter-spacing: .06em; }
.grt-card .val { color: #E6E8EC; font-size: 1.5rem; font-weight: 700;
  line-height: 1.25; margin-top: .15rem; }
.grt-card .sub { font-size: .8rem; margin-top: .15rem; }

/* pills / badges */
.grt-pill { display: inline-block; padding: .12rem .6rem; border-radius: 999px;
  font-size: .78rem; font-weight: 700; }
.grt-badge { display: inline-block; padding: .14rem .55rem; border-radius: 5px;
  font-size: .72rem; font-weight: 600; border: 1px solid #2A3140; color: #8B93A7;
  background: #1E2430; }

/* hero header bar */
.grt-hero { display: flex; align-items: baseline; gap: .8rem; }
.grt-hero .name { font-size: 1.55rem; font-weight: 800; color: #E6E8EC; }
.grt-hero .accent { color: #C8A15A; }
.grt-hero .tag { color: #8B93A7; font-size: .9rem; }

/* dataframe polish */
[data-testid="stDataFrame"] { border: 1px solid #2A3140; border-radius: 8px; }

.grt-disc { color: #6B7280; font-size: .74rem; border-top: 1px solid #2A3140;
  margin-top: 2rem; padding-top: .7rem; }
.grt-note { color:#8B93A7; font-size:.82rem; }
</style>
"""


def apply_page_config() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon="🪙", layout="wide",
                       initial_sidebar_state="expanded")


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
