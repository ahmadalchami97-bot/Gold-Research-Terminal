"""Risk engine — "What could invalidate the thesis?"

Historical VaR/CVaR, one-year max drawdown, explicit bull/bear invalidation
levels, and a set of named risk triggers (real-yield spike, dollar breakout,
volatility regime, positioning crowding, real-yield decoupling).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.data.types import MarketData
from app.engines.util import TRADING_DAYS, log_returns, percentile_of_last
from app.schemas import Invalidation, RegimeState, RiskAssessment, RiskTrigger


def _var_cvar(ret: pd.Series, q: float) -> tuple[float, float]:
    sample = ret.iloc[-500:] if len(ret) > 500 else ret
    cutoff = np.percentile(sample, q)
    var = -cutoff * 100
    tail = sample[sample <= cutoff]
    cvar = -tail.mean() * 100 if len(tail) else var
    return float(var), float(cvar)


def compute(data: MarketData, regime: RegimeState | None = None) -> RiskAssessment:
    close = data.close
    ret = log_returns(close)
    price = float(close.iloc[-1])
    as_of = close.index[-1].to_pydatetime()

    var95, cvar95 = _var_cvar(ret, 5)
    var99, _ = _var_cvar(ret, 1)
    var95_1m = var95 * np.sqrt(21)

    window = close.iloc[-TRADING_DAYS:]
    max_dd = float((window / window.cummax() - 1).min() * 100)

    # invalidation levels from clean structural references
    ma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else price
    ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else price
    low_3m = float(close.iloc[-63:].min())
    high_3m = float(close.iloc[-63:].max())

    support = max([lv for lv in (ma50, ma200, low_3m) if lv < price], default=price * 0.95)
    resistance = min([lv for lv in (high_3m, price * 1.05) if lv > price], default=price * 1.05)

    bull_inval = Invalidation(
        level=round(support, 2),
        condition=f"Sustained daily close below {support:,.0f} "
                  f"({(support/price-1)*100:.1f}% away) negates the constructive case.")
    bear_inval = Invalidation(
        level=round(resistance, 2),
        condition=f"Sustained daily close above {resistance:,.0f} "
                  f"({(resistance/price-1)*100:+.1f}% away) negates the bearish case.")

    triggers: list[RiskTrigger] = []

    if data.has_macro("real_yield_10y"):
        ry = float(data.macro["real_yield_10y"].dropna().iloc[-1])
        triggers.append(RiskTrigger(
            name="Real-yield spike", severity="High",
            condition=f"10y real yield rises above {ry + 0.4:.2f}% (now {ry:.2f}%)",
            rationale="Higher real yields raise the opportunity cost of holding "
                      "non-yielding gold — the most direct headwind."))

    if data.has_macro("dxy"):
        dxy = data.macro["dxy"].dropna()
        recent_high = float(dxy.iloc[-63:].max())
        cur = float(dxy.iloc[-1])
        triggers.append(RiskTrigger(
            name="Dollar breakout", severity="Medium",
            condition=f"DXY closes above {recent_high:.1f} (now {cur:.1f})",
            rationale="A stronger dollar mechanically pressures USD-priced gold."))

    if regime is not None and regime.vol_percentile >= 80:
        triggers.append(RiskTrigger(
            name="Volatility regime", severity="Medium",
            condition=f"Realized vol in the {regime.vol_percentile:.0f}th percentile",
            rationale="Elevated volatility widens the distribution and the "
                      "probability of stop-driven, two-sided moves."))

    if data.positioning is not None and len(data.positioning) > 20:
        net = data.positioning["mm_net"]
        pctile = percentile_of_last(net, window=min(104, len(net)))
        if pctile >= 80:
            triggers.append(RiskTrigger(
                name="Positioning crowding", severity="Medium",
                condition=f"Managed-money net length in the {pctile:.0f}th percentile",
                rationale="Crowded longs raise the risk of a sharp unwind on "
                          "adverse macro surprises (contrarian risk)."))

    corr_breakdown = bool(regime.decoupled) if regime is not None else False
    if corr_breakdown:
        triggers.append(RiskTrigger(
            name="Real-yield decoupling", severity="Low",
            condition="Gold trading independently of real yields",
            rationale="When the usual macro anchor weakens, the thesis relies "
                      "more on flow/safe-haven demand, which can reverse quickly."))

    notes = [
        "VaR/CVaR are historical (non-parametric) on trailing ~2y daily returns; "
        "the 1-month figure scales the 1-day VaR by √21 (iid assumption).",
        "Invalidation levels are structural references, not stop recommendations.",
    ]

    return RiskAssessment(
        as_of=as_of, var_95_1d_pct=round(var95, 2), var_99_1d_pct=round(var99, 2),
        cvar_95_1d_pct=round(cvar95, 2), var_95_1m_pct=round(var95_1m, 2),
        max_drawdown_1y_pct=round(max_dd, 2),
        bull_invalidation=bull_inval, bear_invalidation=bear_inval,
        triggers=triggers, correlation_breakdown=corr_breakdown, notes=notes,
    )
