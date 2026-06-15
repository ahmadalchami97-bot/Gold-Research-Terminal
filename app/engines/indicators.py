"""Indicator consensus engine.

Computes 14 technical indicators, classifies each into a 5-state vocabulary
(Bearish / Slightly Bearish / Neutral / Slightly Bullish / Bullish), then
aggregates to bullish/neutral/bearish percentages and a 0-100 institutional
score. Every classification rule is deterministic and documented in
docs/METHODOLOGY.md.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.data.types import MarketData
from app.schemas import (
    INDICATOR_SCORE,
    ConsensusSummary,
    IndicatorReading,
    IndicatorState,
    TimeframeConsensus,
)

S = IndicatorState  # local alias


# --------------------------------------------------------------------------- #
# primitives
# --------------------------------------------------------------------------- #
def _wilder(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(alpha=1 / n, adjust=False).mean()


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    rs = _wilder(gain, n) / _wilder(loss, n).replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def _band_state(value: float, bands: list[tuple[float, IndicatorState]],
                default: IndicatorState) -> IndicatorState:
    for threshold, state in bands:
        if value >= threshold:
            return state
    return default


# --------------------------------------------------------------------------- #
# individual indicators -> (value_str, state, rationale)
# --------------------------------------------------------------------------- #
def ind_rsi(close: pd.Series):
    rsi = float(_rsi(close).iloc[-1])
    state = _band_state(rsi, [
        (70, S.SLIGHTLY_BULLISH),  # overbought: strong but tempered
        (60, S.BULLISH),
        (52, S.SLIGHTLY_BULLISH),
        (48, S.NEUTRAL),
        (40, S.SLIGHTLY_BEARISH),
        (30, S.BEARISH),
    ], default=S.SLIGHTLY_BEARISH)         # <30 oversold: bounce potential
    return f"{rsi:.1f}", state, f"RSI(14) at {rsi:.1f}"


def ind_macd(close: pd.Series):
    macd = _ema(close, 12) - _ema(close, 26)
    signal = _ema(macd, 9)
    hist = float((macd - signal).iloc[-1])
    m, sig = float(macd.iloc[-1]), float(signal.iloc[-1])
    price = float(close.iloc[-1])
    if abs(hist) < 0.0004 * price:
        state = S.NEUTRAL
    elif m > sig and m > 0:
        state = S.BULLISH
    elif m > sig:
        state = S.SLIGHTLY_BULLISH
    elif m < sig and m < 0:
        state = S.BEARISH
    else:
        state = S.SLIGHTLY_BEARISH
    return f"hist {hist:+.1f}", state, f"MACD {m:+.1f} vs signal {sig:+.1f}"


def _stoch_kd(high, low, close, n=14, k=3, d=3):
    ll = low.rolling(n).min()
    hh = high.rolling(n).max()
    raw = 100 * (close - ll) / (hh - ll).replace(0, np.nan)
    k_line = raw.rolling(k).mean()
    d_line = k_line.rolling(d).mean()
    return k_line, d_line


def _stoch_state(k: float, d: float) -> IndicatorState:
    cross = k - d
    if k > 80:
        return S.SLIGHTLY_BEARISH if cross < 0 else S.SLIGHTLY_BULLISH
    if k < 20:
        return S.SLIGHTLY_BULLISH if cross > 0 else S.SLIGHTLY_BEARISH
    if cross > 0 and k > 55:
        return S.BULLISH
    if cross > 0:
        return S.SLIGHTLY_BULLISH
    if cross < 0 and k < 45:
        return S.BEARISH
    if cross < 0:
        return S.SLIGHTLY_BEARISH
    return S.NEUTRAL


def ind_stochastic(prices: pd.DataFrame):
    k_line, d_line = _stoch_kd(prices["high"], prices["low"], prices["close"])
    k, d = float(k_line.iloc[-1]), float(d_line.iloc[-1])
    return f"%K {k:.0f}/%D {d:.0f}", _stoch_state(k, d), f"Stochastic %K {k:.1f}, %D {d:.1f}"


def ind_stoch_rsi(close: pd.Series, n: int = 14):
    rsi = _rsi(close, n)
    ll = rsi.rolling(n).min()
    hh = rsi.rolling(n).max()
    stoch = 100 * (rsi - ll) / (hh - ll).replace(0, np.nan)
    k = stoch.rolling(3).mean()
    d = k.rolling(3).mean()
    kv, dv = float(k.iloc[-1]), float(d.iloc[-1])
    return f"%K {kv:.0f}", _stoch_state(kv, dv), f"Stoch RSI %K {kv:.1f}, %D {dv:.1f}"


def ind_adx(prices: pd.DataFrame, n: int = 14):
    high, low, close = prices["high"], prices["low"], prices["close"]
    up = high.diff()
    down = -low.diff()
    plus_dm = ((up > down) & (up > 0)) * up
    minus_dm = ((down > up) & (down > 0)) * down
    tr = pd.concat([(high - low),
                    (high - close.shift()).abs(),
                    (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = _wilder(tr, n).replace(0, np.nan)
    plus_di = 100 * _wilder(plus_dm, n) / atr
    minus_di = 100 * _wilder(minus_dm, n) / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = float(_wilder(dx.fillna(0), n).iloc[-1])
    pdi, mdi = float(plus_di.iloc[-1]), float(minus_di.iloc[-1])
    if adx < 20:
        state = S.NEUTRAL
    elif pdi > mdi:
        state = S.BULLISH if adx >= 25 else S.SLIGHTLY_BULLISH
    else:
        state = S.BEARISH if adx >= 25 else S.SLIGHTLY_BEARISH
    return f"ADX {adx:.0f}", state, f"ADX {adx:.1f}, +DI {pdi:.0f} / -DI {mdi:.0f}"


def ind_ema(close: pd.Series, span: int, thr: float = 0.75):
    if len(close) < span:
        return "n/a", S.NEUTRAL, f"EMA{span}: insufficient history"
    ema = float(_ema(close, span).iloc[-1])
    price = float(close.iloc[-1])
    dist = (price / ema - 1) * 100
    if dist > thr:
        state = S.BULLISH
    elif dist > 0.1:
        state = S.SLIGHTLY_BULLISH
    elif dist < -thr:
        state = S.BEARISH
    elif dist < -0.1:
        state = S.SLIGHTLY_BEARISH
    else:
        state = S.NEUTRAL
    return f"{dist:+.1f}%", state, f"Price {dist:+.1f}% vs EMA{span} ({ema:,.0f})"


def ind_ichimoku(prices: pd.DataFrame):
    high, low, close = prices["high"], prices["low"], prices["close"]
    tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
    kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
    span_a = ((tenkan + kijun) / 2).shift(26)
    span_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
    price = float(close.iloc[-1])
    a, b = float(span_a.iloc[-1]), float(span_b.iloc[-1])
    top, bot = max(a, b), min(a, b)
    tk, kj = float(tenkan.iloc[-1]), float(kijun.iloc[-1])
    if price > top:
        state = S.BULLISH if tk > kj else S.SLIGHTLY_BULLISH
    elif price < bot:
        state = S.BEARISH if tk < kj else S.SLIGHTLY_BEARISH
    else:
        state = S.NEUTRAL
    pos = "above cloud" if price > top else "below cloud" if price < bot else "in cloud"
    return pos, state, f"Price {pos}; Tenkan {tk:,.0f} vs Kijun {kj:,.0f}"


def ind_bollinger(close: pd.Series, n: int = 20):
    mid = close.rolling(n).mean()
    sd = close.rolling(n).std(ddof=0)
    upper, lower = mid + 2 * sd, mid - 2 * sd
    pctb = float(((close.iloc[-1] - lower.iloc[-1]) /
                  (upper.iloc[-1] - lower.iloc[-1])))
    state = _band_state(pctb, [
        (1.0, S.SLIGHTLY_BULLISH),   # above upper band: stretched
        (0.8, S.BULLISH),
        (0.55, S.SLIGHTLY_BULLISH),
        (0.45, S.NEUTRAL),
        (0.2, S.SLIGHTLY_BEARISH),
        (0.0, S.BEARISH),
    ], default=S.SLIGHTLY_BEARISH)    # below lower band: stretched/oversold
    return f"%B {pctb:.2f}", state, f"Bollinger %B at {pctb:.2f}"


def ind_donchian(prices: pd.DataFrame, n: int = 20):
    high, low, close = prices["high"], prices["low"], prices["close"]
    upper = float(high.rolling(n).max().iloc[-1])
    lower = float(low.rolling(n).min().iloc[-1])
    price = float(close.iloc[-1])
    pos = (price - lower) / (upper - lower) if upper > lower else 0.5
    if price >= upper * 0.999:
        state = S.BULLISH
    elif pos > 0.66:
        state = S.SLIGHTLY_BULLISH
    elif pos < 0.34 and price <= lower * 1.001:
        state = S.BEARISH
    elif pos < 0.34:
        state = S.SLIGHTLY_BEARISH
    else:
        state = S.NEUTRAL
    return f"{pos*100:.0f}% of range", state, f"Donchian(20) position {pos*100:.0f}%"


def ind_fibonacci(close: pd.Series, lookback: int = 180):
    window = close.iloc[-lookback:] if len(close) > lookback else close
    hi, lo = float(window.max()), float(window.min())
    price = float(close.iloc[-1])
    ret = (price - lo) / (hi - lo) if hi > lo else 0.5
    state = _band_state(ret, [
        (0.78, S.BULLISH),
        (0.62, S.SLIGHTLY_BULLISH),
        (0.38, S.NEUTRAL),
        (0.22, S.SLIGHTLY_BEARISH),
    ], default=S.BEARISH)
    return f"{ret*100:.0f}% retr.", state, (
        f"Price at {ret*100:.0f}% of {lookback}d swing ({lo:,.0f}-{hi:,.0f})")


def ind_regression(close: pd.Series, lookback: int = 120):
    window = close.iloc[-lookback:] if len(close) > lookback else close
    x = np.arange(len(window))
    slope, intercept = np.polyfit(x, window.values, 1)
    fitted = slope * x + intercept
    resid_std = float(np.std(window.values - fitted, ddof=1))
    price = float(window.iloc[-1])
    slope_ann = slope / price * 252 * 100  # %/yr
    z = (price - fitted[-1]) / resid_std if resid_std else 0.0
    if slope_ann > 5:
        state = S.SLIGHTLY_BULLISH if z > 1.5 else S.BULLISH
    elif slope_ann > 1:
        state = S.SLIGHTLY_BULLISH
    elif slope_ann < -5:
        state = S.SLIGHTLY_BEARISH if z < -1.5 else S.BEARISH
    elif slope_ann < -1:
        state = S.SLIGHTLY_BEARISH
    else:
        state = S.NEUTRAL
    return f"{slope_ann:+.0f}%/yr", state, (
        f"Regression slope {slope_ann:+.1f}%/yr, channel z={z:+.1f}")


# --------------------------------------------------------------------------- #
# aggregation
# --------------------------------------------------------------------------- #
def _label_from_score(score_0_100: float) -> str:
    if score_0_100 >= 75:
        return "Strongly Bullish"
    if score_0_100 >= 60:
        return "Bullish"
    if score_0_100 > 40:
        return "Neutral"
    if score_0_100 > 25:
        return "Bearish"
    return "Strongly Bearish"


def bias3(score_0_100: float) -> str:
    """Coarse 3-state bias for the timeframe consensus summary."""
    if score_0_100 >= 60:
        return "Bullish"
    if score_0_100 <= 40:
        return "Bearish"
    return "Neutral"


def _resample(prices: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample daily OHLCV to a coarser timeframe (e.g. weekly, monthly)."""
    agg = {"open": "first", "high": "max", "low": "min", "close": "last",
           "volume": "sum"}
    cols = {k: v for k, v in agg.items() if k in prices.columns}
    return prices.resample(rule).agg(cols).dropna(subset=["close"])


