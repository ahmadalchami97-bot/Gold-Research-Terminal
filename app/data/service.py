"""Data orchestration: assemble a :class:`MarketData` from live providers,
falling back to the bundled snapshot. The only data entrypoint the app uses.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from app.config import Settings, get_settings
from app.data.providers import cftc, demo, fred, news, yahoo
from app.data.providers.base import ProviderError
from app.data.types import MarketData
from app.schemas import DataProvenance, SeriesStatus


def _status(key: str, source: str, ok: bool, as_of: datetime | None,
            detail: str = "") -> SeriesStatus:
    return SeriesStatus(key=key, source=source, mode="live" if ok else "cached",
                        as_of=as_of, ok=ok, detail=detail)


def build_live(settings: Settings) -> MarketData:
    """Assemble live data. Raises if the core price series is unavailable."""
    statuses: list[SeriesStatus] = []

    prices = yahoo.fetch_gold_ohlcv(timeout=settings.request_timeout)
    gold_asof = prices.index[-1].to_pydatetime()
    statuses.append(_status("gold", "Yahoo Finance", True, gold_asof))

    # Market-priced macro from Yahoo.
    try:
        macro = yahoo.fetch_macro(timeout=settings.request_timeout)
        for col in macro.columns:
            statuses.append(_status(col, "Yahoo Finance", True, gold_asof))
    except ProviderError as exc:
        macro = pd.DataFrame()
        statuses.append(_status("macro", "Yahoo Finance", False, None, str(exc)[:120]))

    # Rates / inflation complex from FRED (key optional via fredgraph CSV).
    try:
        fred_macro = fred.fetch_macro(api_key=settings.fred_api_key,
                                      timeout=settings.request_timeout)
        for col in fred_macro.columns:
            if col == "nominal_10y" and "nominal_10y" in macro.columns:
                continue  # Yahoo ^TNX already supplied it
            macro[col] = fred_macro[col]
            statuses.append(_status(col, "FRED", True, fred_macro[col].dropna().index[-1].to_pydatetime()))
    except ProviderError as exc:
        statuses.append(_status("real_yield_10y", "FRED", False, None, str(exc)[:120]))

    macro = macro.sort_index() if not macro.empty else macro

    # Positioning (best-effort).
    positioning = None
    try:
        positioning = cftc.fetch_positioning(timeout=settings.request_timeout)
        statuses.append(_status("positioning", "CFTC", True,
                                positioning.index[-1].to_pydatetime()))
    except (ProviderError, Exception) as exc:  # noqa: BLE001 - never fatal
        statuses.append(_status("positioning", "CFTC", False, None, str(exc)[:120]))

    # News (best-effort).
    news_raw: list[dict] = []
    try:
        news_raw = news.fetch_news(newsapi_key=settings.newsapi_key,
                                   timeout=settings.request_timeout)
        statuses.append(_status("news", "RSS/NewsAPI", True, datetime.now(timezone.utc)))
    except (ProviderError, Exception) as exc:  # noqa: BLE001
        statuses.append(_status("news", "RSS/NewsAPI", False, None, str(exc)[:120]))

    provenance = DataProvenance(mode="live", generated_at=datetime.now(timezone.utc),
                                series=statuses)
    return MarketData(prices=prices, macro=macro, positioning=positioning,
                      news_raw=news_raw, provenance=provenance)


def load_market_data(settings: Settings | None = None) -> MarketData:
    """Resolve the dataset honouring DATA_MODE, with snapshot fallback."""
    settings = settings or get_settings()

    if settings.force_demo:
        return demo.load()

    try:
        return build_live(settings)
    except Exception as exc:  # noqa: BLE001 - degrade, never crash the UI
        data = demo.load()
        if data.provenance is not None:
            data.provenance.series.append(
                SeriesStatus(key="live-feed", source="service", mode="cached",
                             as_of=None, ok=False,
                             detail=f"live unavailable, using snapshot: {exc}"[:160])
            )
        return data


# --- Streamlit caching (only when a script run context exists) --------------
def _in_runtime() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except Exception:
        return False


def get_market_data() -> MarketData:
    """Cached entrypoint for the Streamlit app; direct call elsewhere."""
    settings = get_settings()
    if _in_runtime():
        import streamlit as st

        @st.cache_data(ttl=settings.ttl_prices, show_spinner="Loading market data…")
        def _cached(mode: str) -> MarketData:
            return load_market_data(settings)

        return _cached(settings.data_mode)
    return load_market_data(settings)
