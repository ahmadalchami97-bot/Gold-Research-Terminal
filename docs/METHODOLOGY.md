# Methodology

Every figure in the terminal is computed by a pure function in `app/engines/`.
This document records the formulas, parameters and classification rules so that
any number can be reproduced and defended. Conventions: returns are daily log
returns `r_t = ln(P_t / P_{t-1})` unless stated; volatility is annualized with
`√252`.

---

## 1. Market State (`market_state.py`)

- **Returns** over 1D/1W(5)/1M(21)/3M(63)/1Y(252)/5Y(1260) trading days, plus
  **YTD** from the first close of the current calendar year. Simple percentage.
- **Moving averages** 20/50/100/200-day SMA; reports value, signed `price/MA−1`
  and above/below.
- **Realized volatility** = `√252 · stdev(r, window)` for windows 10/20/30; the
  headline annualized vol uses the 20-day window. Stored as **percent**.
- **ATR(14)** = mean true range / price, where
  `TR = max(H−L, |H−C_{−1}|, |L−C_{−1}|)`.
- **52-week range / drawdown:** position within the trailing-252-day high/low;
  drawdown vs. the all-time-high close.
- **Trend state** classified from price vs. the 20/50/100/200 MAs (all above →
  uptrend; all below → downtrend; otherwise constructive/corrective).

## 2. Indicator Consensus (`indicators.py`)

14 indicators, each mapped to one 5-state label `{Bearish −2, Slightly Bearish
−1, Neutral 0, Slightly Bullish +1, Bullish +2}`. Rules:

| Indicator | Computation | Classification |
|---|---|---|
| **RSI(14)** | Wilder RSI | ≥70 Slightly Bullish (overbought); 60–70 Bullish; 52–60 Sl. Bull; 48–52 Neutral; 40–48 Sl. Bear; 30–40 Bearish; <30 Sl. Bear (oversold) |
| **MACD(12,26,9)** | line=EMA12−EMA26, signal=EMA9, hist | hist≈0 (<0.04%·price) Neutral; line>signal & line>0 Bullish; line>signal Sl. Bull; line<signal & line<0 Bearish; else Sl. Bear |
| **Stochastic(14,3,3)** | slow %K/%D | level + %K vs %D cross (overbought >80 / oversold <20 tempered) |
| **Stoch RSI(14)** | stochastic of RSI | same level+cross logic as Stochastic |
| **ADX/DMI(14)** | Wilder ADX, ±DI | ADX<20 Neutral; +DI>−DI → Bullish (ADX≥25) / Sl. Bull; −DI>+DI → Bearish (ADX≥25) / Sl. Bear |
| **EMA20/50/100/200** | price vs EMA, distance `d%` | d>0.75% Bullish; 0.1–0.75% Sl. Bull; −0.1…0.1% Neutral; −0.75…−0.1% Sl. Bear; <−0.75% Bearish |
| **Ichimoku(9,26,52)** | price vs cloud + Tenkan/Kijun | above cloud → Bullish (Tenkan>Kijun) / Sl. Bull; below → Bearish / Sl. Bear; inside Neutral |
| **Bollinger(20,2)** | %B | >1 Sl. Bull (stretched); 0.8–1 Bullish; 0.55–0.8 Sl. Bull; 0.45–0.55 Neutral; 0.2–0.45 Sl. Bear; 0–0.2 Bearish; <0 Sl. Bear |
| **Donchian(20)** | position in channel | new 20d high Bullish; >0.66 Sl. Bull; 0.34–0.66 Neutral; <0.34 Sl. Bear; new 20d low Bearish |
| **Fibonacci** | position in 180d swing | >0.78 Bullish; 0.62–0.78 Sl. Bull; 0.38–0.62 Neutral; 0.22–0.38 Sl. Bear; <0.22 Bearish |
| **Regression Channel** | OLS of price on time, 120d; slope %/yr + channel z | slope>+5% Bullish (Sl. Bull if z>1.5); >+1% Sl. Bull; <−5% Bearish (Sl. Bear if z<−1.5); <−1% Sl. Bear; else Neutral |

**Aggregation:** Bullish % = share in {Bullish, Slightly Bullish}; Bearish %
likewise; Neutral % the remainder. **Institutional score** = `(mean_state + 2)/4
× 100` (0–100, 50 = neutral), labelled Strongly Bearish (<25) … Strongly Bullish
(≥75).

## 3. Drivers & Attribution (`drivers.py`)

Multi-factor OLS of daily gold log-returns on driver changes over a 120-day
estimation window, with HC1 (heteroskedasticity-robust) t-stats:

```
Δln(Gold)_t = α + β1·Δ(real yield)_t + β2·Δln(DXY)_t + β3·Δ(breakeven)_t
                + β4·Δln(VIX)_t + β5·Δln(SPX)_t + ε_t
```