def consensus_from_prices(prices: pd.DataFrame, timeframe: str = "Daily") -> ConsensusSummary:
    """Classify the 14 indicators on one OHLCV frame (any timeframe)."""
    close = prices["close"].dropna()
    specs = [
        ("RSI", "Momentum", ind_rsi(close)),
        ("MACD", "Momentum", ind_macd(close)),
        ("Stochastic", "Momentum", ind_stochastic(prices)),
        ("Stoch RSI", "Momentum", ind_stoch_rsi(close)),
        ("ADX/DMI", "Trend", ind_adx(prices)),
        ("EMA20", "Trend", ind_ema(close, 20)),
        ("EMA50", "Trend", ind_ema(close, 50)),
        ("EMA100", "Trend", ind_ema(close, 100)),
        ("EMA200", "Trend", ind_ema(close, 200)),
        ("Ichimoku", "Trend", ind_ichimoku(prices)),
        ("Bollinger", "Volatility", ind_bollinger(close)),
        ("Donchian", "Structure", ind_donchian(prices)),
        ("Fibonacci", "Structure", ind_fibonacci(close)),
        ("Regression Channel", "Trend", ind_regression(close)),
    ]

    readings: list[IndicatorReading] = []
    for name, category, (value, state, rationale) in specs:
        readings.append(IndicatorReading(
            name=name, category=category, value=value, state=state,
            score=INDICATOR_SCORE[state], rationale=rationale))

    n = len(readings)
    counts = {s.value: 0 for s in IndicatorState}
    for r in readings:
        counts[r.state.value] += 1

    bullish = counts[S.BULLISH.value] + counts[S.SLIGHTLY_BULLISH.value]
    bearish = counts[S.BEARISH.value] + counts[S.SLIGHTLY_BEARISH.value]
    neutral = counts[S.NEUTRAL.value]

    mean_score = float(np.mean([r.score for r in readings]))
    inst_score = round((mean_score + 2) / 4 * 100, 1)  # 0..100, 50 = neutral

    return ConsensusSummary(
        as_of=close.index[-1].to_pydatetime(),
        timeframe=timeframe,
        readings=readings,
        bullish_pct=round(bullish / n * 100, 1),
        neutral_pct=round(neutral / n * 100, 1),
        bearish_pct=round(bearish / n * 100, 1),
        institutional_score=inst_score,
        institutional_label=_label_from_score(inst_score),
        bias=bias3(inst_score),
        counts=counts,
    )


