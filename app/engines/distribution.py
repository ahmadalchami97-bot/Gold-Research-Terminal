"""Distribution engine — "Probability distribution / expected range".

A GARCH(1,1) forward volatility term structure feeds a blended Monte Carlo
simulation (Gaussian GBM + Student-t fat tails + historical bootstrap). Outputs
horizon ranges (central and tail bands), probability of finishing above spot,
and first-passage "touch" probabilities for key round levels. The seed is fixed
so every run is reproducible.
"""
from __future__ import annotations

import math
import warnings

import numpy as np
import pandas as pd

from app.data.types import MarketData
from app.engines.util import TRADING_DAYS, HORIZON_DAYS, clamp, log_returns
from app.schemas import DistributionResult, HorizonRange

N_PER_METHOD = 6000           # paths per generator (x3 generators)
MAX_H = max(HORIZON_DAYS.values())


def _garch_vol_path(returns: pd.Series, horizon: int) -> tuple[np.ndarray, bool]:
    """Daily (decimal) volatility path from GARCH(1,1); realized fallback."""
    realized = float(returns.iloc[-60:].std(ddof=1))
    try:
        from arch import arch_model
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            am = arch_model(returns.values * 100, mean="Constant",
                            vol="GARCH", p=1, q=1, dist="normal")
            res = am.fit(disp="off", show_warning=False)
            fc = res.forecast(horizon=horizon, reindex=False)
        var = np.asarray(fc.variance.values[-1], dtype=float)
        vol = np.sqrt(var) / 100.0
        if not np.all(np.isfinite(vol)) or np.any(vol <= 0):
            raise ValueError("non-finite GARCH variance")
        return vol, True
    except Exception:
        return np.full(horizon, realized), False


def compute(data: MarketData, seed: int = 20260614,
            n_per_method: int = N_PER_METHOD) -> DistributionResult:
    close = data.close
    spot = float(close.iloc[-1])
    ret = log_returns(close)
    as_of = close.index[-1].to_pydatetime()

    sigma_daily = float(ret.iloc[-60:].std(ddof=1))
    sigma_realized = sigma_daily * math.sqrt(TRADING_DAYS)

    # Damped historical drift keeps the median only mildly tilted; ranges are
    # volatility-dominated (research framing, not a directional bet).
    raw_drift = float(ret.iloc[-TRADING_DAYS:].mean())
    mu = clamp(0.25 * raw_drift, -0.0004, 0.0004)

    vol_path, garch_ok = _garch_vol_path(ret, MAX_H)
    sigma_garch = float(vol_path[0] * math.sqrt(TRADING_DAYS))

    rng = np.random.default_rng(seed)
    # GBM (Gaussian) and Student-t blocks use the GARCH vol term structure.
    zg = rng.standard_normal((n_per_method, MAX_H))
    df = 5
    zt = rng.standard_t(df, size=(n_per_method, MAX_H)) / math.sqrt(df / (df - 2))
    steps_g = mu + vol_path * zg
    steps_t = mu + vol_path * zt
    # Historical bootstrap embeds real higher-moments; recenter to drift mu.
    hist = ret.iloc[-500:].values if len(ret) > 500 else ret.values
    boot = rng.choice(hist, size=(n_per_method, MAX_H), replace=True)
    boot = boot - hist.mean() + mu
    steps = np.vstack([steps_g, steps_t, boot])

    logpaths = np.cumsum(steps, axis=1)
    price_paths = spot * np.exp(logpaths)
    run_max = np.maximum.accumulate(price_paths, axis=1)
    run_min = np.minimum.accumulate(price_paths, axis=1)

    horizons: list[HorizonRange] = []
    terminal_samples: dict[str, list[float]] = {}
    for hkey, days in HORIZON_DAYS.items():
        col = days - 1
        terminal = price_paths[:, col]
        q = np.percentile(terminal, [5, 25, 50, 75, 95])
        sigma_h_annual = float(np.std(np.log(terminal / spot)) * math.sqrt(TRADING_DAYS / days))

        ru = math.ceil(spot / 100) * 100
        rd = math.floor(spot / 100) * 100
        if abs(ru - spot) < spot * 0.004:
            ru += 100
        if abs(rd - spot) < spot * 0.004:
            rd -= 100
        touch = {
            f"≥ {ru:,.0f}": float(np.mean(run_max[:, col] >= ru)),
            f"≤ {rd:,.0f}": float(np.mean(run_min[:, col] <= rd)),
        }

        horizons.append(HorizonRange(
            horizon=hkey, days=days, spot=spot, median=float(q[2]),
            expected_low=float(q[1]), expected_high=float(q[3]),
            wide_low=float(q[0]), wide_high=float(q[4]),
            sigma_annual=sigma_h_annual,
            prob_above_spot=float(np.mean(terminal > spot)),
            touch_prob={k: round(v, 3) for k, v in touch.items()},
        ))
        terminal_samples[hkey] = terminal[rng.choice(len(terminal),
                                                     size=min(2500, len(terminal)),
                                                     replace=False)].round(2).tolist()

    cone = {
        "days": [float(d) for d in range(1, MAX_H + 1)],
        "annualized_vol": [float(v * math.sqrt(TRADING_DAYS) * 100) for v in vol_path],
        "realized_ref": [float(sigma_realized * 100)] * MAX_H,
    }

    return DistributionResult(
        as_of=as_of, spot=spot,
        method="Monte Carlo blend: GBM + Student-t(5) + historical bootstrap, "
               f"GARCH(1,1) vol term structure{'' if garch_ok else ' (realized fallback)'}",
        seed=seed, n_paths=int(price_paths.shape[0]),
        sigma_realized=sigma_realized, sigma_garch=sigma_garch,
        garch_vol_cone=cone, horizons=horizons, terminal_samples=terminal_samples,
    )
