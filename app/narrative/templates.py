"""Deterministic, fully-auditable narrative.

Every sentence is templated from computed metrics — no LLM, no invented
figures. This is the default prose and the fallback whenever the Claude layer
is disabled or unavailable.
"""
from __future__ import annotations

from app.schemas import NarrativeBlock, TerminalSnapshot


def _pct(x: float | None, dp: int = 1) -> str:
    return "n/a" if x is None else f"{x:+.{dp}f}%"


def market_state_text(snap: TerminalSnapshot) -> str:
    ms = snap.market_state
    rets = {r.horizon: r.pct for r in ms.returns}
    return (
        f"Gold is trading at ${ms.price:,.0f}, {_pct(ms.change_pct_1d)} on the day "
        f"and {_pct(rets.get('1M'))} over the past month ({_pct(rets.get('1Y'))} "
        f"year-on-year). Price sits {ms.pct_of_52w_range:.0f}% of the way up its "
        f"52-week range and {_pct(ms.drawdown_from_ath_pct)} from the all-time high. "
        f"Realized volatility is {ms.annualized_vol:.0f}% annualized. {ms.trend_state}.")


def drivers_text(snap: TerminalSnapshot) -> str:
    d = snap.drivers
    if not d.betas:
        return "Driver attribution is unavailable for the current dataset."
    lead = d.betas[0]
    parts = [
        f"The trailing move decomposes primarily onto {d.dominant_driver.lower()}. "
        f"Over the estimation window the factor model explains {d.r_squared*100:.0f}% "
        f"of daily variance."]
    contribs = ", ".join(
        f"{b.label} {b.contribution_bps:+.0f}bps" for b in d.betas[:3])
    parts.append(f"Attributed contributions to the recent move: {contribs}.")
    parts.append(
        f"{lead.label} shows a 90-day correlation of {lead.corr_90d:+.2f} "
        f"(expected {lead.corr_sign_expected}).")
    return " ".join(parts)


def regime_text(snap: TerminalSnapshot) -> str:
    r = snap.regime
    bullets = " ".join(r.what_changed[:3])
    return (f"Volatility regime is {r.vol_regime.lower()} "
            f"({r.vol_percentile:.0f}th percentile); trend regime: "
            f"{r.trend_regime.lower()}. {r.correlation_regime}. {bullets}")


def outlook_text(snap: TerminalSnapshot) -> str:
    parts = []
    for h in snap.outlook.horizons:
        parts.append(
            f"{h.horizon}: {h.direction.value.lower()} bias, central estimate "
            f"${h.target_price:,.0f} (range ${h.expected_low:,.0f}-${h.expected_high:,.0f}), "
            f"{h.confidence.value.lower()} confidence.")
    return " ".join(parts)


def risk_text(snap: TerminalSnapshot) -> str:
    rk = snap.risk
    triggers = "; ".join(f"{t.name} ({t.severity.lower()})" for t in rk.triggers[:3])
    return (
        f"1-day 95% VaR is {rk.var_95_1d_pct:.1f}% (CVaR {rk.cvar_95_1d_pct:.1f}%); "
        f"the trailing-year max drawdown was {rk.max_drawdown_1y_pct:.1f}%. "
        f"The constructive case is negated on a close below "
        f"${rk.bull_invalidation.level:,.0f}; the bearish case on a close above "
        f"${rk.bear_invalidation.level:,.0f}. Key risk triggers: {triggers or 'none flagged'}.")


def executive_summary(snap: TerminalSnapshot) -> str:
    ms, c, o = snap.market_state, snap.consensus, snap.outlook
    near = o.horizons[0]
    return (
        f"Gold is at ${ms.price:,.0f} with a {c.institutional_label.lower()} technical "
        f"posture (score {c.institutional_score:.0f}/100). The {near.horizon.lower()} "
        f"view is {near.direction.value.lower()} with a central estimate of "
        f"${near.target_price:,.0f}, led by {near.key_driver.lower()}. "
        f"Volatility is {snap.regime.vol_regime.lower()} and the dominant macro driver "
        f"is {snap.drivers.dominant_driver.lower()}.")


def build_blocks(snap: TerminalSnapshot) -> list[NarrativeBlock]:
    src = "deterministic"
    return [
        NarrativeBlock("Executive summary", executive_summary(snap), src),
        NarrativeBlock("What gold is doing", market_state_text(snap), src),
        NarrativeBlock("Why it is doing it", drivers_text(snap), src),
        NarrativeBlock("What changed", regime_text(snap), src),
        NarrativeBlock("Outlook", outlook_text(snap), src),
        NarrativeBlock("Risks & invalidation", risk_text(snap), src),
    ]
