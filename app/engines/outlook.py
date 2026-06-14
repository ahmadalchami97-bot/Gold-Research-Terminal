"""Outlook engine — "What is the outlook?"

Produces the explicit 1-week / 1-month / 3-month dashboard. For each horizon it
reports Direction (5-state), Target Price, Expected Range, Confidence, Key
Driver and Invalidation.

Coherence by construction:
  * Direction blends technical momentum, medium-term trend and the distribution
    tilt (forward / coincident signals).
  * Expected Range and P(above spot) come straight from the objective Monte
    Carlo distribution.
  * Target is a conviction-weighted central estimate, scaled by the directional
    score and *bounded inside* the probabilistic range — so a bearish direction
    never shows a target above spot.
  * Key Driver is the dominant factor from the attribution engine.

Framing: model central estimates and probabilistic ranges with explicit
invalidation — research outputs, not trade recommendations.
"""
from __future__ import annotations

import math

import numpy as np

from app.data.types import MarketData
from app.engines.util import HORIZON_DAYS, HORIZON_LABELS, TRADING_DAYS, clamp
from app.schemas import (
    Confidence,
    ConsensusSummary,
    Direction,
    DistributionResult,
    DriverModel,
    HorizonOutlook,
    Invalidation,
    OutlookDashboard,
    RegimeState,
    RiskAssessment,
)

# per-horizon blend weights: (momentum, medium-term trend, distribution tilt)
WEIGHTS = {
    "1W": (0.50, 0.30, 0.20),
    "1M": (0.40, 0.35, 0.25),
    "3M": (0.30, 0.45, 0.25),
}
CONF_HORIZON_FACTOR = {"1W": 1.00, "1M": 0.95, "3M": 0.88}
TARGET_TILT = 0.5  # full conviction shifts the central estimate ~0.5 horizon-sigma


def _direction(score: float) -> Direction:
    if score > 0.5:
        return Direction.BULLISH
    if score > 0.15:
        return Direction.NEUTRAL_BULLISH
    if score >= -0.15:
        return Direction.NEUTRAL
    if score >= -0.5:
        return Direction.NEUTRAL_BEARISH
    return Direction.BEARISH


def _confidence(pct: float) -> Confidence:
    if pct >= 70:
        return Confidence.HIGH
    if pct >= 50:
        return Confidence.MEDIUM
    return Confidence.LOW


def _trend_signal(close, days: int, sigma_annual: float) -> float:
    """Trailing return over the horizon, normalised by horizon volatility."""
    if len(close) <= days:
        return 0.0
    past = float(close.iloc[-1 - days])
    if past <= 0:
        return 0.0
    sig = sigma_annual * math.sqrt(days / TRADING_DAYS)
    return clamp(math.log(float(close.iloc[-1]) / past) / (sig + 1e-9), -1, 1)


def compute(data: MarketData, distribution: DistributionResult,
            drivers: DriverModel, consensus: ConsensusSummary,
            risk: RiskAssessment, regime: RegimeState | None = None) -> OutlookDashboard:
    spot = distribution.spot
    close = data.close
    by_h = {h.horizon: h for h in distribution.horizons}

    momentum = clamp((consensus.institutional_score - 50) / 50, -1, 1)

    # confidence components shared across horizons
    r2_comp = clamp(drivers.r_squared / 0.5, 0, 1)
    agreement = clamp(abs(consensus.bullish_pct - consensus.bearish_pct) / 60.0, 0, 1)
    vol_calm = 1 - (regime.vol_percentile / 100.0) if regime is not None else 0.5
    conf_base = 0.45 * r2_comp + 0.30 * agreement + 0.25 * vol_calm

    horizons: list[HorizonOutlook] = []
    for hkey, days in HORIZON_DAYS.items():
        hr = by_h[hkey]
        sigma_h = hr.sigma_annual * math.sqrt(days / TRADING_DAYS)
        dist_tilt = clamp(math.log(hr.median / spot) / (sigma_h + 1e-9) * 1.5, -1, 1)
        trend = _trend_signal(close, days * 3, hr.sigma_annual)  # medium-term trend

        w_mom, w_trend, w_dist = WEIGHTS[hkey]
        score = clamp(w_mom * momentum + w_trend * trend + w_dist * dist_tilt, -1, 1)
        direction = _direction(score)

        # conviction-weighted central estimate, bounded by the probabilistic band
        target = spot * math.exp(score * TARGET_TILT * sigma_h)
        target = float(np.clip(target, hr.expected_low, hr.expected_high))

        conf_pct = clamp((35 + conf_base * 55) * CONF_HORIZON_FACTOR[hkey], 25, 92)
        inval = risk.bull_invalidation if score >= 0 else risk.bear_invalidation

        rationale = (
            f"{direction.value} over {HORIZON_LABELS[hkey].lower()}: central "
            f"estimate {target:,.0f} within a {hr.expected_low:,.0f}-"
            f"{hr.expected_high:,.0f} range, led by {drivers.dominant_driver.lower()}. "
            f"{hr.prob_above_spot*100:.0f}% probability of finishing above spot.")

        horizons.append(HorizonOutlook(
            horizon=HORIZON_LABELS[hkey], days=days, direction=direction,
            direction_score=round(score, 3), target_price=round(target, 2),
            expected_low=round(hr.expected_low, 2), expected_high=round(hr.expected_high, 2),
            confidence=_confidence(conf_pct), confidence_pct=round(conf_pct, 0),
            key_driver=drivers.dominant_driver,
            invalidation=Invalidation(level=inval.level, condition=inval.condition),
            rationale=rationale))

    return OutlookDashboard(as_of=distribution.as_of, spot=spot, horizons=horizons)
