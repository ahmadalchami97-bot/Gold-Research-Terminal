"""Yahoo Finance provider (keyless).

Uses the public v8 chart endpoint. Supplies gold OHLCV plus the market-priced
macro complex (dollar index, nominal 10y yield, VIX, S&P 500, silver). The
rates/inflation series that need FRED are handled by the FRED provider.
"""
from __future__ import annotations

import pandas as pd

from app.data.providers.base import ProviderError, get_json

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

# canonical macro key -> Yahoo symbol
MACRO_SYMBOLS = {
    "dxy": "DX-Y.NYB",
    "nominal_10y": "^TNX",
    "vix": "^VIX",
    "spx": "^GSPC",
    "silver": "SI=F",
}


def _chart(symbol: str, rng: str = "10y", interval: str = "1d",
           timeout: int = 12) -> pd.DataFrame:
    data = get_json(CHART_URL.format(symbol=symbol),
                    params={"range": rng, "interval": interval}, timeout=timeout)
    try:
        result = data["chart"]["result"][0]
        stamps = result["timestamp"]
        quote = result["indicators"]["quote"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError(f"unexpected Yahoo payload for {symbol}: {exc}") from exc

    idx = pd.to_datetime(stamps, unit="s", utc=True).tz_convert(None).normalize()
    frame = pd.DataFrame(
        {
            "open": quote.get("open"),
            "high": quote.get("high"),
            "low": quote.get("low"),
            "close": quote.get("close"),
            "volume": quote.get("volume"),
        },
        index=idx,
    )
    frame = frame[~frame.index.duplicated(keep="last")]
    frame = frame.dropna(subset=["close"])
    if frame.empty:
        raise ProviderError(f"empty Yahoo series for {symbol}")
    return frame


def fetch_gold_ohlcv(rng: str = "max", timeout: int = 12) -> pd.DataFrame:
    # "max" history so the weekly/monthly indicator matrix has enough bars
    # (e.g. a 200-period monthly EMA needs ~17 years of data).
    return _chart("GC=F", rng=rng, timeout=timeout)


def _scale_tnx(series: pd.Series) -> pd.Series:
    """^TNX is sometimes quoted as yield*10 (e.g. 42.0 == 4.20%)."""
    if series.dropna().median() > 20:
        return series / 10.0
    return series


def fetch_macro(rng: str = "10y", timeout: int = 12) -> pd.DataFrame:
    cols = {}
    for key, symbol in MACRO_SYMBOLS.items():
        try:
            close = _chart(symbol, rng=rng, timeout=timeout)["close"]
        except ProviderError:
            continue  # individual symbol may be unavailable; skip gracefully
        if key == "nominal_10y":
            close = _scale_tnx(close)
        cols[key] = close
    if not cols:
        raise ProviderError("no Yahoo macro series available")
    return pd.DataFrame(cols).sort_index()
