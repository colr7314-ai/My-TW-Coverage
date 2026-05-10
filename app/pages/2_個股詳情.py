"""Ticker detail: momentum metrics, K-line chart, and the underlying report."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.lib import (  # noqa: E402
    format_pct, load_companies, load_prices, load_report, load_snapshot,
    load_ticker_themes,
)

st.set_page_config(page_title="個股詳情", page_icon="🔍", layout="wide")
st.title("🔍 個股詳情")

snap = load_snapshot()
if snap is None:
    st.warning("尚無動能快照。")
    st.stop()
metrics_df, _, _ = snap

companies = load_companies()
ticker_themes = load_ticker_themes()

options = sorted(companies)
labels = {t: f"{t} - {companies[t]['name']}" for t in options}

ticker = st.selectbox("選擇個股", options=options,
                      format_func=lambda t: labels[t],
                      index=options.index("2330") if "2330" in options else 0)

row = metrics_df[metrics_df["ticker"] == ticker]
if row.empty:
    st.warning("此檔個股無動能資料。")
    st.stop()
r = row.iloc[0]

info = companies.get(ticker, {})
st.subheader(f"{ticker} - {info.get('name', '')}")
st.caption(f"產業: {info.get('sector', '')}")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("收盤", f"{r['last_close']:.2f}" if pd.notna(r["last_close"]) else "—",
          format_pct(r["ret_1w"]))
c2.metric("1 月", format_pct(r["ret_1m"]))
c3.metric("3 月", format_pct(r["ret_3m"]))
c4.metric("RS Rating",
          f"{r['rs_rating']:.0f}" if pd.notna(r["rs_rating"]) else "—",
          help="0-99 percentile vs 全市場")
c5.metric("量比 (5/60)",
          f"{r['vol_surge']:.2f}" if pd.notna(r["vol_surge"]) else "—")

signals = []
if r.get("new_high_20d"):
    signals.append("🟢 20 日新高")
if r.get("new_high_60d"):
    signals.append("🟢 60 日新高")
if r.get("new_high_250d"):
    signals.append("🚀 年線新高")
if r.get("vol_surge") and r["vol_surge"] > 2:
    signals.append("📊 爆量")
if signals:
    st.markdown("**訊號:** " + "  ·  ".join(signals))

st.divider()

# Price chart
px = load_prices(ticker)
if px is not None and not px.empty:
    px = px.tail(180)
    fig = go.Figure(data=[go.Candlestick(
        x=px.index, open=px["Open"], high=px["High"], low=px["Low"], close=px["Close"],
        name=ticker,
    )])
    fig.update_layout(
        height=420, margin=dict(l=10, r=10, t=10, b=10),
        xaxis_rangeslider_visible=False, showlegend=False,
    )
    st.plotly_chart(fig, width="stretch")
else:
    st.info("無價格資料。")

# Themes this ticker belongs to
st.subheader("所屬題材")
themes = ticker_themes.get(ticker, {}).get("themes", [])
if themes:
    cols = st.columns(4)
    for i, t in enumerate(themes):
        cols[i % 4].markdown(f"`{t}`")
else:
    st.caption("此檔無 wikilink 題材標記。")

st.divider()
st.subheader("研究報告")
report = load_report(ticker)
if report:
    st.markdown(report)
else:
    st.caption("找不到對應報告。")
