"""Generate the bundled sample snapshot in ``data_samples/``.

This builds a *synthetic but internally coherent* market world: the macro
drivers are simulated first, then gold returns are constructed as a documented
linear response to those drivers plus idiosyncratic noise. As a result the
attribution, regime and correlation engines recover realistic structure on the
sample data, and every page renders offline.

The output is clearly labelled synthetic/sample throughout the terminal. Live
providers replace it automatically on networks with data access.

Run:  python scripts/seed_samples.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20260614
START = "2018-01-01"
END = "2026-06-12"
TARGET_LAST_GOLD = 2965.0  # synthetic level anchor for a plausible 2026 print
OUT = Path(__file__).resolve().parents[1] / "data_samples"


def ar1_around(index, anchors: dict[str, float], phi: float, sigma: float,
               rng: np.random.Generator, log: bool = False) -> pd.Series:
    """AR(1) process reverting to a time-varying mean defined by anchors."""
    anchor_s = pd.Series(anchors).copy()
    anchor_s.index = pd.to_datetime(anchor_s.index)
    mean = (anchor_s.reindex(anchor_s.index.union(index)).sort_index()
            .interpolate("time").reindex(index).bfill().ffill())
    if log:
        mean = np.log(mean)
    out = np.empty(len(index))
    out[0] = mean.iloc[0]
    z = rng.standard_normal(len(index))
    for t in range(1, len(index)):
        out[t] = mean.iloc[t] + phi * (out[t - 1] - mean.iloc[t - 1]) + sigma * z[t]
    series = pd.Series(out, index=index)
    return np.exp(series) if log else series


def main() -> None:
    rng = np.random.default_rng(SEED)
    idx = pd.bdate_range(START, END)
    n = len(idx)

    # --- macro drivers -----------------------------------------------------
    real_yield = ar1_around(idx, {
        "2018-01-01": 0.55, "2018-12-01": 0.95, "2019-09-01": 0.15,
        "2020-03-15": 0.50, "2020-08-01": -1.05, "2021-12-01": -1.00,
        "2022-06-01": 0.60, "2023-10-01": 2.35, "2024-06-01": 2.00,
        "2024-12-01": 1.90, "2025-09-01": 1.40, "2026-06-12": 1.15,
    }, phi=0.94, sigma=0.040, rng=rng)

    breakeven = ar1_around(idx, {
        "2018-01-01": 2.05, "2020-03-15": 0.90, "2021-11-01": 2.70,
        "2022-04-01": 3.00, "2023-06-01": 2.20, "2024-06-01": 2.30,
        "2026-06-12": 2.30,
    }, phi=0.95, sigma=0.030, rng=rng)

    nominal = (real_yield + breakeven + rng.normal(0, 0.03, n)).clip(0.1, None)

    dxy = ar1_around(idx, {
        "2018-02-01": 90.0, "2018-12-01": 96.0, "2020-03-20": 103.0,
        "2021-01-01": 90.0, "2022-09-28": 114.0, "2023-07-01": 101.0,
        "2024-01-01": 103.0, "2024-12-01": 107.0, "2025-06-01": 99.0,
        "2026-06-12": 98.0,
    }, phi=0.97, sigma=0.38, rng=rng)

    vix = ar1_around(idx, {
        "2018-01-01": 13.5, "2018-12-24": 30.0, "2019-08-01": 17.0,
        "2020-03-18": 58.0, "2020-12-01": 22.0, "2022-06-15": 30.0,
        "2023-03-15": 24.0, "2024-08-05": 28.0, "2025-04-01": 22.0,
        "2026-06-12": 15.5,
    }, phi=0.92, sigma=0.060, rng=rng, log=True).clip(9.0, 75.0)

    spx_ret = rng.normal(0.09 / 252, 0.0105, n)
    spx = pd.Series(3200 * np.cumprod(1 + spx_ret), index=idx)

    gsr = ar1_around(idx, {
        "2018-01-01": 78.0, "2020-03-18": 122.0, "2021-01-01": 70.0,
        "2022-09-01": 88.0, "2024-01-01": 86.0, "2026-06-12": 82.0,
    }, phi=0.97, sigma=0.5, rng=rng)

    # --- gold returns as a documented response to drivers ------------------
    d_ry = real_yield.diff().fillna(0.0)               # percentage points
    d_be = breakeven.diff().fillna(0.0)
    r_dxy = np.log(dxy).diff().fillna(0.0)
    r_vix = np.log(vix).diff().fillna(0.0)

    c_ry, c_dxy, c_be, c_vix = -0.10, -0.55, 0.045, 0.030
    mu_daily = 0.075 / 252
    idio = rng.normal(0, 0.0062, n)

    r_gold = (mu_daily + c_ry * d_ry + c_dxy * r_dxy + c_be * d_be
              + c_vix * r_vix + idio)
    r_gold.iloc[0] = 0.0
    cum = np.cumprod(1 + r_gold.values)
    s0 = TARGET_LAST_GOLD / cum[-1]
    close = pd.Series(s0 * cum, index=idx)

    silver = (close / gsr) * (1 + rng.normal(0, 0.004, n))

    # --- synthesise OHLCV around the close ---------------------------------
    prev_close = close.shift(1).fillna(close.iloc[0])
    gap = rng.normal(0, 0.0015, n)
    open_ = prev_close * (1 + gap)
    span = close.values * (0.0035 + 0.55 * np.abs(r_gold.values))
    hi_base = np.maximum(open_.values, close.values)
    lo_base = np.minimum(open_.values, close.values)
    high = hi_base + span * rng.uniform(0.2, 1.0, n)
    low = lo_base - span * rng.uniform(0.2, 1.0, n)
    volume = (180_000 + 600_000 * np.abs(r_gold.values) / 0.01
              + rng.normal(0, 25_000, n)).clip(50_000, None)

    prices = pd.DataFrame({
        "open": open_.values, "high": high, "low": low,
        "close": close.values, "volume": volume.round(0),
    }, index=idx)

    macro = pd.DataFrame({
        "dxy": dxy, "real_yield_10y": real_yield, "nominal_10y": nominal,
        "breakeven_10y": breakeven, "vix": vix, "spx": spx, "silver": silver,
    }, index=idx)

    # --- weekly CFTC-style positioning -------------------------------------
    tuesdays = pd.bdate_range(START, END, weekmask="Tue", freq="C")
    mom = close.pct_change(60).reindex(tuesdays).fillna(0.0)
    mm_net = (110_000 + 380_000 * mom + rng.normal(0, 18_000, len(tuesdays))).clip(-150_000, 350_000)
    oi = (480_000 + rng.normal(0, 30_000, len(tuesdays))).clip(300_000, None)
    mm_long = (mm_net.clip(0, None) + 140_000 + rng.normal(0, 12_000, len(tuesdays))).clip(0, None)
    mm_short = (mm_long - mm_net).clip(0, None)
    positioning = pd.DataFrame({
        "mm_long": mm_long.round(0), "mm_short": mm_short.round(0),
        "mm_net": mm_net.round(0), "open_interest": oi.round(0),
    }, index=tuesdays)

    # --- representative sample headlines -----------------------------------
    asof = idx[-1]
    sample_news = [
        ("Gold holds near record as soft payrolls revive Fed rate-cut bets", -0, "Reuters", 1),
        ("Dollar slips to two-month low, lifting gold and silver", None, "Bloomberg", 2),
        ("10-year real yields ease as CPI undershoots expectations", None, "FXStreet", 1),
        ("Central banks added to gold reserves again last month, WGC says", None, "Kitco", 3),
        ("Hawkish Fed minutes lift the dollar; gold pares gains", None, "MarketWatch", 4),
        ("Treasury yields climb after strong jobless claims data", None, "CNBC", 5),
        ("Safe-haven bid returns on geopolitical tensions", None, "Reuters", 2),
        ("ETF gold holdings rise for a third straight week", None, "Mining.com", 3),
        ("Stronger dollar caps bullion as traders trim cut odds", None, "Bloomberg", 6),
        ("Gold consolidates as markets await next inflation print", None, "FXStreet", 1),
        ("Rising real rates pressure non-yielding assets", None, "WSJ", 7),
        ("Silver outperforms gold; ratio narrows on industrial demand", None, "Kitco", 4),
    ]
    news = []
    for headline, _, source, days_ago in sample_news:
        ts = (asof - pd.Timedelta(days=days_ago, hours=int(rng.integers(0, 12))))
        news.append({
            "headline": headline, "source": source,
            "url": "https://example.com/sample",
            "published_at": ts.isoformat(),
            "summary": "Sample headline included with the offline snapshot.",
        })

    # --- write -------------------------------------------------------------
    OUT.mkdir(parents=True, exist_ok=True)
    prices.to_parquet(OUT / "prices.parquet")
    macro.to_parquet(OUT / "macro.parquet")
    positioning.to_parquet(OUT / "positioning.parquet")
    (OUT / "news.json").write_text(json.dumps(news, indent=2))
    (OUT / "meta.json").write_text(json.dumps({
        "synthetic": True, "seed": SEED, "start": START, "end": END,
        "rows": int(n), "last_gold": round(float(close.iloc[-1]), 2),
        "note": "Synthetic sample snapshot. Drivers simulated; gold built as a "
                "documented linear response to drivers plus noise.",
    }, indent=2))

    print(f"Wrote snapshot to {OUT}  ({n} rows, last gold ${close.iloc[-1]:,.2f})")
    corr = pd.concat([np.log(close).diff(), real_yield.diff()], axis=1).corr().iloc[0, 1]
    print(f"  sanity: corr(gold ret, d real_yield) = {corr:+.2f}  "
          f"ann vol = {r_gold.std()*np.sqrt(252)*100:.1f}%")


if __name__ == "__main__":
    main()
