"""Canonical data contract shared by every provider and engine.

The terminal standardises on two daily, date-indexed frames plus optional
lower-frequency tables. Column names are fixed here so engines never depend on
a particular vendor's symbology.

PRICE_COLS  -> OHLCV for the gold front-month / spot (technical analysis).
MACRO_COLS  -> aligned driver series (forward-filled to trading days).
"""
from __future__ import annotations

from dataclasses import dataclass

# --- canonical column names -------------------------------------------------
PRICE_COLS = ["open", "high", "low", "close", "volume"]

# Macro / driver columns (units noted in SeriesSpec below).
MACRO_COLS = [
    "dxy",            # US Dollar Index (level)
    "real_yield_10y", # 10y TIPS real yield (%)
    "nominal_10y",    # 10y nominal Treasury yield (%)
    "breakeven_10y",  # 10y breakeven inflation (%)
    "vix",            # CBOE VIX (level)
    "spx",            # S&P 500 (level)
    "silver",         # Silver spot (USD/oz) -> gold/silver ratio
]

# Positioning (CFTC, weekly).
POSITIONING_COLS = ["mm_long", "mm_short", "mm_net", "open_interest"]


@dataclass(frozen=True)
class SeriesSpec:
    """Registry entry describing one logical series and where it comes from."""

    key: str            # canonical column / series key
    label: str          # human label for UI
    units: str
    yahoo: str | None    # Yahoo Finance symbol
    fred: str | None     # FRED series id
    source: str         # primary source name
    license: str        # licensing posture
    note: str = ""


# --- series registry --------------------------------------------------------
# Primary source preference: Yahoo for tradable instruments, FRED for the
# rates/inflation complex (TIPS real yields have no clean keyless source).
REGISTRY: list[SeriesSpec] = [
    SeriesSpec("gold", "Gold front-month (COMEX GC=F)", "USD/oz",
               "GC=F", "IR14270", "Yahoo Finance / LBMA",
               "Research/personal use (Yahoo ToS); LBMA via FRED public domain",
               "Spot/near-month gold price; OHLCV used for technical analysis."),
    SeriesSpec("dxy", "US Dollar Index", "level",
               "DX-Y.NYB", "DTWEXBGS", "ICE / Federal Reserve",
               "Yahoo ToS / FRED public domain",
               "Inverse gold driver: gold is priced in USD."),
    SeriesSpec("real_yield_10y", "10y TIPS real yield", "percent",
               None, "DFII10", "FRED (US Treasury)", "Public domain",
               "Primary macro driver: opportunity cost of holding non-yielding gold."),
    SeriesSpec("nominal_10y", "10y Treasury yield", "percent",
               "^TNX", "DGS10", "CBOE / FRED", "Yahoo ToS / public domain",
               "Nominal = real + breakeven."),
    SeriesSpec("breakeven_10y", "10y breakeven inflation", "percent",
               None, "T10YIE", "FRED", "Public domain",
               "Market-implied inflation; supports the inflation-hedge thesis."),
    SeriesSpec("vix", "CBOE VIX", "level",
               "^VIX", "VIXCLS", "CBOE / FRED", "Yahoo ToS / public domain",
               "Risk sentiment / safe-haven demand proxy."),
    SeriesSpec("spx", "S&P 500", "level",
               "^GSPC", "SP500", "S&P / FRED", "Yahoo ToS / public domain",
               "Cross-asset risk benchmark."),
    SeriesSpec("silver", "Silver spot", "USD/oz",
               "SI=F", "SLVPRD", "COMEX", "Yahoo ToS",
               "Gold/silver ratio — relative precious-metals positioning."),
]

REGISTRY_BY_KEY = {s.key: s for s in REGISTRY}


def label_for(key: str) -> str:
    spec = REGISTRY_BY_KEY.get(key)
    return spec.label if spec else key
