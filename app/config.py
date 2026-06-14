"""Central configuration for the Gold Research Terminal.

Settings resolve from (1) process environment variables, then (2) Streamlit
secrets (``st.secrets``), then (3) documented defaults. Nothing here raises if
Streamlit is unavailable (e.g. under pytest) or if no secrets file exists, so
the engines and data layer can be imported and unit-tested in isolation.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

# Default Anthropic model for the grounded narrative layer — the most capable
# Claude model. Override via the ANTHROPIC_MODEL secret (e.g. a faster/cheaper
# model) if cost or latency matters more than prose quality.
DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-8"


def _get(key: str, default: str | None = None) -> str | None:
    """Resolve a setting from the environment, then Streamlit secrets."""
    val = os.environ.get(key)
    if val:
        return val
    try:  # Streamlit secrets are optional and may not exist.
        import streamlit as st

        try:
            if key in st.secrets:
                secret = st.secrets[key]
                return str(secret) if secret != "" else default
        except Exception:
            # No secrets.toml present, or secrets not initialised yet.
            return default
    except Exception:
        return default
    return default


def _get_int(key: str, default: int) -> int:
    raw = _get(key)
    try:
        return int(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    """Immutable resolved configuration snapshot."""

    fred_api_key: str | None
    anthropic_api_key: str | None
    anthropic_model: str
    newsapi_key: str | None
    data_mode: str  # "auto" | "live" | "demo"

    # Cache time-to-live (seconds) used by the Streamlit data cache.
    ttl_prices: int
    ttl_macro: int
    ttl_news: int

    request_timeout: int
    mc_seed: int  # fixed seed → reproducible Monte Carlo

    # --- capability flags -------------------------------------------------
    @property
    def fred_enabled(self) -> bool:
        return bool(self.fred_api_key)

    @property
    def claude_enabled(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def newsapi_enabled(self) -> bool:
        return bool(self.newsapi_key)

    @property
    def allow_live(self) -> bool:
        return self.data_mode in ("auto", "live")

    @property
    def force_demo(self) -> bool:
        return self.data_mode == "demo"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        fred_api_key=_get("FRED_API_KEY"),
        anthropic_api_key=_get("ANTHROPIC_API_KEY"),
        anthropic_model=_get("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL) or DEFAULT_ANTHROPIC_MODEL,
        newsapi_key=_get("NEWSAPI_KEY"),
        data_mode=(_get("DATA_MODE", "auto") or "auto").lower(),
        ttl_prices=_get_int("TTL_PRICES", 900),     # 15 min
        ttl_macro=_get_int("TTL_MACRO", 3600),      # 1 hour
        ttl_news=_get_int("TTL_NEWS", 1800),        # 30 min
        request_timeout=_get_int("REQUEST_TIMEOUT", 12),
        mc_seed=_get_int("MC_SEED", 20260614),
    )


# Product-level constants ----------------------------------------------------
APP_NAME = "Gold Research Terminal"
APP_TAGLINE = "Institutional gold research, outlook & probability analytics"
DISCLAIMER = (
    "Research and decision-support only. Not investment advice, not a "
    "recommendation, offer or solicitation to transact. Figures are model "
    "estimates derived from public data and documented methodology; they carry "
    "uncertainty and may be revised. Past behaviour does not guarantee future "
    "results."
)
