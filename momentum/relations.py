"""Theme relationship analysis.

Measures how related themes are by their constituent overlap (Jaccard
similarity). Used to render the theme-network page and the "related
themes" widget on theme detail.
"""
from __future__ import annotations

from collections import defaultdict


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def related_themes(
    target: str,
    theme_index: dict,
    top_k: int = 15,
    min_overlap: int = 2,
) -> list[dict]:
    """Return the ``top_k`` themes most similar to ``target`` by Jaccard."""
    if target not in theme_index:
        return []
    target_tickers = set(theme_index[target]["tickers"])
    if not target_tickers:
        return []

    rows = []
    for theme, info in theme_index.items():
        if theme == target:
            continue
        other = set(info["tickers"])
        overlap = target_tickers & other
        if len(overlap) < min_overlap:
            continue
        rows.append({
            "theme": theme,
            "type": info["type"],
            "overlap": len(overlap),
            "shared": sorted(overlap),
            "jaccard": jaccard(target_tickers, other),
        })
    rows.sort(key=lambda r: (-r["jaccard"], -r["overlap"]))
    return rows[:top_k]


def neighborhood_edges(
    target: str,
    theme_index: dict,
    top_k: int = 10,
    min_overlap: int = 2,
) -> tuple[list[dict], list[dict]]:
    """Return (nodes, edges) for a network-graph view centred on ``target``.

    Includes the target, its top-K related themes, and edges among ALL of
    those themes (so the user sees clusters, not just a star).
    """
    related = related_themes(target, theme_index, top_k=top_k, min_overlap=min_overlap)
    keep = [target] + [r["theme"] for r in related]
    keep_set = set(keep)

    sizes = {t: len(theme_index[t]["tickers"]) for t in keep if t in theme_index}
    nodes = [
        {"id": t, "type": theme_index.get(t, {}).get("type", "other"),
         "size": sizes.get(t, 0), "is_target": t == target}
        for t in keep if t in theme_index
    ]

    edges = []
    seen = set()
    for a in keep:
        if a not in theme_index:
            continue
        ta = set(theme_index[a]["tickers"])
        for b in keep:
            if a == b or b not in theme_index:
                continue
            key = tuple(sorted((a, b)))
            if key in seen:
                continue
            seen.add(key)
            tb = set(theme_index[b]["tickers"])
            ov = ta & tb
            if len(ov) < min_overlap:
                continue
            edges.append({
                "source": key[0], "target": key[1],
                "weight": len(ov), "jaccard": jaccard(ta, tb),
            })
    return nodes, edges
