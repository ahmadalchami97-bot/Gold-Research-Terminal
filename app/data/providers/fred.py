"""FRED provider for the rates / inflation complex.

Prefers the official API when ``FRED_API_KEY`` is set, otherwise falls back to
the keyless ``fredgraph.csv`` endpoint. Supplies the series that have no clean
keyless market source: the 10y TIPS real yield and 10y breakeven inflation.
"""
from __future__ import annotations

import pandas as pd

from app.data.providers.base import ProviderError, get_csv, get_json

API_URL = "https://api.stlouisfed.org/fred/series/observations"
CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"

# canonical key -> FRED series id
FRED_SERIES = {
    "real_yield_10y": "DFII10",
    "breakeven_10y": "T10YIE",
    "nominal_10y": "DGS10",   # fallback if Yahoo ^TNX is unavailable
}


def fetch_series(series_id: str, api_key: str | None = None,
                 timeout: int = 12) -> pd.Series:
    if api_key:
        data = get_json(
            API_URL,
            params={
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "observation_start": "2015-01-01",
            },
            timeout=timeout,
        )
        obs = data.get("observations", [])
        if not obs:
            raise ProviderError(f"FRED returned no observations for {series_id}")
        frame = pd.DataFrame(obs)
        idx = pd.to_datetime(frame["date"])
        values = pd.to_numeric(frame["value"], errors="coerce")
        return pd.Series(values.values, index=idx, name=series_id).dropna()

    # Keyless CSV fallback.
    frame = get_csv(CSV_URL, params={"id": series_id}, timeout=timeout)
    date_col = frame.columns[0]
    val_col = frame.columns[-1]
    idx = pd.to_datetime(frame[date_col])
    values = pd.to_numeric(frame[val_col], errors="coerce")
    series = pd.Series(values.values, index=idx, name=series_id).dropna()
    if series.empty:
        raise ProviderError(f"empty FRED series {series_id}")
    return series


def fetch_macro(api_key: str | None = None, timeout: int = 12) -> pd.DataFrame:
    cols = {}
    for key, sid in FRED_SERIES.items():
        try:
            cols[key] = fetch_series(sid, api_key=api_key, timeout=timeout)
        except ProviderError:
            continue
    if not cols:
        raise ProviderError("no FRED series available")
    return pd.DataFrame(cols).sort_index()
