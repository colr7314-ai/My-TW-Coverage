"""Momentum metrics.

Pure pandas/numpy. Given a price DataFrame (Date index, OHLCV columns),
produces a row of momentum metrics. Used both per-ticker and aggregated
to per-theme.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Mapping

import numpy as np
import pandas as pd

# Trading days lookback windows
LOOKBACK = {"1w": 5, "1m": 21, "3m": 63, "6m": 126, "12m": 252}


@dataclass
class Metrics:
    ticker: str
    last_close: float | None
    last_date: str | None
    ret_1w: float | None
    ret_1m: float | None
    ret_3m: float | None
    ret_6m: float | None
    ret_12m: float | None
    rs_rating: float | None         # 0-99 percentile vs universe
    rs_vs_bench_3m: float | None    # ticker 3m return - benchmark 3m return
    vol_surge: float | None         # 5-day avg vol / 60-day avg vol
    near_high_pct: float | None     # last close / 250-day high
    new_high_20d: bool
    new_high_60d: bool
    new_high_250d: bool


def _pct_change_n(close: pd.Series, n: int) -> float | None:
    if len(close) <= n:
        return None
    prev = close.iloc[-(n + 1)]
    last = close.iloc[-1]
    if not np.isfinite(prev) or prev == 0:
        return None
    return float(last / prev - 1.0)


def _rolling_high(close: pd.Series, n: int) -> bool:
    if len(close) < n:
        return False
    window = close.iloc[-n:]
    return bool(window.iloc[-1] >= window.max())


def compute_metrics(
    ticker: str,
    df: pd.DataFrame,
    bench: pd.DataFrame | None = None,
) -> Metrics:
    """Compute metrics for a single ticker. ``df`` must have a Close column."""
    close = df["Close"].dropna()
    if close.empty:
        return Metrics(ticker, None, None,
                       None, None, None, None, None,
                       None, None, None, None,
                       False, False, False)

    last_close = float(close.iloc[-1])
    last_date = close.index[-1].strftime("%Y-%m-%d")

    rets = {k: _pct_change_n(close, n) for k, n in LOOKBACK.items()}

    rs_vs_bench = None
    if bench is not None and "Close" in bench.columns:
        bench_close = bench["Close"].dropna()
        b_3m = _pct_change_n(bench_close, LOOKBACK["3m"])
        if b_3m is not None and rets["3m"] is not None:
            rs_vs_bench = rets["3m"] - b_3m

    vol = df["Volume"].dropna() if "Volume" in df else pd.Series(dtype=float)
    vol_surge = None
    if len(vol) >= 60:
        recent = vol.iloc[-5:].mean()
        base = vol.iloc[-60:].mean()
        if base > 0:
            vol_surge = float(recent / base)

    near_high_pct = None
    if len(close) >= 60:
        h = close.iloc[-min(252, len(close)):].max()
        if h > 0:
            near_high_pct = float(last_close / h)

    return Metrics(
        ticker=ticker,
        last_close=last_close,
        last_date=last_date,
        ret_1w=rets["1w"],
        ret_1m=rets["1m"],
        ret_3m=rets["3m"],
        ret_6m=rets["6m"],
        ret_12m=rets["12m"],
        rs_rating=None,  # filled later by populate_rs_rating
        rs_vs_bench_3m=rs_vs_bench,
        vol_surge=vol_surge,
        near_high_pct=near_high_pct,
        new_high_20d=_rolling_high(close, 20),
        new_high_60d=_rolling_high(close, 60),
        new_high_250d=_rolling_high(close, 250),
    )


def populate_rs_rating(metrics: list[Metrics]) -> list[Metrics]:
    """IBD-style RS rating: blended return percentile vs the cross-section.

    Weight: 2*(3m) + 1*(6m) + 1*(12m), missing components are dropped.
    Output is integer 1-99 per ticker.
    """
    rows = []
    for m in metrics:
        score_parts = []
        if m.ret_3m is not None:
            score_parts.append(2 * m.ret_3m)
        if m.ret_6m is not None:
            score_parts.append(m.ret_6m)
        if m.ret_12m is not None:
            score_parts.append(m.ret_12m)
        score = sum(score_parts) if score_parts else None
        rows.append(score)

    series = pd.Series(rows, dtype=float)
    ranks = series.rank(pct=True) * 99
    for m, r in zip(metrics, ranks):
        if pd.notna(r):
            m.rs_rating = round(float(r), 1)
    return metrics


def metrics_to_dataframe(metrics: list[Metrics]) -> pd.DataFrame:
    return pd.DataFrame([asdict(m) for m in metrics])
