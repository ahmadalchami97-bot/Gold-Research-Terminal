"""CFTC Commitment of Traders (managed-money positioning) via Socrata.

Best-effort: gold COT helps explain crowding and contrarian risk. If the
endpoint or schema differs, the service degrades gracefully and the positioning
panel reports "unavailable".
"""
from __future__ import annotations

import pandas as pd

from app.data.providers.base import ProviderError, get_json

# CFTC disaggregated futures-only report (Socrata).
SOCRATA_URL = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"


def fetch_positioning(timeout: int = 15, limit: int = 400) -> pd.DataFrame:
    params = {
        "$where": "upper(commodity_name) like '%GOLD%'",
        "$order": "report_date_as_yyyy_mm_dd DESC",
        "$limit": limit,
    }
    try:
        rows = get_json(SOCRATA_URL, params=params, timeout=timeout)
    except ProviderError:
        # Some deployments expose the column as market_and_exchange_names.
        params["$where"] = "upper(market_and_exchange_names) like '%GOLD%'"
        rows = get_json(SOCRATA_URL, params=params, timeout=timeout)

    if not rows:
        raise ProviderError("CFTC returned no gold rows")

    frame = pd.DataFrame(rows)
    # Keep COMEX gold, drop micro / silver lookalikes.
    name_col = next((c for c in ("commodity_name", "market_and_exchange_names")
                     if c in frame.columns), None)
    if name_col:
        mask = frame[name_col].str.upper().str.contains("GOLD")
        mask &= ~frame[name_col].str.upper().str.contains("MICRO")
        frame = frame[mask]

    def num(col: str) -> pd.Series:
        return pd.to_numeric(frame.get(col), errors="coerce")

    out = pd.DataFrame({
        "mm_long": num("m_money_positions_long_all"),
        "mm_short": num("m_money_positions_short_all"),
        "open_interest": num("open_interest_all"),
    })
    out.index = pd.to_datetime(frame["report_date_as_yyyy_mm_dd"])
    out["mm_net"] = out["mm_long"] - out["mm_short"]
    out = out.dropna(subset=["mm_net"]).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    if out.empty:
        raise ProviderError("CFTC gold positioning parsed empty")
    return out[["mm_long", "mm_short", "mm_net", "open_interest"]]
