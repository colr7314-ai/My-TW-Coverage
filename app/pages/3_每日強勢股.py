"""Market-wide movers: top gainers, breakouts, volume surges."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.lib import format_pct, load_companies, load_snapshot  # noqa: E402

st.set_page_config(page_title="每日強勢股", page_icon="🚀", layout="wide")
st.title("🚀 每日強勢股")

snap = load_snapshot()
if snap is None:
    st.warning("尚無動能快照。")
    st.stop()
metrics_df, _, snapshot_date = snap
st.caption(f"快照日期: {snapshot_date}")

companies = load_companies()
df = metrics_df.copy()
df["company"] = df["ticker"].map(lambda t: companies.get(t, {}).get("name", ""))
df["sector"] = df["ticker"].map(lambda t: companies.get(t, {}).get("sector", ""))

filter_col, _ = st.columns([1, 3])
with filter_col:
    sectors = ["全部"] + sorted({s for s in df["sector"].unique() if s})
    sector_sel = st.selectbox("產業篩選", sectors)
    min_rs = st.slider("最低 RS Rating", 0, 99, 80)
    min_close = st.number_input("最低股價 (排除水餃股)", value=10.0, step=5.0)

view = df[df["rs_rating"] >= min_rs]
view = view[view["last_close"] >= min_close]
if sector_sel != "全部":
    view = view[view["sector"] == sector_sel]


def show(df, sort_col: str, ascending: bool = False, n: int = 30):
    s = df.sort_values(sort_col, ascending=ascending, na_position="last").head(n)
    out = pd.DataFrame({
        "代號": s["ticker"],
        "公司": s["company"],
        "產業": s["sector"],
        "收盤": s["last_close"].round(2),
        "1W": s["ret_1w"].apply(format_pct),
        "1M": s["ret_1m"].apply(format_pct),
        "3M": s["ret_3m"].apply(format_pct),
        "RS": s["rs_rating"].round(0).astype("Int64"),
        "量比": s["vol_surge"].round(2),
        "60日新高": s["new_high_60d"].map({True: "✓", False: ""}),
    })
    st.dataframe(out, hide_index=True, width="stretch", height=500)


tabs = st.tabs(["🔥 RS 領先股", "📈 1 週強勢", "📊 爆量股", "🚀 創 60 日新高"])

with tabs[0]:
    show(view, "rs_rating")
with tabs[1]:
    show(view, "ret_1w")
with tabs[2]:
    show(view, "vol_surge")
with tabs[3]:
    show(view[view["new_high_60d"]], "ret_1m")
