"""Levels engine — "What levels matter?"

Synthesises support/resistance from multiple, independent methods: swing
highs/lows, classic pivot points, moving averages, Fibonacci retracements of the
dominant swing, psychological round numbers, and forward volatility bands.
Levels are de-duplicated (clustered) and ranked by distance from spot.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema

from app.data.types import MarketData
from app.engines.util import HORIZON_DAYS, TRADING_DAYS, log_returns, realized_vol
from app.schemas import Level, LevelMap

FIB_RATIOS = [0.236, 0.382, 0.5, 0.618, 0.786]


def _swings(close: pd.Series, order: int = 8, lookback: int = 400):
    s = close.iloc[-lookback:]
    arr = s.values
    hi_idx = argrelextrema(arr, np.greater, order=order)[0]
    lo_idx = argrelextrema(arr, np.less, order=order)[0]
    highs = [float(arr[i]) for i in hi_idx]
    lows = [float(arr[i]) for i in lo_idx]
    return highs, lows


def _pivots(prices: pd.DataFrame, window: int = 21) -> dict[str, float]:
    recent = prices.iloc[-window:]
    h, l, c = float(recent["high"].max()), float(recent["low"].min()), float(recent["close"].iloc[-1])
    p = (h + l + c) / 3
    return {"Pivot": p, "R1": 2 * p - l, "S1": 2 * p - h,
            "R2": p + (h - l), "S2": p - (h - l)}


def _round_levels(price: float) -> list[float]:
    step = 100 if price >= 1000 else 50 if price >= 200 else 10
    base = round(price / step) * step
    return [base + k * step for k in (-2, -1, 0, 1, 2)]


def _cluster(levels: list[Level], price: float, tol_pct: float = 0.4) -> list[Level]:
    """Merge levels within tol_pct of each other, combining their labels."""
    if not levels:
        return []
    levels = sorted(levels, key=lambda x: x.price)
    tol = price * tol_pct / 100
    clusters: list[list[Level]] = [[levels[0]]]
    for lv in levels[1:]:
        if abs(lv.price - clusters[-1][-1].price) <= tol:
            clusters[-1].append(lv)
        else:
            clusters.append([lv])

    merged: list[Level] = []
    for group in clusters:
        avg = float(np.mean([g.price for g in group]))
        labels = " · ".join(dict.fromkeys(g.label for g in group))
        sources = ", ".join(dict.fromkeys(g.kind for g in group))
        kind = "resistance" if avg >= price else "support"
        merged.append(Level(price=round(avg, 2), kind=kind, label=labels,
                            source=sources, distance_pct=round((avg / price - 1) * 100, 2)))
    return merged


def compute(data: MarketData) -> LevelMap:
    prices = data.prices
    close = data.close
    price = float(close.iloc[-1])
    raw: list[Level] = []

    def add(value: float, label: str, source: str):
        if value <= 0 or not np.isfinite(value):
            return
        kind = "resistance" if value >= price else "support"
        raw.append(Level(price=round(float(value), 2), kind=kind, label=label,
                        source=source, distance_pct=round((value / price - 1) * 100, 2)))

    highs, lows = _swings(close)
    for h in highs:
        add(h, "Swing high", "swing")
    for l in lows:
        add(l, "Swing low", "swing")

    for name, val in _pivots(prices).items():
        add(val, name, "pivot")

    for w in (50, 100, 200):
        if len(close) >= w:
            add(float(close.rolling(w).mean().iloc[-1]), f"{w}DMA", "ma")

    win = close.iloc[-180:] if len(close) > 180 else close
    hi, lo = float(win.max()), float(win.min())
    for r in FIB_RATIOS:
        add(lo + (hi - lo) * r, f"Fib {r*100:.1f}%", "fib")

    for rnd in _round_levels(price):
        add(rnd, f"Round {rnd:,.0f}", "round")

    sigma = realized_vol(log_returns(close), 20)
    for horizon_days, n_sig in [(HORIZON_DAYS["1M"], 1), (HORIZON_DAYS["1M"], 2)]:
        move = price * sigma * np.sqrt(horizon_days / TRADING_DAYS) * n_sig
        add(price + move, f"+{n_sig}σ 1M band", "band")
        add(price - move, f"-{n_sig}σ 1M band", "band")

    clustered = _cluster(raw, price)
    supports = sorted([l for l in clustered if l.price < price],
                      key=lambda x: x.price, reverse=True)
    resistances = sorted([l for l in clustered if l.price >= price],
                         key=lambda x: x.price)

    return LevelMap(
        as_of=close.index[-1].to_pydatetime(), price=price,
        supports=supports, resistances=resistances,
        nearest_support=supports[0] if supports else None,
        nearest_resistance=resistances[0] if resistances else None,
        all_levels=sorted(clustered, key=lambda x: x.price),
    )
