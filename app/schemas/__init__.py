"""Typed result contracts shared between engines, narrative, reporting and UI.

These are plain dataclasses (no pydantic dependency) so the engines stay pure
and trivially unit-testable. Enums encode the exact discrete vocabularies
specified for the terminal (5-state direction, 5-state indicator consensus,
3-state news classification).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# --------------------------------------------------------------------------- #
# Shared vocabularies
# --------------------------------------------------------------------------- #
class Direction(str, Enum):
    BULLISH = "Bullish"
    NEUTRAL_BULLISH = "Neutral-Bullish"
    NEUTRAL = "Neutral"
    NEUTRAL_BEARISH = "Neutral-Bearish"
    BEARISH = "Bearish"


class IndicatorState(str, Enum):
    BEARISH = "Bearish"
    SLIGHTLY_BEARISH = "Slightly Bearish"
    NEUTRAL = "Neutral"
    SLIGHTLY_BULLISH = "Slightly Bullish"
    BULLISH = "Bullish"


class Classification(str, Enum):
    BULLISH = "Bullish"
    NEUTRAL = "Neutral"
    BEARISH = "Bearish"


class Confidence(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


# Numeric score attached to each discrete state for aggregation.
INDICATOR_SCORE = {
    IndicatorState.BEARISH: -2,
    IndicatorState.SLIGHTLY_BEARISH: -1,
    IndicatorState.NEUTRAL: 0,
    IndicatorState.SLIGHTLY_BULLISH: 1,
    IndicatorState.BULLISH: 2,
}


# --------------------------------------------------------------------------- #
# Data provenance
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class SeriesStatus:
    key: str
    source: str           # e.g. "Yahoo Finance", "FRED", "synthetic-sample"
    mode: str             # "live" | "cached"
    as_of: datetime | None
    ok: bool
    detail: str = ""


@dataclass
class DataProvenance:
    mode: str                       # overall: "live" | "cached" | "mixed"
    generated_at: datetime
    series: list[SeriesStatus] = field(default_factory=list)

    @property
    def is_live(self) -> bool:
        return self.mode == "live"


# --------------------------------------------------------------------------- #
# Market state  ("What is gold doing?")
# --------------------------------------------------------------------------- #
@dataclass
class ReturnStat:
    horizon: str          # "1D", "1W", "1M", "3M", "YTD", "1Y", "5Y"
    pct: float | None


@dataclass
class MovingAverageStat:
    window: int
    value: float
    pct_distance: float   # price vs MA, as %
    above: bool


@dataclass
class MarketState:
    as_of: datetime
    price: float
    prior_close: float
    change_pct_1d: float
    returns: list[ReturnStat]
    moving_averages: list[MovingAverageStat]
    realized_vol: dict[str, float]      # e.g. {"10d": .., "20d": .., "30d": ..}
    annualized_vol: float
    atr_pct: float
    high_52w: float
    low_52w: float
    ath: float
    drawdown_from_ath_pct: float
    pct_of_52w_range: float
    trend_state: str                    # e.g. "Uptrend (price > all MAs)"
    gold_silver_ratio: float | None


# --------------------------------------------------------------------------- #
# Drivers  ("Why is it doing it?")
# --------------------------------------------------------------------------- #
@dataclass
class DriverBeta:
    driver: str
    label: str
    beta: float                 # sensitivity of gold log-return to driver change
    t_stat: float
    corr_90d: float
    corr_sign_expected: str     # "negative" | "positive"
    contribution_bps: float     # attributed contribution to the recent window move


@dataclass
class DriverModel:
    as_of: datetime
    window_days: int
    r_squared: float
    betas: list[DriverBeta]
    explained_move_bps: float       # sum of attributed contributions
    actual_move_bps: float          # actual gold move over the window
    residual_bps: float
    dominant_driver: str
    rolling_corr: dict[str, list[float]]   # driver -> rolling correlation series
    rolling_corr_dates: list[str]


# --------------------------------------------------------------------------- #
# Regime  ("What changed?")
# --------------------------------------------------------------------------- #
@dataclass
class RegimeChange:
    date: str
    metric: str
    description: str


@dataclass
class RegimeState:
    as_of: datetime
    vol_regime: str             # "Low" | "Normal" | "Elevated" | "High"
    vol_percentile: float
    trend_regime: str
    correlation_regime: str     # e.g. "Real-yield coupled (typical)"
    real_yield_corr_60d: float
    real_yield_corr_long: float
    decoupled: bool
    change_points: list[RegimeChange]
    what_changed: list[str]     # bullet summary of notable recent shifts


# --------------------------------------------------------------------------- #
# Levels  ("What levels matter?")
# --------------------------------------------------------------------------- #
@dataclass
class Level:
    price: float
    kind: str                   # "support" | "resistance" | "pivot" | "ma" | "fib" | "band" | "round"
    label: str
    source: str
    distance_pct: float         # signed distance from spot, %


@dataclass
class LevelMap:
    as_of: datetime
    price: float
    supports: list[Level]
    resistances: list[Level]
    nearest_support: Level | None
    nearest_resistance: Level | None
    all_levels: list[Level]


# --------------------------------------------------------------------------- #
# Distribution  ("Probability distribution / expected range")
# --------------------------------------------------------------------------- #
@dataclass
class HorizonRange:
    horizon: str                # "1W", "1M", "3M"
    days: int
    spot: float
    median: float
    expected_low: float         # central band low (e.g. 25th pct)
    expected_high: float        # central band high (e.g. 75th pct)
    wide_low: float             # tail band low (e.g. 5th pct)
    wide_high: float            # tail band high (e.g. 95th pct)
    sigma_annual: float
    prob_above_spot: float
    touch_prob: dict[str, float]   # label -> probability of touching a level


@dataclass
class DistributionResult:
    as_of: datetime
    spot: float
    method: str                 # "Monte Carlo (GBM + Student-t + bootstrap blend)"
    seed: int
    n_paths: int
    sigma_realized: float
    sigma_garch: float
    garch_vol_cone: dict[str, list[float]]   # horizon-indexed forward vol path
    horizons: list[HorizonRange]
    terminal_samples: dict[str, list[float]]  # horizon -> sampled terminal prices (downsampled)


# --------------------------------------------------------------------------- #
# Outlook  ("What is the outlook?")  -- explicit 3-horizon dashboard
# --------------------------------------------------------------------------- #
@dataclass
class Invalidation:
    level: float
    condition: str              # human-readable trigger


@dataclass
class HorizonOutlook:
    horizon: str                # "1 Week" | "1 Month" | "3 Months"
    days: int
    direction: Direction
    direction_score: float      # [-1, +1]
    target_price: float
    expected_low: float
    expected_high: float
    confidence: Confidence
    confidence_pct: float
    key_driver: str
    invalidation: Invalidation
    rationale: str


@dataclass
class OutlookDashboard:
    as_of: datetime
    spot: float
    horizons: list[HorizonOutlook]


# --------------------------------------------------------------------------- #
# Indicator consensus
# --------------------------------------------------------------------------- #
@dataclass
class IndicatorReading:
    name: str
    category: str               # "Momentum" | "Trend" | "Volatility" | "Structure"
    value: str                  # formatted current value
    state: IndicatorState
    score: int                  # -2..+2
    rationale: str


@dataclass
class ConsensusSummary:
    as_of: datetime
    timeframe: str              # "Daily" | "Weekly" | "Monthly"
    readings: list[IndicatorReading]
    bullish_pct: float
    neutral_pct: float
    bearish_pct: float
    institutional_score: float  # 0..100 (50 = neutral)
    institutional_label: str    # Strongly Bearish .. Strongly Bullish
    bias: str                   # 3-state: Bearish | Neutral | Bullish
    counts: dict[str, int]      # state -> count


@dataclass
class TimeframeConsensus:
    """The 14 indicators classified across Daily / Weekly / Monthly timeframes."""
    as_of: datetime
    daily: ConsensusSummary
    weekly: ConsensusSummary
    monthly: ConsensusSummary
    alignment: str              # human note on cross-timeframe alignment / divergence

    @property
    def frames(self) -> list[ConsensusSummary]:
        return [self.daily, self.weekly, self.monthly]


# --------------------------------------------------------------------------- #
# Risk  ("What could invalidate the thesis?")
# --------------------------------------------------------------------------- #
@dataclass
class RiskTrigger:
    name: str
    condition: str
    severity: str               # "High" | "Medium" | "Low"
    rationale: str


@dataclass
class RiskAssessment:
    as_of: datetime
    var_95_1d_pct: float
    var_99_1d_pct: float
    cvar_95_1d_pct: float
    var_95_1m_pct: float
    max_drawdown_1y_pct: float
    bull_invalidation: Invalidation
    bear_invalidation: Invalidation
    triggers: list[RiskTrigger]
    correlation_breakdown: bool
    notes: list[str]


# --------------------------------------------------------------------------- #
# News
# --------------------------------------------------------------------------- #
@dataclass
class NewsItem:
    headline: str
    source: str
    url: str
    published_at: datetime | None
    classification: Classification
    impact_score: int           # -2..+2
    what_happened: str
    what_it_means: str


@dataclass
class NewsDigest:
    as_of: datetime
    items: list[NewsItem]
    macro_score: float          # -100..+100
    overall_classification: Classification
    bullish_count: int
    neutral_count: int
    bearish_count: int
    generated_by: str           # "claude" | "lexicon"
    summary: str


# --------------------------------------------------------------------------- #
# Narrative + composite
# --------------------------------------------------------------------------- #
@dataclass
class NarrativeBlock:
    title: str
    body: str
    source: str                 # "deterministic" | "claude"


@dataclass
class TerminalSnapshot:
    """Everything the Overview page and Research Note need in one object."""
    as_of: datetime
    provenance: DataProvenance
    market_state: MarketState
    drivers: DriverModel
    regime: RegimeState
    levels: LevelMap
    distribution: DistributionResult
    outlook: OutlookDashboard
    consensus: ConsensusSummary           # daily (kept for overview/narrative/report)
    consensus_mtf: TimeframeConsensus     # daily / weekly / monthly matrix
    risk: RiskAssessment
