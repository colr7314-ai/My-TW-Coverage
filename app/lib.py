"""Shared helpers for the Streamlit app."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = REPO_ROOT / "data"
DAILY_DIR = DATA_ROOT / "daily"
PRICE_DIR = DATA_ROOT / "prices"
REPORTS_ROOT = REPO_ROOT / "Pilot_Reports"

TYPE_COLOR = {
    "technology": "#1f77b4",
    "other": "#9467bd",
    "tw_company": "#2ca02c",
}


@st.cache_data(show_spinner=False)
def load_snapshot() -> tuple[pd.DataFrame, pd.DataFrame, str] | None:
    if not DAILY_DIR.exists():
        return None
    dates = sorted(p.name for p in DAILY_DIR.iterdir() if p.is_dir())
    if not dates:
        return None
    latest = dates[-1]
    d = DAILY_DIR / latest
    metrics = pd.read_csv(d / "ticker_momentum.csv", dtype={"ticker": str})
    themes = pd.read_json(d / "themes_ranking.json")
    return metrics, themes, latest


@st.cache_data(show_spinner=False)
def load_theme_index() -> dict:
    p = DATA_ROOT / "theme_index.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


@st.cache_data(show_spinner=False)
def load_ticker_themes() -> dict:
    p = DATA_ROOT / "ticker_themes.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


@st.cache_data(show_spinner=False)
def load_companies() -> dict:
    p = DATA_ROOT / "companies.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


@st.cache_data(show_spinner=False)
def load_prices(ticker: str) -> pd.DataFrame | None:
    p = PRICE_DIR / f"{ticker}.csv"
    if not p.exists():
        return None
    return pd.read_csv(p, index_col="Date", parse_dates=["Date"])


@st.cache_data(show_spinner=False)
def load_report(ticker: str) -> str | None:
    companies = load_companies()
    info = companies.get(ticker)
    if not info:
        return None
    p = REPORTS_ROOT / info["sector"] / f"{ticker}_{info['name']}.md"
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8")


def format_pct(x) -> str:
    if x is None or pd.isna(x):
        return "—"
    return f"{x * 100:+.2f}%"


def type_color(t: str) -> str:
    return TYPE_COLOR.get(t, "#777")
