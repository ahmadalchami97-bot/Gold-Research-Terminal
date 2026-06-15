# 🪙 Gold Research Terminal

**Institutional-grade gold research, outlook & probability analytics** — built for
portfolio managers, investment analysts and research desks.

This is **not** a trading bot, signal generator, or buy/sell application. It is a
**decision-support research terminal** that answers:

> What is gold doing? · Why? · What changed? · What levels matter? · What is the
> outlook? · What is the probability distribution? · What is the expected range? ·
> What could invalidate the thesis?

Every figure traces to a named data source and a documented formula
(`docs/METHODOLOGY.md`). Monte Carlo runs use a fixed, displayed seed.

---

## Dashboards

| Page | Question | Highlights |
|---|---|---|
| **Executive Overview** | At a glance | Scorecards, research summary, cross-horizon outlook, fan chart |
| **Market State** | What is gold doing? | Multi-horizon returns, MAs, realized vol, ATR, 52w range, drawdown |
| **Drivers & Attribution** | Why? | Multi-factor regression, attribution waterfall, correlation heatmap |
| **Regime & Change** | What changed? | Vol/trend/correlation regimes, change-point detection |
| **Levels** | What levels matter? | Swings, pivots, MAs, Fibonacci, round numbers, vol bands |
| **Outlook Dashboard** | What is the outlook? | 1W/1M/3M: direction, target, range, confidence, key driver, invalidation |
| **Probability & Range** | Distribution / range | GARCH + Monte Carlo fan, distribution, expected ranges, touch probabilities |
| **Indicator Consensus** | Technical posture | 14-indicator 5-state matrix, pie, bar, 0–100 institutional score |
| **Risk & Invalidation** | What invalidates it? | VaR/CVaR, drawdown, invalidation levels, risk triggers |
| **News & Events** | Macro flow | Macro score, gold classification, *what happened / what it means* |
| **Research Note** | Output | Compiled note, exportable to Markdown and print-ready HTML |

## Architecture

A single Python **Streamlit** app over a pure, unit-tested analytics core.

```
streamlit_app.py            entry point (st.navigation + status sidebar)
app/
├─ ui/        theme · Plotly template · components · cached data accessors
├─ pages/     one renderer per dashboard (thin; no business logic)
├─ engines/   PURE quant: market_state · indicators · drivers · regime ·
│             levels · distribution · outlook · risk · news · snapshot
├─ data/      providers (Yahoo, FRED, CFTC, RSS news, demo) · service · catalog
├─ narrative/ deterministic templates + grounded Claude layer
├─ reporting/ Markdown / HTML research-note builders
└─ schemas/   typed result contracts (dataclasses)
data_samples/ committed synthetic snapshot (offline fallback)
docs/         ARCHITECTURE · METHODOLOGY · DATA_SOURCES
tests/        pytest golden-masters + page smoke tests
```

**Data resilience:** the service fetches live, and on any failure (timeout, rate
limit, missing key) falls back to the committed snapshot — the terminal never
renders blank. A `LIVE / CACHED` badge shows provenance.

## Run locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Optional keys (the app runs fully without them — see graceful degradation below).
Copy `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml`:

| Secret | Enables | Without it |
|---|---|---|
| `FRED_API_KEY` | 10y real yields, breakevens, CPI | Falls back to keyless FRED CSV / Yahoo; that driver may be marked unavailable |
| `ANTHROPIC_API_KEY` | Claude narrative + news interpretation | Deterministic templates + rule-based lexicon |
| `NEWSAPI_KEY` | Extra news source | Keyless RSS feeds only |
| `DATA_MODE` | `auto` (default) / `live` / `demo` | `auto`: live with snapshot fallback |

> The narrative layer defaults to the most capable Claude model
> (`claude-opus-4-8`). Set `ANTHROPIC_MODEL` to a faster/cheaper model to cut cost.

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub.
2. On [share.streamlit.io](https://share.streamlit.io), create an app pointing at
   the repo/branch with main file `streamlit_app.py`.
3. Add any secrets above in **Settings → Secrets** (TOML format, same keys as the
   example). All are optional.
4. (Optional) In **Advanced settings**, select Python 3.11, 3.12 or 3.13 — all are
   supported. The app deliberately ships **no** `.python-version`/`runtime.txt` pin
   so Streamlit Cloud installs `requirements.txt` into its own managed interpreter.
5. Deploy. Live data fetches at runtime; the bundled snapshot guarantees a
   working first render even before keys are set.

> If a redeploy ever shows a missing dependency, use **Manage app → Reboot**
> (clear cache) so Cloud rebuilds the environment from `requirements.txt`.

## Develop

```bash
pip install -r requirements-dev.txt
python scripts/seed_samples.py     # regenerate the offline snapshot
pytest                             # engine golden-masters + page smoke tests
ruff check .                       # lint
```

## Compliance

Research and decision-support only — **not investment advice**, and not a
recommendation, offer or solicitation to transact. Figures are model estimates
derived from public data and documented methodology; they carry uncertainty and
may be revised. Past behaviour does not guarantee future results. Review each
data source's licensing in `docs/DATA_SOURCES.md` before any redistribution.
