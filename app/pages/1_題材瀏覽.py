"""Theme browser: pick a theme -> see its constituent tickers ranked by momentum."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.lib import (  # noqa: E402
    format_pct, load_companies, load_snapshot, load_theme_index,
)

st.set_page_config(page_title="題材瀏覽", page_icon="🎯", layout="wide")
st.title("🎯 題材瀏覽")

snap = load_snapshot()
if snap is None:
    st.warning("尚無動能快照。")
    st.stop()
metrics_df, themes_df, snapshot_date = snap

theme_index = load_theme_index()
companies = load_companies()

# Build searchable theme list (themes that have constituents with price data)
metrics_idx = metrics_df.set_index("ticker")
available_themes = sorted(themes_df["theme"].tolist())

col_l, col_r = st.columns([1, 3])
with col_l:
    # Use selectbox with searchable default
    selected = st.selectbox(
        "選擇題材",
        options=available_themes,
        index=available_themes.index("CoWoS") if "CoWoS" in available_themes else 0,
    )
with col_r:
    info = theme_index.get(selected, {})
    if info:
        st.markdown(
            f"**類型:** `{info['type']}`  ·  "
            f"**總成分股(含未抓價):** {info['ticker_count']}  ·  "
            f"**有價格資料:** {sum(1 for t in info['tickers'] if t in metrics_idx.index)}"
        )
        if info.get("tw_ticker"):
            st.markdown(f"**對應台股:** [[{selected}]] = {info['tw_ticker']}")

st.divider()

# Stats row from themes_df
theme_row = themes_df[themes_df["theme"] == selected]
if not theme_row.empty:
    r = theme_row.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("中位數 1 月報酬", format_pct(r["median_ret_1m"]))
    c2.metric("中位數 3 月報酬", format_pct(r["median_ret_3m"]))
    c3.metric("平均 RS Rating",
              f"{r['mean_rs_rating']:.1f}" if pd.notna(r["mean_rs_rating"]) else "—")
    c4.metric("創 60 日新高比例",
              f"{r['pct_new_high_60d'] * 100:.0f}%" if pd.notna(r["pct_new_high_60d"]) else "—")

st.subheader("成分股動能排名")
constituents = [t for t in info.get("tickers", []) if t in metrics_idx.index]
sub = metrics_idx.loc[constituents].reset_index()
sub["company"] = sub["ticker"].map(lambda t: companies.get(t, {}).get("name", ""))
sub["sector"] = sub["ticker"].map(lambda t: companies.get(t, {}).get("sector", ""))

sort_col = st.radio("排序依據",
                    options=["rs_rating", "ret_1w", "ret_1m", "ret_3m", "vol_surge"],
                    index=2, horizontal=True)
sub = sub.sort_values(sort_col, ascending=False, na_position="last")

display = pd.DataFrame({
    "代號": sub["ticker"],
    "公司": sub["company"],
    "產業": sub["sector"],
    "收盤": sub["last_close"].round(2),
    "1W": sub["ret_1w"].apply(format_pct),
    "1M": sub["ret_1m"].apply(format_pct),
    "3M": sub["ret_3m"].apply(format_pct),
    "RS": sub["rs_rating"].round(1),
    "量比": sub["vol_surge"].round(2),
    "60日新高": sub["new_high_60d"].map({True: "✓", False: ""}),
})
st.dataframe(display, hide_index=True, width="stretch", height=600)
