"""News engine — macro scoring & gold classification.

Deterministic, rule-based baseline that turns raw headlines into a structured
digest: per-item gold classification, "what happened", "what it means for
gold", and an aggregate recency-weighted Macro Score (-100..+100). This is the
always-available fallback; the Claude layer (narrative/claude.py) can enrich the
prose and classification, then reuse :func:`aggregate`.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from app.data.types import MarketData
from app.engines.util import clamp
from app.schemas import Classification, NewsDigest, NewsItem

# Gold transmission lexicon: phrase -> signed weight (positive = bullish gold).
LEXICON: dict[str, int] = {
    # supportive
    "rate cut": 2, "rate cuts": 2, "cuts rates": 2, "dovish": 2, "easing": 1,
    "weaker dollar": 2, "dollar slips": 2, "dollar falls": 2, "dollar weakens": 2,
    "dollar drops": 2, "two-month low": 1, "real yields ease": 2, "yields ease": 1,
    "yields fall": 2, "yields drop": 1, "real yields fall": 2, "safe-haven": 2,
    "safe haven": 2, "geopolitical": 2, "tensions": 1, "central bank": 2,
    "central banks": 2, "reserves": 1, "record high": 1, "record": 1,
    "etf inflows": 2, "etf holdings rise": 2, "holdings rise": 1, "inflows": 1,
    "recession": 1, "soft": 1, "undershoot": 1, "undershoots": 1, "cut bets": 2,
    "rate-cut": 2, "cooler": 1, "cools": 1,
    # headwinds
    "rate hike": -2, "rate hikes": -2, "hikes rates": -2, "hawkish": -2,
    "stronger dollar": -2, "dollar rises": -2, "dollar climbs": -2,
    "dollar firms": -2, "dollar gains": -2, "yields climb": -2, "yields rise": -2,
    "real yields rise": -2, "real rates": -1, "rising real": -2, "strong jobs": -2,
    "strong payrolls": -2, "hot inflation": -1, "etf outflows": -2,
    "outflows": -1, "risk-on": -1, "taper": -1, "higher for longer": -2,
    "yields jump": -2, "pares gains": -1, "caps": -1, "pressure": -1,
}


def _score_text(text: str) -> int:
    low = text.lower()
    return sum(w for phrase, w in LEXICON.items() if phrase in low)


def classify_item(raw: dict) -> NewsItem:
    text = f"{raw.get('headline', '')} {raw.get('summary', '')}"
    raw_score = _score_text(text)
    impact = int(clamp(raw_score, -2, 2)) if raw_score else 0
    if impact > 0:
        cls, meaning = Classification.BULLISH, _meaning(text, "bull")
    elif impact < 0:
        cls, meaning = Classification.BEARISH, _meaning(text, "bear")
    else:
        cls, meaning = Classification.NEUTRAL, (
            "Limited direct transmission to gold; monitored for macro context.")
    return NewsItem(
        headline=raw.get("headline", ""), source=raw.get("source", ""),
        url=raw.get("url", ""), published_at=raw.get("published_at"),
        classification=cls, impact_score=impact,
        what_happened=raw.get("headline", ""), what_it_means=meaning)


def _meaning(text: str, side: str) -> str:
    low = text.lower()
    drivers = []
    if any(t in low for t in ("yield", "real rate", "real yields")):
        drivers.append("real yields")
    if "dollar" in low or "dxy" in low:
        drivers.append("the US dollar")
    if any(t in low for t in ("fed", "rate", "dovish", "hawkish", "cut", "hike")):
        drivers.append("Fed-policy expectations")
    if any(t in low for t in ("safe", "geopolit", "tension", "war")):
        drivers.append("safe-haven demand")
    if any(t in low for t in ("central bank", "reserves", "etf", "holdings", "inflow", "outflow")):
        drivers.append("official-sector / ETF flows")
    chan = ", ".join(drivers) if drivers else "macro conditions"
    if side == "bull":
        return f"Supportive for gold via {chan} — lowers the opportunity cost of " \
               "holding bullion or lifts safe-haven / flow demand."
    return f"A headwind for gold via {chan} — raises the opportunity cost of " \
           "holding non-yielding bullion or curbs demand."


def _recency_weight(dt: datetime | None, now: datetime) -> float:
    if dt is None:
        return 0.5
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (now - dt).total_seconds() / 86400.0)
    return float(math.exp(-age_days / 5.0))


def aggregate(items: list[NewsItem], generated_by: str = "lexicon") -> NewsDigest:
    now = datetime.now(timezone.utc)
    as_of = now
    if not items:
        return NewsDigest(as_of=as_of, items=[], macro_score=0.0,
                          overall_classification=Classification.NEUTRAL,
                          bullish_count=0, neutral_count=0, bearish_count=0,
                          generated_by=generated_by,
                          summary="No gold-relevant headlines available.")

    num = den = 0.0
    for it in items:
        w = _recency_weight(it.published_at, now)
        num += w * it.impact_score
        den += w
    macro = clamp((num / den) * 50.0, -100, 100) if den else 0.0

    bull = sum(1 for i in items if i.classification == Classification.BULLISH)
    bear = sum(1 for i in items if i.classification == Classification.BEARISH)
    neu = len(items) - bull - bear
    overall = (Classification.BULLISH if macro > 12 else
               Classification.BEARISH if macro < -12 else Classification.NEUTRAL)

    summary = (f"Macro news score {macro:+.0f}/100 ({overall.value} for gold). "
               f"{bull} supportive, {bear} headwind, {neu} neutral of "
               f"{len(items)} headlines.")
    return NewsDigest(as_of=as_of, items=items, macro_score=round(macro, 1),
                      overall_classification=overall, bullish_count=bull,
                      neutral_count=neu, bearish_count=bear,
                      generated_by=generated_by, summary=summary)


def compute(data: MarketData) -> NewsDigest:
    items = [classify_item(r) for r in (data.news_raw or [])]
    return aggregate(items, generated_by="lexicon")
