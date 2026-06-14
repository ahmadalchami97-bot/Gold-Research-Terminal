"""Optional Claude narrative layer (grounded in computed metrics).

Strictly narrates the numbers the engines produced — it never invents figures.
Off by default; enabled only when ANTHROPIC_API_KEY is present. Every failure
path (no key, API error, refusal, bad JSON) returns None so callers fall back
to the deterministic templates. The exact metrics sent are returned for audit.
"""
from __future__ import annotations

import json

from app.config import get_settings
from app.engines import news as news_engine
from app.schemas import (Classification, NarrativeBlock, NewsDigest, NewsItem,
                         TerminalSnapshot)

SYSTEM = (
    "You are a precise sell-side commodities research analyst writing for "
    "portfolio managers and investment committees. You receive a JSON object of "
    "PRE-COMPUTED gold-market metrics and must write concise, professional "
    "institutional prose that narrates ONLY those numbers.\n"
    "Absolute rules:\n"
    "1. Never invent, estimate, extrapolate or alter any figure. Use only values "
    "present in the input. If something is missing, omit it — do not guess.\n"
    "2. No buy/sell/hold recommendations. This is research: frame everything as "
    "bias, scenarios, probabilities, drivers and invalidation levels.\n"
    "3. Be specific and quantitative, citing the provided numbers.\n"
    "4. Output ONLY valid JSON with the requested keys — no markdown, no preamble."
)


def _round(v, dp=2):
    return round(v, dp) if isinstance(v, (int, float)) else v


def snapshot_metrics(snap: TerminalSnapshot) -> dict:
    """Compact, audit-ready dict of the figures handed to the model."""
    ms = snap.market_state
    return {
        "price": _round(ms.price),
        "change_1d_pct": _round(ms.change_pct_1d),
        "returns_pct": {r.horizon: _round(r.pct) for r in ms.returns},
        "annualized_vol_pct": _round(ms.annualized_vol, 1),
        "drawdown_from_ath_pct": _round(ms.drawdown_from_ath_pct),
        "pct_of_52w_range": _round(ms.pct_of_52w_range, 0),
        "trend_state": ms.trend_state,
        "drivers": {
            "r_squared": _round(snap.drivers.r_squared),
            "dominant": snap.drivers.dominant_driver,
            "contributions_bps": {b.label: _round(b.contribution_bps, 0)
                                  for b in snap.drivers.betas[:5]},
            "corr_90d": {b.label: _round(b.corr_90d) for b in snap.drivers.betas[:5]},
        },
        "regime": {
            "vol_regime": snap.regime.vol_regime,
            "vol_percentile": _round(snap.regime.vol_percentile, 0),
            "trend_regime": snap.regime.trend_regime,
            "correlation_regime": snap.regime.correlation_regime,
            "what_changed": snap.regime.what_changed[:4],
        },
        "consensus": {
            "score_0_100": _round(snap.consensus.institutional_score, 0),
            "label": snap.consensus.institutional_label,
            "bullish_pct": snap.consensus.bullish_pct,
            "bearish_pct": snap.consensus.bearish_pct,
        },
        "outlook": [
            {"horizon": h.horizon, "direction": h.direction.value,
             "target": _round(h.target_price), "range": [_round(h.expected_low),
             _round(h.expected_high)], "confidence": h.confidence.value,
             "key_driver": h.key_driver} for h in snap.outlook.horizons],
        "risk": {
            "var_95_1d_pct": snap.risk.var_95_1d_pct,
            "cvar_95_1d_pct": snap.risk.cvar_95_1d_pct,
            "max_drawdown_1y_pct": snap.risk.max_drawdown_1y_pct,
            "bull_invalidation": snap.risk.bull_invalidation.level,
            "bear_invalidation": snap.risk.bear_invalidation.level,
            "triggers": [f"{t.name} ({t.severity})" for t in snap.risk.triggers],
        },
    }