Yields enter as percentage-point changes; index/equity factors as log-returns.
**Attribution** of the trailing 21-day move: `contribution_i = β_i · Σ Δdriver_i`
(in bps). `explained = Σ contributions`; `residual = actual − explained`
(idiosyncratic). Rolling **90-day correlations** are reported per driver. Only
drivers present in the dataset are included.

## 4. Regime & Change (`regime.py`)

- **Volatility regime** from the percentile of the current 20-day realized vol
  within the trailing ~2 years: <25 Low, 25–60 Normal, 60–85 Elevated, ≥85 High.
- **Trend regime** from price/50/200 MA configuration.
- **Correlation regime / decoupling:** 60-day vs. 1-year gold↔real-yield
  correlation; *decoupled* when the 1-year link is strongly inverse (<−0.3) but
  the 60-day link has weakened (>−0.15).
- **Change points** (explainable): 50/200 MA golden/death cross within 1y; a
  CUSUM break in mean return (flagged when the drift shift exceeds ~6%/yr); and
  52-week breakouts/breakdowns.

## 5. Levels (`levels.py`)

Candidate levels from independent methods — swing highs/lows (local extrema,
order 8), classic pivots (P, R1/2, S1/2 from the last 21 days), 50/100/200 MAs,
Fibonacci retracements (23.6/38.2/50/61.8/78.6% of the dominant 180-day swing),
psychological round numbers, and ±1σ/±2σ one-month volatility bands. Levels
within 0.4% are **clustered** (labels merged) and ranked by distance from spot.

## 6. Distribution & Range (`distribution.py`)

- **GARCH(1,1)** (`arch`) fit on returns ×100 produces a forward daily-vol term
  structure over 63 days (realized-vol fallback if the fit fails).
- **Monte Carlo** blends three generators (6,000 paths each = 18,000) using a
  fixed seed: Gaussian GBM and Student-t(5) (both scaled by the GARCH vol path),
  and a historical bootstrap of the last 500 returns (recentred to the model
  drift). Drift is a damped historical mean, `μ = clip(0.25·mean(r₂₅₂), ±0.0004)`
  — ranges are volatility-dominated, not a directional bet.
- **Per horizon** (1W/1M/3M): median, expected band (25–75th pct), tail band
  (5–95th pct), `P(terminal > spot)`, horizon annualized σ, and **first-passage
  touch probabilities** for the nearest round numbers.

## 7. Outlook (`outlook.py`)

For each horizon (1W/1M/3M):

- **Direction score** ∈ [−1,1] = weighted blend of technical **momentum**
  (consensus score), medium-term **trend** (trailing return normalised by horizon
  vol) and the **distribution tilt** (MC median vs. spot). Mapped to the 5-state
  direction (>0.5 Bullish; >0.15 Neutral-Bullish; ±0.15 Neutral; ≥−0.5
  Neutral-Bearish; else Bearish).
- **Target price** = conviction-weighted central estimate
  `spot · exp(score · 0.5 · σ_horizon)`, **bounded inside** the MC expected band —
  so direction and target are always sign-coherent.
- **Expected range** = MC 25–75% band; **P(above spot)** from the MC distribution.
- **Confidence** from model R², indicator agreement and the inverse vol
  percentile, scaled to 25–92% and tapered for longer horizons.
- **Key driver** from the attribution engine; **invalidation** from the risk
  engine (support break if constructive, resistance break if bearish).

These are **model central estimates and probabilistic ranges with explicit
invalidation — research outputs, not trade recommendations.**

## 8. Risk (`risk.py`)

- **VaR/CVaR** historical (non-parametric) on the trailing ~500 daily returns at
  95%/99%; the 1-month VaR scales the 1-day figure by `√21` (iid assumption).
- **Max drawdown** over the trailing year.
- **Invalidation levels:** nearest clean structural references (50/200 MA, 3-month
  swing) below (bull) and above (bear) spot.
- **Triggers:** real-yield spike, dollar breakout, volatility regime, positioning
  crowding (CFTC managed-money percentile), real-yield decoupling.

## 9. News (`news.py` + `narrative/claude.py`)

A curated **macro lexicon** maps gold-transmission phrases to signed weights;
each headline is scored, classified (Bullish/Neutral/Bearish *for gold*) and
given a templated "what it means" via the matched channels (real yields, USD,
Fed policy, safe-haven, flows). The **Macro Score** (−100…+100) is a
recency-weighted (5-day decay) average of item impacts. When enabled, the Claude
layer rewrites the per-item explanation and classification **strictly from the
headline text** and the same aggregation is applied; provenance is recorded
(`claude` vs `lexicon`).

## Narrative grounding

The Claude narrative layer receives only the **pre-computed metrics** (see
`narrative/claude.py::snapshot_metrics`) and is instructed to narrate those
numbers exactly, invent nothing, and make no recommendations. Any failure (no
key, API error, refusal, malformed JSON) falls back to the deterministic
templates, which are auditable line-by-line.
