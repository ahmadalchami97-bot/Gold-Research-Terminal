"""Regime engine — "What changed?"

Classifies the volatility, trend and correlation regimes, and detects
*explainable* change points (moving-average crosses, volatility-regime
transitions, 52-week breakouts, real-yield decoupling) plus a CUSUM break in
mean return. Explainability is preferred over black-box segmentation so a
research desk can defend each flag.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.data.types import MarketData
from app.engines.util import (TRADING_DAYS, annualize_vol, log_returns,
                              percentile_of_last)
from app.schemas import RegimeChange, RegimeState


def _vol_regime(percentile: float) -> str:
    if percentile >= 85:
        return "High"
    if percentile >= 60:
        return "Elevated"
    if percentile >= 25:
        return "Normal"
    return "Low"


def _trend_regime(close: pd.Series) -> str:
    if len(close) < 200:
        return "Indeterminate (short history)"
    ma50 = close.rolling(50).mean().iloc[-1]
    ma200 = close.rolling(200).mean().iloc[-1]
    price = close.iloc[-1]
    slope50 = close.rolling(50).mean().diff(10).iloc[-1]
    if price > ma200 and ma50 > ma200:
        return "Bull trend (price & 50d above 200d)"
    if price < ma200 and ma50 < ma200:
        return "Bear trend (price & 50d below 200d)"
    return "Transition / range" + (" (50d rising)" if slope50 > 0 else " (50d falling)")


def _cusum_break(returns: pd.Series, lookback: int = 252) -> RegimeChange | None:
    r = returns.iloc[-lookback:]
    if len(r) < 40:
        return None
    x = (r - r.mean()).cumsum()
    idx = int(np.argmax(np.abs(x.values)))
    if idx < 10 or idx > len(r) - 10:
        return None
    before = r.iloc[:idx].mean() * TRADING_DAYS * 100
    after = r.iloc[idx:].mean() * TRADING_DAYS * 100
    if abs(after - before) < 6:  # < 6% annualised drift shift: not material
        return None
    date = r.index[idx].strftime("%Y-%m-%d")
    return RegimeChange(date=date, metric="Mean return (CUSUM)",
                        description=f"Drift shifted from {before:+.0f}%/yr to "
                                    f"{after:+.0f}%/yr around {date}")


def _ma_cross(close: pd.Series) -> RegimeChange | None:
    if len(close) < 260:
        return None
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()
    diff = (ma50 - ma200).dropna().iloc[-TRADING_DAYS:]
    sign = np.sign(diff)
    flips = sign.diff().fillna(0)
    crosses = flips[flips != 0]
    if crosses.empty:
        return None
    date = crosses.index[-1]
    golden = diff.loc[date] > 0
    return RegimeChange(date=date.strftime("%Y-%m-%d"), metric="MA cross",
                        description=("Golden cross (50d crossed above 200d)" if golden
                                     else "Death cross (50d crossed below 200d)"))


def compute(data: MarketData) -> RegimeState:
    close = data.close
    ret = log_returns(close)
    as_of = close.index[-1].to_pydatetime()

    vol_series = ret.rolling(20).apply(lambda w: annualize_vol(w.std(ddof=1)), raw=False)
    vol_pct = percentile_of_last(vol_series.dropna(), window=min(504, len(vol_series.dropna())))
    vol_regime = _vol_regime(vol_pct)
    # annualized realized vol as PERCENT for display / bullet thresholds
    cur_vol = float(vol_series.dropna().iloc[-1]) * 100 if vol_series.notna().any() else float("nan")

    # correlation regime vs real yields
    decoupled = False
    corr60 = corr_long = float("nan")
    corr_regime = "Real-yield link unavailable"
    if data.has_macro("real_yield_10y"):
        ry_chg = data.macro["real_yield_10y"].reindex(close.index).ffill().diff()
        joined = pd.concat([ret, ry_chg], axis=1).dropna()
        joined.columns = ["g", "ry"]
        if len(joined) > 90:
            corr60 = float(joined["g"].iloc[-60:].corr(joined["ry"].iloc[-60:]))
            corr_long = float(joined["g"].iloc[-252:].corr(joined["ry"].iloc[-252:]))
            decoupled = corr_long < -0.3 and corr60 > -0.15
            if decoupled:
                corr_regime = "Decoupled — usual inverse real-yield link has weakened"
            elif corr60 < -0.3:
                corr_regime = "Coupled — gold tracking real yields inversely (typical)"
            else:
                corr_regime = "Mixed — real-yield sensitivity moderate"

    changes: list[RegimeChange] = []
    for fn in (_ma_cross, lambda c=close: _cusum_break(ret)):
        try:
            ch = fn(close) if fn is _ma_cross else _cusum_break(ret)
        except Exception:
            ch = None
        if ch:
            changes.append(ch)

    # 52-week breakout recency
    high_252 = close.iloc[-TRADING_DAYS:].max()
    low_252 = close.iloc[-TRADING_DAYS:].min()
    price = close.iloc[-1]
    if price >= high_252 * 0.999:
        changes.append(RegimeChange(date=as_of.strftime("%Y-%m-%d"),
                                    metric="Breakout", description="At / near a 52-week high"))
    elif price <= low_252 * 1.001:
        changes.append(RegimeChange(date=as_of.strftime("%Y-%m-%d"),
                                    metric="Breakdown", description="At / near a 52-week low"))

    # what-changed narrative bullets
    bullets: list[str] = []
    vol_3m_ago = vol_series.dropna()
    if len(vol_3m_ago) > 63:
        prev = float(vol_3m_ago.iloc[-63]) * 100
        delta = cur_vol - prev
        if abs(delta) > 2:
            bullets.append(f"Realized volatility {'rose' if delta > 0 else 'fell'} "
                           f"from {prev:.0f}% to {cur_vol:.0f}% over 3 months "
                           f"({vol_regime.lower()} regime, {vol_pct:.0f}th pctile).")
    if decoupled:
        bullets.append(f"Gold has decoupled from real yields: 60d correlation "
                       f"{corr60:+.2f} vs {corr_long:+.2f} over 1y.")
    for ch in changes:
        bullets.append(f"{ch.metric}: {ch.description}.")
    if not bullets:
        bullets.append("No material regime shifts detected in recent sessions.")

    return RegimeState(
        as_of=as_of, vol_regime=vol_regime, vol_percentile=round(vol_pct, 1),
        trend_regime=_trend_regime(close), correlation_regime=corr_regime,
        real_yield_corr_60d=round(corr60, 3) if not np.isnan(corr60) else float("nan"),
        real_yield_corr_long=round(corr_long, 3) if not np.isnan(corr_long) else float("nan"),
        decoupled=decoupled, change_points=changes, what_changed=bullets,
    )
