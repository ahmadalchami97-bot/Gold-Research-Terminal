"""Institutional Plotly chart builders with one shared visual style."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from app.ui.theme import PALETTE, STATE_COLORS

FONT = "Inter, Segoe UI, sans-serif"


def style(fig: go.Figure, height: int = 360, legend: bool = True,
          margin: dict | None = None) -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=PALETTE["panel"],
        font=dict(family=FONT, color=PALETTE["text"], size=12),
        margin=margin or dict(l=10, r=10, t=30, b=10),
        showlegend=legend,
        legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", yanchor="bottom",
                    y=1.0, x=0, font=dict(size=11)),
        hoverlabel=dict(bgcolor=PALETTE["panel2"], font_size=12,
                        bordercolor=PALETTE["border"]),
    )
    fig.update_xaxes(gridcolor=PALETTE["grid"], zeroline=False,
                     linecolor=PALETTE["border"], showspikes=False)
    fig.update_yaxes(gridcolor=PALETTE["grid"], zeroline=False,
                     linecolor=PALETTE["border"])
    return fig


def price_chart(prices: pd.DataFrame, levels=None, bars: int = 320,
                show_ma=(50, 200), title: str = "") -> go.Figure:
    df = prices.iloc[-bars:]
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"], low=df["low"],
        close=df["close"], name="Gold",
        increasing_line_color=PALETTE["bull"], decreasing_line_color=PALETTE["bear"],
        increasing_fillcolor=PALETTE["bull"], decreasing_fillcolor=PALETTE["bear"]))
    for w, color in zip(show_ma, (PALETTE["gold"], PALETTE["blue"])):
        if len(prices) >= w:
            ma = prices["close"].rolling(w).mean().iloc[-bars:]
            fig.add_trace(go.Scatter(x=df.index, y=ma, name=f"{w}DMA",
                                     line=dict(color=color, width=1.3)))
    for lv in (levels or []):
        dash = "dot" if lv.kind in ("ma", "fib", "band") else "dash"
        color = PALETTE["bear_soft"] if lv.kind == "resistance" or lv.price >= df["close"].iloc[-1] else PALETTE["bull_soft"]
        fig.add_hline(y=lv.price, line=dict(color=color, width=1, dash=dash),
                      annotation_text=lv.label, annotation_position="right",
                      annotation_font_size=9, annotation_font_color=PALETTE["muted"])
    fig.update_layout(title=title, xaxis_rangeslider_visible=False)
    return style(fig, height=460)


def fan_chart(spot: float, horizons) -> go.Figure:
    xs = [0] + [h.days for h in horizons]
    med = [spot] + [h.median for h in horizons]
    lo25 = [spot] + [h.expected_low for h in horizons]
    hi75 = [spot] + [h.expected_high for h in horizons]
    lo5 = [spot] + [h.wide_low for h in horizons]
    hi95 = [spot] + [h.wide_high for h in horizons]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=hi95, line=dict(width=0), showlegend=False,
                             hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=xs, y=lo5, fill="tonexty", line=dict(width=0),
                             fillcolor="rgba(200,161,90,0.12)", name="5–95%"))
    fig.add_trace(go.Scatter(x=xs, y=hi75, line=dict(width=0), showlegend=False,
                             hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=xs, y=lo25, fill="tonexty", line=dict(width=0),
                             fillcolor="rgba(200,161,90,0.28)", name="25–75%"))
    fig.add_trace(go.Scatter(x=xs, y=med, line=dict(color=PALETTE["gold"], width=2.4),
                             name="Median path"))
    fig.add_hline(y=spot, line=dict(color=PALETTE["muted"], width=1, dash="dot"))
    fig.update_xaxes(title="Trading days ahead")
    fig.update_yaxes(title="Price (USD/oz)")
    return style(fig, height=380)


def distribution_hist(samples, spot, median, lo, hi) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=samples, nbinsx=60, marker_color=PALETTE["gold"],
                               opacity=0.78, name="Terminal price"))
    for val, color, label in [(spot, PALETTE["muted"], "Spot"),
                              (median, PALETTE["gold_soft"], "Median"),
                              (lo, PALETTE["bear_soft"], "25%"),
                              (hi, PALETTE["bull_soft"], "75%")]:
        fig.add_vline(x=val, line=dict(color=color, width=1.4, dash="dash"),
                      annotation_text=label, annotation_font_size=9,
                      annotation_font_color=color)
    fig.update_xaxes(title="Price (USD/oz)")
    fig.update_yaxes(title="Frequency")
    return style(fig, height=340, legend=False)


def corr_heatmap(rolling: dict, dates: list, max_cols: int = 44) -> go.Figure:
    drivers = list(rolling.keys())
    n = len(dates)
    step = max(1, n // max_cols)
    idx = list(range(0, n, step))
    x = [dates[i] for i in idx]
    z = [[rolling[d][i] for i in idx] for d in drivers]
    fig = go.Figure(go.Heatmap(
        z=z, x=x, y=drivers, zmin=-1, zmax=1,
        colorscale=[[0, PALETTE["bear"]], [0.5, PALETTE["panel2"]], [1, PALETTE["bull"]]],
        colorbar=dict(title="ρ", thickness=12)))
    return style(fig, height=300, legend=False)


def rolling_corr_lines(rolling: dict, dates: list) -> go.Figure:
    palette = [PALETTE["gold"], PALETTE["blue"], PALETTE["bull"], PALETTE["bear"], PALETTE["gold_soft"]]
    fig = go.Figure()
    for i, (driver, vals) in enumerate(rolling.items()):
        fig.add_trace(go.Scatter(x=dates, y=vals, name=driver,
                                 line=dict(color=palette[i % len(palette)], width=1.5)))
    fig.add_hline(y=0, line=dict(color=PALETTE["muted"], width=1, dash="dot"))
    fig.update_yaxes(title="90-day correlation", range=[-1, 1])
    return style(fig, height=320)


def attribution_bar(betas) -> go.Figure:
    betas = sorted(betas, key=lambda b: b.contribution_bps)
    labels = [b.label for b in betas]
    vals = [b.contribution_bps for b in betas]
    colors = [PALETTE["bull"] if v >= 0 else PALETTE["bear"] for v in vals]
    fig = go.Figure(go.Bar(x=vals, y=labels, orientation="h", marker_color=colors,
                           text=[f"{v:+.0f}" for v in vals], textposition="auto"))
    fig.update_xaxes(title="Contribution to trailing move (bps)")
    return style(fig, height=300, legend=False)


def consensus_pie(bullish_pct, neutral_pct, bearish_pct) -> go.Figure:
    fig = go.Figure(go.Pie(
        labels=["Bullish", "Neutral", "Bearish"],
        values=[bullish_pct, neutral_pct, bearish_pct], hole=0.58,
        marker_colors=[PALETTE["bull"], PALETTE["neutral"], PALETTE["bear"]],
        textinfo="label+percent", sort=False))
    return style(fig, height=300, legend=False, margin=dict(l=10, r=10, t=20, b=10))


def consensus_bar(readings) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=[r.name for r in readings], y=[r.score for r in readings],
        marker_color=[STATE_COLORS.get(r.state.value, PALETTE["neutral"]) for r in readings],
        text=[r.state.value for r in readings], textposition="none"))
    fig.update_yaxes(title="Score", range=[-2.4, 2.4],
                     tickvals=[-2, -1, 0, 1, 2])
    fig.update_xaxes(tickangle=-40)
    return style(fig, height=320, legend=False)


def gauge(value, title, vmin=0, vmax=100, suffix="") -> go.Figure:
    span = vmax - vmin
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value, number=dict(suffix=suffix, font=dict(size=26)),
        title=dict(text=title, font=dict(size=13, color=PALETTE["muted"])),
        gauge=dict(
            axis=dict(range=[vmin, vmax], tickcolor=PALETTE["muted"]),
            bar=dict(color=PALETTE["gold"], thickness=0.25),
            bordercolor=PALETTE["border"], borderwidth=1,
            steps=[
                dict(range=[vmin, vmin + span * 0.4], color="rgba(224,86,78,0.30)"),
                dict(range=[vmin + span * 0.4, vmin + span * 0.6], color="rgba(154,163,178,0.25)"),
                dict(range=[vmin + span * 0.6, vmax], color="rgba(47,182,122,0.30)"),
            ])))
    return style(fig, height=260, legend=False, margin=dict(l=20, r=20, t=40, b=10))


def vol_cone(cone: dict) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cone["days"], y=cone["annualized_vol"],
                             line=dict(color=PALETTE["gold"], width=2),
                             name="GARCH forward vol"))
    fig.add_trace(go.Scatter(x=cone["days"], y=cone["realized_ref"],
                             line=dict(color=PALETTE["muted"], width=1.4, dash="dash"),
                             name="Realized (60d)"))
    fig.update_xaxes(title="Trading days ahead")
    fig.update_yaxes(title="Annualized volatility (%)")
    return style(fig, height=300)
