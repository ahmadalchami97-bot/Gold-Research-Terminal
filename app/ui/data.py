"""Cached data + snapshot accessors for the Streamlit pages."""
from __future__ import annotations

import streamlit as st

from app.config import get_settings
from app.data import service
from app.data.types import MarketData
from app.engines.snapshot import build_snapshot
from app.schemas import TerminalSnapshot


def get_data() -> MarketData:
    return service.get_market_data()


@st.cache_data(show_spinner="Running analytics…")
def _build(cache_key: tuple) -> TerminalSnapshot:
    # cache_key changes when the underlying dataset changes; data itself is
    # resolved via the (separately cached) service call.
    data = service.get_market_data()
    return build_snapshot(data, mc_seed=get_settings().mc_seed)


def get_snapshot() -> TerminalSnapshot:
    data = service.get_market_data()
    mode = data.provenance.mode if data.provenance else "?"
    key = (data.as_of.isoformat(), mode, get_settings().mc_seed)
    return _build(key)
