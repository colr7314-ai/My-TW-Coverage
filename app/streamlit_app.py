"""Theme momentum dashboard — entry page.

Run:  streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.lib import load_snapshot, format_pct, type_color  # noqa: E402

st.set_page_config(
    page_title="台股題材動能",
    page_icon="📈",
    layout="wide",
)

st.title("📈 台股題材動能")
st.caption("整合 1,700+ 份個股深度報告的 wikilink 圖譜,追蹤題材輪動")

snap = load_snapshot()
if snap is None:
    st.warning("尚無動能快照。請先執行 `python -m momentum.cli daily --mock` 或設定 GitHub Actions。")
    st.stop()

metrics_df, themes_df, snapshot_date = snap
st.caption(f"快照日期: **{snapshot_date}** · 個股: {len(metrics_df)} · 題材: {len(themes_df)}")

# Filters
col_l, col_r = st.columns([1, 3])
with col_l:
    type_filter = st.multiselect(
        "題材類型",
        options=["technology", "other", "tw_company"],
        default=["technology", "other"],
        help="technology = 製程/材料/應用 · other = 國際大廠/材料 · tw_company = 覆蓋範圍內台股",
    )
    min_n = st.slider("最少成分股數", min_value=3, max_value=50, value=5)
    horizon = st.radio("動能期間", options=["1w", "1m", "3m"], index=1, horizontal=True)

ret_col = f"median_ret_{horizon}"
view = themes_df[themes_df["type"].isin(type_filter)].copy()
view = view[view["n_with_price"] >= min_n]
view = view.sort_values(ret_col, ascending=False, na_position="last")

with col_r:
    tab_hot, tab_cold = st.tabs(["🔥 領漲題材", "❄️ 落後題材"])

    def render(df: pd.DataFrame, ascending: bool):
        df = df.copy().sort_values(ret_col, ascending=ascending, na_position="last").head(25)
        df["中位數動能"] = df[ret_col].apply(format_pct)
        df["平均 RS"] = df["mean_rs_rating"].round(1)
        df["創 60 日新高 %"] = (df["pct_new_high_60d"] * 100).round(1)
        df["勝大盤 %"] = (df["pct_above_bench_3m"] * 100).round(1)
        df["週輪動"] = df.get("rotation_score", pd.Series(dtype=float)).apply(format_pct)
        df = df.rename(columns={
            "theme": "題材",
            "type": "類型",
            "n_with_price": "成分股數",
        })
        st.dataframe(
            df[["題材", "類型", "成分股數", "中位數動能", "週輪動", "平均 RS",
                "創 60 日新高 %", "勝大盤 %"]],
            hide_index=True,
            width="stretch",
        )

    with tab_hot:
        render(view, ascending=False)
    with tab_cold:
        render(view, ascending=True)

st.divider()
st.markdown("**側邊欄頁面**:")
st.markdown("- **題材瀏覽**:點任一題材看成分股動能")
st.markdown("- **個股詳情**:單檔個股動能 + K 線 + 所屬題材")
st.markdown("- **每日強勢股**:全市場 movers (按 RS / 1w / 突破訊號)")