def _call(prompt: str, max_tokens: int = 3000) -> dict | None:
    settings = get_settings()
    if not settings.claude_enabled:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        resp = client.messages.create(
            model=settings.anthropic_model, max_tokens=max_tokens,
            system=SYSTEM, messages=[{"role": "user", "content": prompt}])
        if resp.stop_reason == "refusal":
            return None
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1].lstrip("json").strip()
        return json.loads(text)
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Research narrative
# --------------------------------------------------------------------------- #
_NARRATIVE_KEYS = [
    ("executive_summary", "Executive summary"),
    ("what_gold_is_doing", "What gold is doing"),
    ("why", "Why it is doing it"),
    ("what_changed", "What changed"),
    ("outlook", "Outlook"),
    ("risks", "Risks & invalidation"),
]


def generate_narrative(snap: TerminalSnapshot) -> list[NarrativeBlock] | None:
    metrics = snapshot_metrics(snap)
    prompt = (
        "Write an institutional gold research note from these metrics. Return JSON "
        "with keys: executive_summary, what_gold_is_doing, why, what_changed, "
        "outlook, risks. Each value is 2-4 sentences of prose.\n\n"
        f"METRICS:\n{json.dumps(metrics, indent=2)}")
    data = _call(prompt)
    if not data:
        return None
    blocks = []
    for key, title in _NARRATIVE_KEYS:
        body = data.get(key)
        if isinstance(body, str) and body.strip():
            blocks.append(NarrativeBlock(title, body.strip(), "claude"))
    return blocks or None


# --------------------------------------------------------------------------- #
# News interpretation
# --------------------------------------------------------------------------- #
def interpret_news(raw_items: list[dict], context: dict) -> NewsDigest | None:
    if not raw_items:
        return None
    headlines = [{"i": i, "headline": r.get("headline", ""),
                  "summary": r.get("summary", "")[:240]}
                 for i, r in enumerate(raw_items)]
    prompt = (
        "Classify each gold-related headline's likely impact on the GOLD price via "
        "the standard transmission channels (real yields, the US dollar, Fed-policy "
        "expectations, safe-haven demand, official-sector/ETF flows). Do not invent "
        "facts beyond each headline. Return JSON: {\"items\": [{\"i\": <index>, "
        "\"classification\": \"Bullish|Neutral|Bearish\", \"impact_score\": -2..2, "
        "\"what_happened\": \"one factual sentence\", \"what_it_means\": \"one "
        "sentence on the gold transmission\"}], \"summary\": \"one-sentence macro "
        "read\"}. Bullish/Bearish are from gold's perspective.\n\n"
        f"MARKET CONTEXT: {json.dumps(context)}\n\nHEADLINES: {json.dumps(headlines)}")
    data = _call(prompt, max_tokens=4000)
    if not data or "items" not in data:
        return None

    by_idx = {it.get("i"): it for it in data["items"] if isinstance(it, dict)}
    items: list[NewsItem] = []
    for i, raw in enumerate(raw_items):
        info = by_idx.get(i)
        if not info:
            items.append(news_engine.classify_item(raw))  # deterministic fallback
            continue
        try:
            cls = Classification(info.get("classification", "Neutral"))
        except ValueError:
            cls = Classification.NEUTRAL
        impact = int(max(-2, min(2, info.get("impact_score", 0) or 0)))
        items.append(NewsItem(
            headline=raw.get("headline", ""), source=raw.get("source", ""),
            url=raw.get("url", ""), published_at=raw.get("published_at"),
            classification=cls, impact_score=impact,
            what_happened=str(info.get("what_happened", raw.get("headline", "")))[:400],
            what_it_means=str(info.get("what_it_means", ""))[:400]))

    digest = news_engine.aggregate(items, generated_by="claude")
    if data.get("summary"):
        digest.summary = str(data["summary"])[:400]
    return digest
