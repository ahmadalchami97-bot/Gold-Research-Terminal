"""Market state engine — "What is gold doing?"

Multi-horizon returns, moving-average posture, realized volatility, ATR,
52-week range, drawdown from all-time high and a trend classification.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.data.types import MarketData
from app.engines.util import (TRADING_DAYS, annualize_vol, log_returns,
                              pct_change_over, realized_vol)
from app.schemas import MarketState, MovingAverageStat, ReturnStat

MA_WINDOWS = [20, 50, 100, 200]
RETURN_HORIZONS = [("1D", 1), ("1W", 5), ("1M", 21), ("3M", 63),
                   ("1Y", 252), ("5Y", 1260)]


def _atr_pct(prices: pd.DataFrame, window: int = 14) -> float:
    high, low, close = prices["high"], prices["low"], prices["close"]
    prev_close = close.shift(1)
    tr = pd.concat([(high - low).abs(),
                    (high - prev_close).abs(),
                    (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(window).mean().iloc[-1]
    return float(atr / close.iloc[-1] * 100.0)


def _ytd_return(close: pd.Series) -> float | None:
    year = close.index[-1].year
    ytd = close[close.index.year == year]
    if len(ytd) < 2:
        return None
    return float((close.iloc[-1] / ytd.iloc[0] - 1.0) * 100.0)


def _trend_state(price: float, mas: list[MovingAverageStat]) -> str:
    above = [m.above for m in mas]
    by_window = {m.window: m for m in mas}
    stacked_up = (200 in by_window and 50 in by_window
                  and by_window[50].value > by_window[200].value)
    if all(above):
        return "Uptrend — price above all key moving averages" + (
            " (50d > 200d, golden-cross posture)" if stacked_up else "")
    if not any(above):
        return "Downtrend — price below all key moving averages"
    if above[0] and above[1]:
        return "Constructive — price above short-term averages, mixed longer term"
    return "Corrective — price below short-term averages within a broader trend"


def compute(data: MarketData) -> MarketState:
    prices = data.prices
    close = data.close
    price = float(close.iloc[-1])
    prior = float(close.iloc[-2]) if len(close) > 1 else price

    returns = [ReturnStat(h, pct_change_over(close, p)) for h, p in RETURN_HORIZONS]
    returns.append(ReturnStat("YTD", _ytd_return(close)))
    # keep a sensible display order
    order = ["1D", "1W", "1M", "3M", "YTD", "1Y", "5Y"]
    returns.sort(key=lambda r: order.index(r.horizon) if r.horizon in order else 99)

    mas: list[MovingAverageStat] = []
    for w in MA_WINDOWS:
        if len(close) >= w:
            val = float(close.rolling(w).mean().iloc[-1])
            mas.append(MovingAverageStat(window=w, value=val,
                                         pct_distance=float((price / val - 1) * 100),
                                         above=price >= val))

    log_ret = log_returns(close)
    # vols stored as annualized PERCENT to match the rest of the terminal
    rv = {f"{w}d": realized_vol(log_ret, w) * 100 for w in (10, 20, 30)}
    ann_vol = realized_vol(log_ret, 20) * 100

    high_52w = float(close.iloc[-TRADING_DAYS:].max())
    low_52w = float(close.iloc[-TRADING_DAYS:].min())
    ath = float(close.max())
    rng = high_52w - low_52w
    pct_range = float((price - low_52w) / rng * 100) if rng else 50.0

    gsr = None
    if data.has_macro("silver"):
        silver = data.macro["silver"].reindex(close.index).ffill().iloc[-1]
        if silver and not np.isnan(silver):
            gsr = float(price / silver)

    return MarketState(
        as_of=close.index[-1].to_pydatetime(),
        price=price, prior_close=prior,
        change_pct_1d=float((price / prior - 1) * 100),
        returns=returns, moving_averages=mas,
        realized_vol=rv, annualized_vol=ann_vol,
        atr_pct=_atr_pct(prices), high_52w=high_52w, low_52w=low_52w, ath=ath,
        drawdown_from_ath_pct=float((price / ath - 1) * 100),
        pct_of_52w_range=pct_range,
        trend_state=_trend_state(price, mas),
        gold_silver_ratio=gsr,
    )
