"""Compose all engines into a single :class:`TerminalSnapshot`.

Used by the Overview page and the Research Note. Individual pages may also call
individual engines directly. Engine order respects dependencies: the outlook
engine consumes the distribution, drivers, consensus and risk outputs so every
figure in the terminal reconciles.
"""
from __future__ import annotations

from app.data.types import MarketData
from app.engines import distribution as distribution_engine
from app.engines import drivers as drivers_engine
from app.engines import indicators as indicators_engine
from app.engines import levels as levels_engine
from app.engines import market_state as market_state_engine
from app.engines import outlook as outlook_engine
from app.engines import regime as regime_engine
from app.engines import risk as risk_engine
from app.schemas import TerminalSnapshot


def build_snapshot(data: MarketData, mc_seed: int = 20260614) -> TerminalSnapshot:
    market_state = market_state_engine.compute(data)
    consensus = indicators_engine.compute(data)
    levels = levels_engine.compute(data)
    drivers = drivers_engine.compute(data)
    regime = regime_engine.compute(data)
    distribution = distribution_engine.compute(data, seed=mc_seed)
    risk = risk_engine.compute(data, regime=regime)
    outlook = outlook_engine.compute(data, distribution, drivers, consensus, risk, regime)

    return TerminalSnapshot(
        as_of=market_state.as_of,
        provenance=data.provenance,
        market_state=market_state,
        drivers=drivers,
        regime=regime,
        levels=levels,
        distribution=distribution,
        outlook=outlook,
        consensus=consensus,
        risk=risk,
    )
