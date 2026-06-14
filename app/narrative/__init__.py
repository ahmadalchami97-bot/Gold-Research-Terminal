"""Narrative façade: grounded Claude prose with deterministic fallback."""
from __future__ import annotations

from app.config import get_settings
from app.data.types import MarketData
from app.engines import news as news_engine
from app.narrative import claude, templates
from app.schemas import NarrativeBlock, NewsDigest, TerminalSnapshot


def get_narrative(snap: TerminalSnapshot, prefer_claude: bool = True) -> list[NarrativeBlock]:
    """Claude narrative when enabled, else the deterministic template engine."""
    if prefer_claude and get_settings().claude_enabled:
        blocks = claude.generate_narrative(snap)
        if blocks:
            return blocks
    return templates.build_blocks(snap)


def get_news_digest(data: MarketData, snap: TerminalSnapshot | None = None,
                    prefer_claude: bool = True) -> NewsDigest:
    """Claude-interpreted news digest when enabled, else the lexicon engine."""
    if prefer_claude and get_settings().claude_enabled and data.news_raw:
        context = {}
        if snap is not None:
            context = {
                "gold_price": snap.market_state.price,
                "real_yield_dominant": snap.drivers.dominant_driver,
                "vol_regime": snap.regime.vol_regime,
            }
        digest = claude.interpret_news(data.news_raw, context)
        if digest:
            return digest
    return news_engine.compute(data)
