"""Theme relationship network: visualize which themes share constituents."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.lib import load_theme_index  # noqa: E402
from momentum.relations import neighborhood_edges, related_themes  # noqa: E402

st.set_page_config(page_title="題材網路圖", page_icon="🕸️", layout="wide")
st.title("🕸️ 題材關聯網路圖")
st.caption("以 Jaccard 相似度衡量題材間的成分股重疊 — 看出哪些題材其實共享同一批公司")

theme_index = load_theme_index()
themes = sorted(theme_index)
default = "CoWoS" if "CoWoS" in themes else themes[0]

col_l, col_r = st.columns([1, 4])
with col_l:
    target = st.selectbox("中心題材", options=themes,
                          index=themes.index(default))
    top_k = st.slider("顯示鄰居數", 5, 30, 12)
    min_overlap = st.slider("最少共同股數", 2, 20, 3)

# Compute graph
nodes, edges = neighborhood_edges(target, theme_index,
                                  top_k=top_k, min_overlap=min_overlap)

if not nodes or len(nodes) < 2:
    st.warning(f"題材「{target}」沒有足夠的關聯題材 (門檻 ≥{min_overlap} 共同股)。試著降低門檻。")
    st.stop()

# Layout: place target at centre, neighbours on a circle
center_x, center_y = 0.0, 0.0
others = [n for n in nodes if not n["is_target"]]
n_others = len(others)
positions: dict[str, tuple[float, float]] = {target: (center_x, center_y)}
for i, n in enumerate(others):
    angle = 2 * math.pi * i / n_others
    positions[n["id"]] = (math.cos(angle), math.sin(angle))

TYPE_COLOR = {"technology": "#1f77b4", "other": "#9467bd",
              "tw_company": "#2ca02c"}

# Edges
edge_traces = []
max_w = max((e["weight"] for e in edges), default=1)
for e in edges:
    x0, y0 = positions[e["source"]]
    x1, y1 = positions[e["target"]]
    width = 0.5 + 4 * (e["weight"] / max_w)
    edge_traces.append(go.Scatter(
        x=[x0, x1, None], y=[y0, y1, None],
        mode="lines", line=dict(width=width, color="rgba(140,140,140,0.45)"),
        hoverinfo="skip", showlegend=False,
    ))

# Nodes
node_x = [positions[n["id"]][0] for n in nodes]
node_y = [positions[n["id"]][1] for n in nodes]
node_sizes = [25 + 25 * (1 if n["is_target"] else 0)
              + 0.05 * n["size"] for n in nodes]
node_colors = ["#d62728" if n["is_target"] else TYPE_COLOR.get(n["type"], "#777")
               for n in nodes]
node_text = [f"{n['id']}<br>類型: {n['type']}<br>成分股: {n['size']}" for n in nodes]

node_trace = go.Scatter(
    x=node_x, y=node_y, mode="markers+text",
    text=[n["id"] for n in nodes], textposition="top center",
    textfont=dict(size=12),
    marker=dict(size=node_sizes, color=node_colors,
                line=dict(width=1, color="#222")),
    hovertext=node_text, hoverinfo="text", showlegend=False,
)

fig = go.Figure(data=[*edge_traces, node_trace])
fig.update_layout(
    height=600, margin=dict(l=10, r=10, t=10, b=10),
    xaxis=dict(visible=False, range=[-1.5, 1.5]),
    yaxis=dict(visible=False, range=[-1.5, 1.5]),
    plot_bgcolor="white",
)
with col_r:
    st.plotly_chart(fig, width="stretch")

# Related themes table
st.subheader(f"與 [[{target}]] 最相關的題材")
rel = related_themes(target, theme_index, top_k=20, min_overlap=2)
if rel:
    import pandas as pd
    rel_df = pd.DataFrame([{
        "相關題材": r["theme"],
        "類型": r["type"],
        "Jaccard": round(r["jaccard"], 3),
        "共同成分股": r["overlap"],
        "共同 ticker (前 8)": ", ".join(r["shared"][:8]),
    } for r in rel])
    st.dataframe(rel_df, hide_index=True, width="stretch")
