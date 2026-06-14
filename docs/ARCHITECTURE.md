# Architecture

A single Python **Streamlit** application (deployable to Streamlit Community
Cloud) over a pure, unit-tested analytics core. The intellectual value lives in
the engines; the UI is a thin, consistent consumer of typed results.

```
┌──────────────────────── streamlit_app.py ────────────────────────┐
│  st.navigation · institutional theme · status sidebar             │
└───────────────────────────────┬───────────────────────────────────┘
                                 │ calls render() per page
┌───────────────────────────────┴───────────────────────────────────┐
│  app/pages/*  — thin renderers (no business logic)                 │
│  app/ui/*     — theme, Plotly template, components, cached accessors│
├────────────────────────────────────────────────────────────────────┤
│  app/narrative/  deterministic templates + grounded Claude layer    │
│  app/reporting/  Markdown / HTML research-note builders             │
├────────────────────────────────────────────────────────────────────┤
│  app/engines/   PURE quant (no Streamlit, no I/O) → typed schemas    │
│  market_state · indicators · drivers · regime · levels ·            │
│  distribution · outlook · risk · news · snapshot (orchestrator)     │
├────────────────────────────────────────────────────────────────────┤
│  app/data/   providers (yahoo·fred·cftc·news·demo) · service · types │
│  live fetch → snapshot fallback;  st.cache_data;  DataProvenance     │
└────────────────────────────────────────────────────────────────────┘
```

## Principles

- **Pure engines.** Everything in `app/engines/` is a deterministic function:
  `MarketData → dataclass`. No Streamlit imports, no network. This makes the
  analytics trivially unit-testable (`tests/test_engines.py`) and reusable.
- **Typed contracts.** `app/schemas/` holds plain dataclasses with enums for the
  discrete vocabularies (5-state direction, 5-state indicator, 3-state news).
  Engines, narrative, reporting and UI all share them.
- **Single source of truth.** The outlook engine consumes the distribution,
  drivers, consensus and risk outputs, so every figure across the terminal
  reconciles (e.g. the Outlook fan and the Probability fan are the same model).
- **Graceful degradation.** Missing keys, dead feeds, or no LLM never crash a
  page — they degrade one panel and surface provenance. `app/data/service.py`
  falls back to the committed snapshot; `app/narrative/` falls back to
  deterministic templates; news falls back to the rule-based lexicon.
- **Reproducibility & audit.** Fixed Monte Carlo seed (shown in the UI); every
  metric is documented in `docs/METHODOLOGY.md`; the Claude layer receives only
  computed numbers and the exact payload is reconstructable.

## Request flow (one page load)

1. `app/ui/data.get_snapshot()` calls the cached `service.get_market_data()`
   (live → snapshot fallback) and builds a `TerminalSnapshot` via
   `engines/snapshot.build_snapshot()` (cached on dataset identity + seed).
2. The page renders scorecards/charts/tables from the snapshot using
   `app/ui/components.py` and `app/ui/plotly_template.py`.
3. Narrative/news pages additionally call `app/narrative` (Claude when a key is
   present, deterministic otherwise).

## Performance notes (Streamlit Cloud)

Dependencies are kept lean (no `feedparser`, `ruptures`, `hmmlearn`, `sklearn`,
or PDF/crypto stacks) to respect the ~1 GB community tier. GARCH + 18k-path Monte
Carlo runs in ~0.1 s; the snapshot is cached per dataset so it is computed once
per refresh, not per page.
