"""Theme-level aggregation.

Given per-ticker metrics and the wikilink theme index, computes:
  - average / median momentum per theme
  - top & bottom performers in each theme
  - theme rotation score (1-week change in median 3m return)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = REPO_ROOT / "data"
DAILY_DIR = DATA_ROOT / "daily"


def load_theme_index() -> dict:
    p = DATA_ROOT / "theme_index.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def load_companies() -> dict:
    p = DATA_ROOT / "companies.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def aggregate_themes(
    metrics_df: pd.DataFrame,
    theme_index: dict,
    min_constituents: int = 3,
    top_n: int = 5,
    type_filter: tuple[str, ...] | None = ("technology", "other", "tw_company"),
    prior_themes_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Roll up per-ticker metrics to per-theme stats.

    A theme is included only if it has at least ``min_constituents`` covered
    tickers and its type is in ``type_filter``.

    If ``prior_themes_df`` is given (a snapshot from N days ago), a
    ``rotation_score`` column is added: ``median_ret_1w(today) - median_ret_1w(prior)``.
    """
    metrics_indexed = metrics_df.set_index("ticker")
    prior_idx = None
    if prior_themes_df is not None and not prior_themes_df.empty:
        prior_idx = prior_themes_df.set_index("theme")
    rows = []
    for theme, info in theme_index.items():
        if type_filter and info["type"] not in type_filter:
            continue
        tickers = [t for t in info["tickers"] if t in metrics_indexed.index]
        if len(tickers) < min_constituents:
            continue
        sub = metrics_indexed.loc[tickers]

        rotation = None
        if prior_idx is not None and theme in prior_idx.index:
            prior_med_1w = prior_idx.loc[theme, "median_ret_1w"]
            cur_med_1w = _med(sub["ret_1w"])
            if pd.notna(prior_med_1w) and cur_med_1w is not None:
                rotation = float(cur_med_1w - prior_med_1w)

        row = {
            "theme": theme,
            "type": info["type"],
            "tw_ticker": info.get("tw_ticker"),
            "n_total": info["ticker_count"],
            "n_with_price": len(tickers),
            "median_ret_1w": _med(sub["ret_1w"]),
            "median_ret_1m": _med(sub["ret_1m"]),
            "median_ret_3m": _med(sub["ret_3m"]),
            "mean_rs_rating": _mean(sub["rs_rating"]),
            "pct_new_high_60d": _pct_true(sub["new_high_60d"]),
            "pct_above_bench_3m": _pct_pos(sub["rs_vs_bench_3m"]),
            "rotation_score": rotation,
            "top_performers": _top_performers(sub, top_n),
            "bottom_performers": _bottom_performers(sub, top_n),
        }
        rows.append(row)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values("median_ret_1m", ascending=False, na_position="last").reset_index(drop=True)


def _med(series: pd.Series) -> float | None:
    s = pd.to_numeric(series, errors="coerce").dropna()
    return float(s.median()) if not s.empty else None


def _mean(series: pd.Series) -> float | None:
    s = pd.to_numeric(series, errors="coerce").dropna()
    return float(s.mean()) if not s.empty else None


def _pct_true(series: pd.Series) -> float | None:
    s = series.dropna()
    return float(s.astype(bool).mean()) if not s.empty else None


def _pct_pos(series: pd.Series) -> float | None:
    s = pd.to_numeric(series, errors="coerce").dropna()
    return float((s > 0).mean()) if not s.empty else None


def _top_performers(sub: pd.DataFrame, n: int) -> list[dict]:
    s = sub[["ret_1m"]].dropna().sort_values("ret_1m", ascending=False).head(n)
    return [{"ticker": t, "ret_1m": float(r)} for t, r in zip(s.index, s["ret_1m"])]


def _bottom_performers(sub: pd.DataFrame, n: int) -> list[dict]:
    s = sub[["ret_1m"]].dropna().sort_values("ret_1m", ascending=True).head(n)
    return [{"ticker": t, "ret_1m": float(r)} for t, r in zip(s.index, s["ret_1m"])]


def save_daily_snapshot(metrics_df: pd.DataFrame, themes_df: pd.DataFrame,
                        date_str: str) -> Path:
    out_dir = DAILY_DIR / date_str
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics_df.to_csv(out_dir / "ticker_momentum.csv", index=False)
    themes_df.to_json(out_dir / "themes_ranking.json",
                      orient="records", force_ascii=False, indent=2)
    return out_dir


def load_latest_snapshot() -> tuple[pd.DataFrame, pd.DataFrame, str] | None:
    if not DAILY_DIR.exists():
        return None
    dates = sorted(p.name for p in DAILY_DIR.iterdir() if p.is_dir())
    if not dates:
        return None
    latest = dates[-1]
    d = DAILY_DIR / latest
    metrics = pd.read_csv(d / "ticker_momentum.csv")
    themes = pd.read_json(d / "themes_ranking.json")
    return metrics, themes, latest


def load_snapshot_n_back(n_business_days: int) -> pd.DataFrame | None:
    """Return the themes DataFrame from the snapshot ~``n_business_days`` ago.

    Returns ``None`` if not enough history exists. Picks the snapshot whose
    date is the largest one strictly older than today by at least N b-days.
    """
    if not DAILY_DIR.exists():
        return None
    dates = sorted(p.name for p in DAILY_DIR.iterdir() if p.is_dir())
    if len(dates) < n_business_days + 1:
        return None
    target = dates[-(n_business_days + 1)]
    p = DAILY_DIR / target / "themes_ranking.json"
    if not p.exists():
        return None
    return pd.read_json(p)
