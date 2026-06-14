"""Bundled-snapshot provider.

Loads the committed sample dataset from ``data_samples/`` so the terminal always
renders — offline, on a cold Streamlit Cloud start, or when a live feed is rate
limited. The snapshot is clearly labelled as synthetic/sample throughout the UI.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from app.data.types import MarketData
from app.schemas import DataProvenance, SeriesStatus

SAMPLES_DIR = Path(__file__).resolve().parents[3] / "data_samples"


def is_available() -> bool:
    return (SAMPLES_DIR / "prices.parquet").exists()


def _read_parquet(name: str) -> pd.DataFrame | None:
    path = SAMPLES_DIR / name
    if not path.exists():
        return None
    frame = pd.read_parquet(path)
    frame.index = pd.to_datetime(frame.index)
    return frame


def load() -> MarketData:
    prices = _read_parquet("prices.parquet")
    macro = _read_parquet("macro.parquet")
    positioning = _read_parquet("positioning.parquet")
    if prices is None or macro is None:
        raise FileNotFoundError(
            f"Sample snapshot missing in {SAMPLES_DIR}. Run scripts/seed_samples.py."
        )

    news_path = SAMPLES_DIR / "news.json"
    news_raw: list[dict] = []
    if news_path.exists():
        for item in json.loads(news_path.read_text()):
            dt = item.get("published_at")
            item["published_at"] = pd.to_datetime(dt).to_pydatetime() if dt else None
            news_raw.append(item)

    as_of = prices.index[-1].to_pydatetime()
    keys = ["gold"] + list(macro.columns)
    status = [
        SeriesStatus(key=k, source="synthetic-sample", mode="cached",
                     as_of=as_of, ok=True, detail="bundled snapshot")
        for k in keys
    ]
    provenance = DataProvenance(
        mode="cached",
        generated_at=datetime.now(timezone.utc),
        series=status,
    )
    return MarketData(prices=prices, macro=macro, positioning=positioning,
                      news_raw=news_raw, provenance=provenance)
