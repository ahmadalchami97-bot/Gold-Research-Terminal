"""The canonical in-memory market dataset passed to every engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

from app.schemas import DataProvenance


@dataclass
class MarketData:
    """Aligned, analysis-ready market dataset.

    ``prices`` is daily gold OHLCV (canonical columns from ``catalog.PRICE_COLS``).
    ``macro`` is the driver complex, forward-filled onto the gold trading
    calendar. ``positioning`` (CFTC, weekly) and ``news_raw`` are optional.
    """

    prices: pd.DataFrame
    macro: pd.DataFrame
    positioning: pd.DataFrame | None
    news_raw: list[dict] = field(default_factory=list)
    provenance: DataProvenance | None = None

    # --- convenience accessors -------------------------------------------
    @property
    def close(self) -> pd.Series:
        return self.prices["close"].dropna()

    @property
    def as_of(self) -> datetime:
        if len(self.prices.index):
            ts = self.prices.index[-1]
            return ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
        return datetime.now(timezone.utc)

    @property
    def spot(self) -> float:
        return float(self.close.iloc[-1])

    def aligned(self) -> pd.DataFrame:
        """Gold close joined with macro columns on the gold calendar."""
        frame = self.macro.reindex(self.prices.index).ffill()
        frame = frame.assign(gold=self.prices["close"])
        return frame

    def has_macro(self, key: str) -> bool:
        return key in self.macro.columns and self.macro[key].notna().any()
