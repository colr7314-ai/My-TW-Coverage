"""Monthly-revenue fundamental momentum.

Sources:
  - TWSE listed (sii):  https://openapi.twse.com.tw/v1/opendata/t187ap05_L
  - TPEx listed (otc):  https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O

Both endpoints return JSON arrays of every company's latest monthly revenue
disclosure. Schema (the field names vary between the two — we normalize):

  公司代號 / Company Code   -> ticker
  營業收入-當月營收           -> revenue (NTD thousands)
  營業收入-上月比較增減(%)    -> mom_pct
  營業收入-去年同月增減(%)    -> yoy_pct
  資料年月 / Data_yyyymm     -> period (YYYYMM)

Each call returns ONE month of data. We snapshot it to
``data/fundamentals/<YYYYMM>.csv`` and merge the latest 6-12 months on
read to compute trailing acceleration.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = REPO_ROOT / "data"
FUND_DIR = DATA_ROOT / "fundamentals"

TWSE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"
TPEX_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O"

# Field-name candidates — both endpoints differ subtly across years.
TICKER_KEYS = ("公司代號", "Code", "code")
REVENUE_KEYS = ("營業收入-當月營收", "CurrentMonthRevenue", "Revenue")
MOM_KEYS = ("營業收入-上月比較增減(%)", "MoMRate", "MoM")
YOY_KEYS = ("營業收入-去年同月增減(%)", "YoYRate", "YoY")
PERIOD_KEYS = ("資料年月", "Data_yyyymm", "Year", "YearMonth")


def _pick(d: dict, keys: tuple[str, ...]):
    for k in keys:
        if k in d:
            return d[k]
    return None


def _to_float(x) -> float | None:
    if x is None or x == "":
        return None
    try:
        return float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return None


def fetch_monthly() -> pd.DataFrame:
    """Fetch the most-recent month from BOTH TWSE and TPEx and concatenate."""
    import urllib.request

    rows = []
    for url, board in ((TWSE_URL, "TWSE"), (TPEX_URL, "TPEx")):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                payload = json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"  [{board}] fetch failed: {e}")
            continue
        for d in payload:
            ticker = _pick(d, TICKER_KEYS)
            if not ticker:
                continue
            rows.append({
                "ticker": str(ticker).strip(),
                "board": board,
                "period": str(_pick(d, PERIOD_KEYS) or ""),
                "revenue": _to_float(_pick(d, REVENUE_KEYS)),
                "mom_pct": _to_float(_pick(d, MOM_KEYS)),
                "yoy_pct": _to_float(_pick(d, YOY_KEYS)),
            })
    return pd.DataFrame(rows)


def save_monthly(df: pd.DataFrame) -> Path | None:
    """Save the snapshot to ``data/fundamentals/<period>.csv``."""
    if df.empty or "period" not in df.columns:
        return None
    periods = df["period"].dropna().unique()
    if len(periods) == 0:
        return None
    period = sorted(periods)[-1]
    FUND_DIR.mkdir(parents=True, exist_ok=True)
    out = FUND_DIR / f"{period}.csv"
    df.to_csv(out, index=False)
    return out


def load_recent(months: int = 6) -> pd.DataFrame:
    """Concatenate the most recent ``months`` snapshots (long format)."""
    if not FUND_DIR.exists():
        return pd.DataFrame()
    files = sorted(FUND_DIR.glob("*.csv"))[-months:]
    frames = [pd.read_csv(f, dtype={"ticker": str, "period": str}) for f in files]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def latest_signals(months: int = 6) -> pd.DataFrame:
    """Per-ticker fundamental signals derived from the recent revenue stack.

    Output columns:
      - latest_period       : most recent YYYYMM published
      - revenue             : latest month revenue (NTD thousands)
      - mom_pct, yoy_pct    : as published
      - yoy_3m_avg          : trailing 3-month avg YoY
      - yoy_accelerating    : True if last YoY > yoy_3m_avg by ≥5pp
      - consec_pos_yoy      : count of consecutive months with YoY>0 (most recent)
    """
    long = load_recent(months=months)
    if long.empty:
        return pd.DataFrame()

    long = long.sort_values(["ticker", "period"])
    out_rows = []
    for ticker, sub in long.groupby("ticker"):
        sub = sub.dropna(subset=["yoy_pct"])
        if sub.empty:
            continue
        latest = sub.iloc[-1]
        yoys = sub["yoy_pct"].tolist()
        yoy_3m = float(pd.Series(yoys[-3:]).mean()) if len(yoys) >= 1 else None
        accel = (
            yoy_3m is not None
            and pd.notna(latest["yoy_pct"])
            and latest["yoy_pct"] > yoy_3m + 5
        )
        consec = 0
        for v in reversed(yoys):
            if v is not None and v > 0:
                consec += 1
            else:
                break
        out_rows.append({
            "ticker": ticker,
            "latest_period": latest["period"],
            "revenue": latest.get("revenue"),
            "mom_pct": latest.get("mom_pct"),
            "yoy_pct": latest.get("yoy_pct"),
            "yoy_3m_avg": yoy_3m,
            "yoy_accelerating": bool(accel),
            "consec_pos_yoy": consec,
        })
    return pd.DataFrame(out_rows)
