"""CLI entry: build index, fetch prices, compute momentum, save snapshot.

Usage:
  python -m momentum.cli build-index
  python -m momentum.cli fetch-prices [--mock]
  python -m momentum.cli compute            # reads cached prices -> data/daily/
  python -m momentum.cli daily              # full pipeline (fetch + compute)
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

from . import indexer, momentum, themes
from .prices import (
    PRICE_DIR, all_cached_tickers, fetch_and_cache, fetch_benchmark, load_benchmark,
)


def cmd_build_index(_args) -> None:
    stats = indexer.build_index()
    print(json.dumps(stats, ensure_ascii=False, indent=2))


def cmd_fetch_prices(args) -> None:
    if args.mock:
        from . import mock_prices
        companies = themes.load_companies()
        theme_index = themes.load_theme_index()
        ticker_themes = json.loads(
            (indexer.DATA_ROOT / "ticker_themes.json").read_text(encoding="utf-8")
        )
        drift = mock_prices.default_theme_drift(theme_index)
        mock_prices.generate_mock(
            list(companies),
            theme_drift=drift,
            ticker_themes=ticker_themes,
        )
        print(f"Mock OHLCV generated for {len(companies)} tickers + benchmark.")
        return
    companies = themes.load_companies()
    tickers = list(companies)
    if args.limit:
        tickers = tickers[: args.limit]
    print(f"Fetching {len(tickers)} tickers + benchmark…")
    fetch_benchmark()
    stats = fetch_and_cache(tickers, period=args.period)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


def cmd_compute(_args) -> None:
    bench = load_benchmark()
    tickers = all_cached_tickers()
    print(f"Computing momentum for {len(tickers)} tickers…")
    metrics_list: list[momentum.Metrics] = []
    for t in tickers:
        df = pd.read_csv(PRICE_DIR / f"{t}.csv", index_col="Date", parse_dates=["Date"])
        metrics_list.append(momentum.compute_metrics(t, df, bench=bench))
    momentum.populate_rs_rating(metrics_list)
    metrics_df = momentum.metrics_to_dataframe(metrics_list)

    theme_index = themes.load_theme_index()
    themes_df = themes.aggregate_themes(metrics_df, theme_index)

    today = date.today().isoformat()
    out_dir = themes.save_daily_snapshot(metrics_df, themes_df, today)
    print(f"Wrote snapshot → {out_dir}")
    print(f"  tickers in snapshot: {len(metrics_df)}")
    print(f"  themes in snapshot:  {len(themes_df)}")


def cmd_daily(args) -> None:
    cmd_fetch_prices(args)
    cmd_compute(args)


def main() -> None:
    p = argparse.ArgumentParser(prog="momentum")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("build-index").set_defaults(func=cmd_build_index)

    fp = sub.add_parser("fetch-prices")
    fp.add_argument("--mock", action="store_true",
                    help="Generate synthetic prices for local dev.")
    fp.add_argument("--period", default="1y")
    fp.add_argument("--limit", type=int, default=None,
                    help="Cap how many tickers to fetch (testing).")
    fp.set_defaults(func=cmd_fetch_prices)

    sub.add_parser("compute").set_defaults(func=cmd_compute)

    d = sub.add_parser("daily")
    d.add_argument("--mock", action="store_true")
    d.add_argument("--period", default="1y")
    d.add_argument("--limit", type=int, default=None)
    d.set_defaults(func=cmd_daily)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
