"""Price fetcher.

Pulls daily OHLCV via yfinance. Each TW listing is tried as both ``.TW``
(TWSE) and ``.TWO`` (TPEx/OTC); whichever returns data wins. Results are
cached as CSV under ``data/prices/`` keyed by the bare 4-5 digit ticker.

This module is designed for production (GitHub Actions). Local-machine
sandboxes that block egress should use ``momentum.mock_prices`` instead.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = REPO_ROOT / "data"
PRICE_DIR = DATA_ROOT / "prices"
BENCHMARK_SYMBOL = "^TWII"  # TAIEX weighted index
BENCHMARK_FILE = PRICE_DIR / "_TWII.csv"

OHLCV_COLS = ["Open", "High", "Low", "Close", "Volume"]


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    keep = [c for c in OHLCV_COLS if c in df.columns]
    df = df[keep].dropna(how="all")
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.index.name = "Date"
    return df


def fetch_one(ticker: str, period: str = "1y") -> tuple[pd.DataFrame, str] | tuple[None, None]:
    """Return ``(df, symbol)`` if either ``.TW`` or ``.TWO`` resolves."""
    import yfinance as yf  # imported lazily — sandboxes may not have it

    for suffix in ("TW", "TWO"):
        sym = f"{ticker}.{suffix}"
        try:
            df = yf.download(
                sym,
                period=period,
                auto_adjust=True,
                progress=False,
                threads=False,
            )
        except Exception:
            df = pd.DataFrame()
        if df is not None and not df.empty:
            return _normalize(df), sym
    return None, None


def _cache_path(ticker: str) -> Path:
    return PRICE_DIR / f"{ticker}.csv"


def load_cached(ticker: str) -> pd.DataFrame | None:
    path = _cache_path(ticker)
    if not path.exists():
        return None
    df = pd.read_csv(path, index_col="Date", parse_dates=["Date"])
    return df if not df.empty else None


def save_cache(ticker: str, df: pd.DataFrame) -> None:
    PRICE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(_cache_path(ticker))


def fetch_and_cache(
    tickers: Iterable[str],
    period: str = "1y",
    sleep_s: float = 0.1,
    progress_every: int = 50,
) -> dict:
    """Download every ticker and write CSVs. Returns summary stats."""
    PRICE_DIR.mkdir(parents=True, exist_ok=True)
    tickers = list(tickers)
    ok, failed = 0, []
    for i, t in enumerate(tickers, 1):
        df, sym = fetch_one(t, period=period)
        if df is None:
            failed.append(t)
        else:
            save_cache(t, df)
            ok += 1
        if sleep_s:
            time.sleep(sleep_s)
        if progress_every and i % progress_every == 0:
            print(f"  [{i}/{len(tickers)}] ok={ok} fail={len(failed)}")
    return {"requested": len(tickers), "ok": ok,
            "failed_count": len(failed), "failed_sample": failed[:25]}


def fetch_benchmark(period: str = "1y") -> pd.DataFrame:
    import yfinance as yf

    df = yf.download(BENCHMARK_SYMBOL, period=period,
                     auto_adjust=True, progress=False, threads=False)
    out = _normalize(df)
    PRICE_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(BENCHMARK_FILE)
    return out


def load_benchmark() -> pd.DataFrame | None:
    if not BENCHMARK_FILE.exists():
        return None
    return pd.read_csv(BENCHMARK_FILE, index_col="Date", parse_dates=["Date"])


def all_cached_tickers() -> list[str]:
    if not PRICE_DIR.exists():
        return []
    return sorted(
        p.stem for p in PRICE_DIR.glob("*.csv")
        if not p.stem.startswith("_")
    )
