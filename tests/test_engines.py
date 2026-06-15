"""Engine invariants and golden-master-style checks on the sample snapshot."""
import math

from app.engines import (
    distribution,
    drivers,
    indicators,
    levels,
    market_state,
    news,
    outlook,
    regime,
    risk,
)
from app.schemas import Direction, IndicatorState


# --- market state ----------------------------------------------------------
def test_market_state(data):
    ms = market_state.compute(data)
    assert ms.price > 0
    assert {r.horizon for r in ms.returns} >= {"1D", "1W", "1M", "1Y", "YTD"}
    assert [m.window for m in ms.moving_averages] == [20, 50, 100, 200]
    assert 0 < ms.annualized_vol < 100          # stored as percent
    assert ms.ath >= ms.price
    assert -100 <= ms.drawdown_from_ath_pct <= 0


# --- indicator consensus ---------------------------------------------------
def test_consensus_matrix(data):
    c = indicators.compute(data)
    assert len(c.readings) == 14
    assert all(isinstance(r.state, IndicatorState) for r in c.readings)
    assert abs(c.bullish_pct + c.neutral_pct + c.bearish_pct - 100) < 0.3
    assert 0 <= c.institutional_score <= 100
    assert sum(c.counts.values()) == 14


# --- multi-timeframe consensus ---------------------------------------------
def test_multi_timeframe_consensus(data):
    mtf = indicators.compute_mtf(data)
    for cs in (mtf.daily, mtf.weekly, mtf.monthly):
        assert len(cs.readings) == 14
        assert 0 <= cs.institutional_score <= 100
        assert cs.bias in {"Bearish", "Neutral", "Bullish"}
    assert mtf.daily.timeframe == "Daily"
    assert mtf.weekly.timeframe == "Weekly"
    assert mtf.monthly.timeframe == "Monthly"
    assert mtf.alignment


# --- drivers ---------------------------------------------------------------
def test_drivers(data):
    d = drivers.compute(data)
    assert 0 <= d.r_squared <= 1
    by = {b.driver: b for b in d.betas}
    # synthetic world: gold falls when real yields rise / dollar strengthens
    assert by["real_yield_10y"].beta < 0
    assert by["dxy"].beta < 0
    assert math.isclose(d.actual_move_bps, d.explained_move_bps + d.residual_bps, abs_tol=1.0)


# --- regime ----------------------------------------------------------------
def test_regime(data):
    r = regime.compute(data)
    assert 0 <= r.vol_percentile <= 100
    assert r.vol_regime in {"Low", "Normal", "Elevated", "High"}
    assert r.what_changed


# --- levels ----------------------------------------------------------------
def test_levels(data):
    lm = levels.compute(data)
    assert lm.all_levels
    if lm.nearest_support:
        assert lm.nearest_support.price < lm.price
        assert lm.nearest_support.distance_pct < 0
    if lm.nearest_resistance:
        assert lm.nearest_resistance.price >= lm.price


# --- distribution ----------------------------------------------------------
def test_distribution_determinism(data):
    a = distribution.compute(data, seed=123, n_per_method=2000)
    b = distribution.compute(data, seed=123, n_per_method=2000)
    assert [h.median for h in a.horizons] == [h.median for h in b.horizons]


def test_distribution_ranges(data):
    dist = distribution.compute(data, seed=20260614, n_per_method=3000)
    assert len(dist.horizons) == 3
    prev_width = -1
    for h in dist.horizons:
        assert h.wide_low < h.expected_low < h.median < h.expected_high < h.wide_high
        assert 0 <= h.prob_above_spot <= 1
        width = h.wide_high - h.wide_low
        assert width > prev_width            # uncertainty grows with horizon
        prev_width = width


# --- outlook (coherence) ---------------------------------------------------
def test_outlook_coherence(data):
    dist = distribution.compute(data, seed=20260614, n_per_method=3000)
    drv = drivers.compute(data)
    cons = indicators.compute_mtf(data)
    reg = regime.compute(data)
    rk = risk.compute(data, regime=reg)
    o = outlook.compute(data, dist, drv, cons, rk, reg)
    assert len(o.horizons) == 3
    for h in o.horizons:
        assert isinstance(h.direction, Direction)
        # target and direction must agree in sign relative to spot
        assert (h.target_price >= o.spot) == (h.direction_score >= 0)
        assert h.expected_low <= h.target_price <= h.expected_high
        assert 25 <= h.confidence_pct <= 92


# --- risk ------------------------------------------------------------------
def test_risk(data):
    reg = regime.compute(data)
    rk = risk.compute(data, regime=reg)
    assert rk.var_95_1d_pct > 0
    assert rk.cvar_95_1d_pct >= rk.var_95_1d_pct  # CVaR is at least VaR
    assert rk.max_drawdown_1y_pct <= 0
    assert rk.bull_invalidation.level > 0 and rk.bear_invalidation.level > 0


# --- news ------------------------------------------------------------------
def test_news(data):
    nd = news.compute(data)
    assert -100 <= nd.macro_score <= 100
    assert nd.bullish_count + nd.neutral_count + nd.bearish_count == len(nd.items)
    assert nd.generated_by == "lexicon"