def compute(data: MarketData) -> ConsensusSummary:
    """Daily consensus (kept for the overview, narrative and report)."""
    return consensus_from_prices(data.prices, "Daily")


def _alignment_note(daily: ConsensusSummary, weekly: ConsensusSummary,
                    monthly: ConsensusSummary) -> str:
    biases = {"Daily": daily.bias, "Weekly": weekly.bias, "Monthly": monthly.bias}
    distinct = set(biases.values())
    if len(distinct) == 1:
        return f"All timeframes agree: {daily.bias.lower()}. Aligned outlook across horizons."
    if daily.bias != monthly.bias and "Neutral" not in (daily.bias, monthly.bias):
        return (f"Timeframes diverge: short-term (daily) is {daily.bias.lower()} while "
                f"long-term (monthly) is {monthly.bias.lower()} — typically a "
                f"counter-trend move within the larger trend. Expect the near-term "
                f"horizon to lean {daily.bias.lower()} and the multi-month horizon "
                f"to lean {monthly.bias.lower()}.")
    parts = ", ".join(f"{k.lower()} {v.lower()}" for k, v in biases.items())
    return f"Mixed across timeframes ({parts}); treat the signal as transitional."


def compute_mtf(data: MarketData) -> TimeframeConsensus:
    """Classify all 14 indicators on Daily, Weekly and Monthly timeframes."""
    daily = consensus_from_prices(data.prices, "Daily")
    weekly = consensus_from_prices(_resample(data.prices, "W-FRI"), "Weekly")
    monthly = consensus_from_prices(_resample(data.prices, "ME"), "Monthly")
    return TimeframeConsensus(
        as_of=daily.as_of, daily=daily, weekly=weekly, monthly=monthly,
        alignment=_alignment_note(daily, weekly, monthly))
