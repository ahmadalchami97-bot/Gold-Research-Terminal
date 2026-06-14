"""Small shared helpers for the analytics engines."""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252

# Canonical horizons used across outlook / distribution / range analytics.
HORIZON_DAYS: dict[str, int] = {"1W": 5, "1M": 21, "3M": 63}
HORIZON_LABELS: dict[str, str] = {"1W": "1 Week", "1M": "1 Month", "3M": "3 Months"}


def log_returns(series: pd.Series) -> pd.Series:
    return np.log(series.astype(float)).diff().dropna()


def simple_returns(series: pd.Series) -> pd.Series:
    return series.astype(float).pct_change().dropna()


def annualize_vol(daily_std: float) -> float:
    return float(daily_std) * np.sqrt(TRADING_DAYS)


def realized_vol(returns: pd.Series, window: int) -> float:
    if len(returns) < window:
        window = len(returns)
    if window < 2:
        return float("nan")
    return annualize_vol(returns.iloc[-window:].std(ddof=1))


def pct_change_over(series: pd.Series, periods: int) -> float | None:
    s = series.dropna()
    if len(s) <= periods:
        return None
    return float((s.iloc[-1] / s.iloc[-1 - periods] - 1.0) * 100.0)


def safe_pct(numer: float, denom: float) -> float:
    return float((numer / denom - 1.0) * 100.0) if denom else float("nan")


def clamp(x: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, x)))


def zscore_last(series: pd.Series, window: int) -> float:
    s = series.dropna().iloc[-window:]
    if len(s) < 3 or s.std(ddof=1) == 0:
        return 0.0
    return float((s.iloc[-1] - s.mean()) / s.std(ddof=1))


def percentile_of_last(series: pd.Series, window: int | None = None) -> float:
    s = series.dropna()
    if window:
        s = s.iloc[-window:]
    if len(s) < 2:
        return 50.0
    last = s.iloc[-1]
    return float((s < last).mean() * 100.0)
