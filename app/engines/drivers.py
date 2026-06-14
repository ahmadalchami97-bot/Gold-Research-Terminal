"""Driver engine — "Why is it doing it?"

Multi-factor regression of daily gold log-returns on the changes in its primary
macro drivers (real yields, dollar, breakevens, risk sentiment, equities),
robust (HC1) t-stats, an attribution decomposition of the trailing move into
per-driver contributions, and rolling correlations.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from app.data.types import MarketData
from app.engines.util import log_returns
from app.schemas import DriverBeta, DriverModel

ESTIMATION_WINDOW = 120
ATTRIBUTION_WINDOW = 21
ROLLING_CORR_WINDOW = 90

# canonical driver -> (label, change-type, expected sign)
DRIVER_SPEC = {
    "real_yield_10y": ("10y real yield (TIPS)", "diff", "negative"),
    "dxy": ("US dollar (DXY)", "logret", "negative"),
    "breakeven_10y": ("10y breakeven inflation", "diff", "positive"),
    "vix": ("Risk sentiment (VIX)", "logret", "positive"),
    "spx": ("S&P 500", "logret", "negative"),
}


def _change(series: pd.Series, how: str) -> pd.Series:
    if how == "logret":
        return np.log(series.astype(float)).diff()
    return series.astype(float).diff()


def compute(data: MarketData) -> DriverModel:
    close = data.close
    gold_ret = log_returns(close).rename("gold_ret")

    frame = pd.DataFrame({"gold_ret": gold_ret})
    available: list[str] = []
    for key, (_, how, _) in DRIVER_SPEC.items():
        if data.has_macro(key):
            chg = _change(data.macro[key].reindex(close.index).ffill(), how)
            frame[key] = chg
            available.append(key)
    frame = frame.dropna()

    as_of = close.index[-1].to_pydatetime()
    if len(available) < 2 or len(frame) < ESTIMATION_WINDOW // 2:
        return DriverModel(as_of=as_of, window_days=ATTRIBUTION_WINDOW, r_squared=0.0,
                           betas=[], explained_move_bps=0.0,
                           actual_move_bps=float(gold_ret.iloc[-ATTRIBUTION_WINDOW:].sum() * 1e4),
                           residual_bps=0.0, dominant_driver="n/a",
                           rolling_corr={}, rolling_corr_dates=[])

    est = frame.iloc[-ESTIMATION_WINDOW:]
    X = sm.add_constant(est[available])
    res = sm.OLS(est["gold_ret"], X).fit(cov_type="HC1")

    attrib = frame.iloc[-ATTRIBUTION_WINDOW:]
    betas: list[DriverBeta] = []
    explained = 0.0
    for key in available:
        label, _, exp_sign = DRIVER_SPEC[key]
        beta = float(res.params[key])
        tval = float(res.tvalues[key])
        contrib = beta * float(attrib[key].sum()) * 1e4  # bps
        explained += contrib
        corr90 = float(frame["gold_ret"].iloc[-ROLLING_CORR_WINDOW:]
                       .corr(frame[key].iloc[-ROLLING_CORR_WINDOW:]))
        betas.append(DriverBeta(driver=key, label=label, beta=beta, t_stat=tval,
                                corr_90d=corr90, corr_sign_expected=exp_sign,
                                contribution_bps=round(contrib, 1)))

    actual = float(frame["gold_ret"].iloc[-ATTRIBUTION_WINDOW:].sum() * 1e4)
    dominant = max(betas, key=lambda b: abs(b.contribution_bps)).label if betas else "n/a"

    # rolling correlations (trailing year) for the heatmap/lines
    tail = frame.iloc[-252:] if len(frame) > 252 else frame
    roll_dates = [d.strftime("%Y-%m-%d") for d in tail.index]
    rolling = {}
    for key in available:
        rc = frame["gold_ret"].rolling(ROLLING_CORR_WINDOW).corr(frame[key])
        rolling[DRIVER_SPEC[key][0]] = [None if pd.isna(v) else round(float(v), 3)
                                        for v in rc.reindex(tail.index)]

    betas.sort(key=lambda b: abs(b.contribution_bps), reverse=True)
    return DriverModel(
        as_of=as_of, window_days=ATTRIBUTION_WINDOW,
        r_squared=float(res.rsquared), betas=betas,
        explained_move_bps=round(explained, 1), actual_move_bps=round(actual, 1),
        residual_bps=round(actual - explained, 1), dominant_driver=dominant,
        rolling_corr=rolling, rolling_corr_dates=roll_dates,
    )
