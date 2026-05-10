"""Synthetic price generator for local development.

Produces ~1 year of fake OHLCV per ticker so the momentum pipeline, theme
aggregation, and Streamlit UI can be exercised on machines without market
data access (e.g. sandboxed environments). In production these CSVs are
overwritten by ``momentum.prices.fetch_and_cache``.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from .prices import PRICE_DIR, BENCHMARK_FILE, OHLCV_COLS

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = REPO_ROOT / "data"


def _business_days(end: date, n: int) -> pd.DatetimeIndex:
    # pandas 3.x bdate_range under-counts when ``end`` is a weekend; pad and trim.
    idx = pd.bdate_range(end=pd.Timestamp(end), periods=n + 10)
    return idx[-n:]


def _gbm_path(n: int, drift: float, vol: float, start: float, rng: np.random.Generator) -> np.ndarray:
    dt = 1 / 252
    shocks = rng.normal((drift - 0.5 * vol ** 2) * dt, vol * np.sqrt(dt), n)
    return start * np.exp(np.cumsum(shocks))


def _ohlcv_from_close(close: np.ndarray, rng: np.random.Generator,
                     base_vol: float) -> pd.DataFrame:
    daily_vol_pct = rng.uniform(0.005, 0.025, len(close))
    high = close * (1 + daily_vol_pct)
    low = close * (1 - daily_vol_pct)
    open_ = np.r_[close[0], close[:-1]] * (1 + rng.normal(0, 0.005, len(close)))
    volume = (base_vol * rng.lognormal(0, 0.4, len(close))).astype(int)
    return pd.DataFrame({"Open": open_, "High": high, "Low": low,
                         "Close": close, "Volume": volume})


def generate_mock(
    tickers: list[str],
    days: int = 260,
    seed: int = 7,
    theme_drift: dict[str, float] | None = None,
    ticker_themes: dict | None = None,
) -> None:
    """Generate synthetic OHLCV for every ticker plus the TAIEX benchmark.

    If ``theme_drift`` and ``ticker_themes`` are provided, each ticker's drift
    is biased by the average drift of the themes it participates in — so
    "hot" themes will visibly outperform.
    """
    PRICE_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    end = date.today()
    dates = _business_days(end, days)

    # Benchmark
    bench_close = _gbm_path(days, drift=0.06, vol=0.18, start=20000, rng=rng)
    bench_df = _ohlcv_from_close(bench_close, rng, base_vol=1e9)
    bench_df.index = dates
    bench_df.index.name = "Date"
    bench_df.to_csv(BENCHMARK_FILE)

    for t in tickers:
        # Per-ticker base drift
        base_drift = rng.normal(0.05, 0.15)
        if theme_drift and ticker_themes and t in ticker_themes:
            themes = ticker_themes[t].get("themes", [])
            bumps = [theme_drift[th] for th in themes if th in theme_drift]
            if bumps:
                base_drift += float(np.mean(bumps))

        vol = float(np.clip(rng.normal(0.30, 0.10), 0.10, 0.70))
        start_price = float(np.clip(rng.lognormal(4.0, 0.6), 8, 1200))
        close = _gbm_path(days, drift=base_drift, vol=vol, start=start_price, rng=rng)
        df = _ohlcv_from_close(close, rng, base_vol=rng.uniform(5e5, 5e7))
        df.index = dates
        df.index.name = "Date"
        df.to_csv(PRICE_DIR / f"{t}.csv")


def default_theme_drift(theme_index: dict, seed: int = 7) -> dict[str, float]:
    """Assign a 'hot/cold' drift to each theme so the mock data has structure."""
    rng = np.random.default_rng(seed)
    # Pick a handful to be 'hot' (positive drift), some 'cold' (negative)
    themes = list(theme_index)
    hot = set(rng.choice(themes, size=min(40, len(themes) // 20 + 5), replace=False))
    cold = set(rng.choice([t for t in themes if t not in hot],
                          size=min(20, len(themes) // 50 + 3), replace=False))
    out = {}
    for t in themes:
        if t in hot:
            out[t] = rng.uniform(0.15, 0.45)
        elif t in cold:
            out[t] = rng.uniform(-0.30, -0.10)
        else:
            out[t] = rng.normal(0, 0.05)
    return out


if __name__ == "__main__":
    companies = json.loads((DATA_ROOT / "companies.json").read_text(encoding="utf-8"))
    theme_index = json.loads((DATA_ROOT / "theme_index.json").read_text(encoding="utf-8"))
    ticker_themes = json.loads((DATA_ROOT / "ticker_themes.json").read_text(encoding="utf-8"))
    tickers = list(companies)
    drift = default_theme_drift(theme_index)
    generate_mock(tickers, theme_drift=drift, ticker_themes=ticker_themes)
    print(f"Generated mock OHLCV for {len(tickers)} tickers + benchmark.")
