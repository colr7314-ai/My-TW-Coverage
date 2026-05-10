"""Daily alert pusher.

Posts a markdown summary of today's snapshot to a webhook URL. Auto-detects
Slack-style (``hooks.slack.com``) vs Discord-style (``discord.com``) and
formats the payload appropriately. Anything else is sent as a generic
``{"text": "..."}`` JSON POST, which works with Mattermost / Teams /
homemade endpoints.

Configure with the ``MOMENTUM_WEBHOOK_URL`` env var (set as a GitHub Actions
secret in production). If unset, this module is a no-op.
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import Iterable

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DAILY_DIR = REPO_ROOT / "data" / "daily"


def _format_pct(x) -> str:
    if x is None or pd.isna(x):
        return "—"
    return f"{x * 100:+.1f}%"


def build_summary(metrics_df: pd.DataFrame, themes_df: pd.DataFrame,
                  snapshot_date: str, top_n: int = 8) -> str:
    """Compose the markdown body for today's alert."""
    lines = [f"*📈 台股題材動能 · {snapshot_date}*", ""]

    hot = themes_df.dropna(subset=["median_ret_1m"]).sort_values(
        "median_ret_1m", ascending=False).head(top_n)
    lines.append("*🔥 領漲題材 (1M 中位數)*")
    for _, r in hot.iterrows():
        lines.append(f"  • `{r['theme']}` ({int(r['n_with_price'])} 檔) "
                     f"{_format_pct(r['median_ret_1m'])}  RS {r.get('mean_rs_rating', 0):.0f}")

    if "rotation_score" in themes_df.columns:
        rot = themes_df.dropna(subset=["rotation_score"])
        if not rot.empty:
            rot_top = rot.sort_values("rotation_score", ascending=False).head(5)
            lines += ["", "*♻️ 本週輪動進場*"]
            for _, r in rot_top.iterrows():
                lines.append(f"  • `{r['theme']}` 1W 中位數 "
                             f"從 {_format_pct(r['median_ret_1w'] - r['rotation_score'])} "
                             f"→ {_format_pct(r['median_ret_1w'])}")

    movers = metrics_df.dropna(subset=["rs_rating"]).copy()
    movers = movers[movers["last_close"].fillna(0) >= 10]
    movers = movers.sort_values("rs_rating", ascending=False).head(top_n)
    lines += ["", "*🚀 個股 RS 領先*"]
    for _, r in movers.iterrows():
        flags = []
        if r.get("new_high_60d"):
            flags.append("60D高")
        if r.get("vol_surge") and r["vol_surge"] > 2:
            flags.append("爆量")
        flag_str = (" · " + ", ".join(flags)) if flags else ""
        lines.append(f"  • `{r['ticker']}` RS {r['rs_rating']:.0f} · "
                     f"1M {_format_pct(r['ret_1m'])}{flag_str}")
    return "\n".join(lines)


def _slack_payload(text: str) -> dict:
    return {"text": text, "mrkdwn": True}


def _discord_payload(text: str) -> dict:
    # Discord uses "content" and supports up to 2000 chars in basic markdown.
    return {"content": text[:1990]}


def _generic_payload(text: str) -> dict:
    return {"text": text}


def post_webhook(text: str, url: str | None = None) -> bool:
    url = url or os.environ.get("MOMENTUM_WEBHOOK_URL")
    if not url:
        print("MOMENTUM_WEBHOOK_URL not set — skipping alert.")
        return False

    if "hooks.slack.com" in url:
        body = _slack_payload(text)
    elif "discord.com" in url or "discordapp.com" in url:
        body = _discord_payload(text)
    else:
        body = _generic_payload(text)

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            r.read()
        print(f"Alert posted ({len(text)} chars).")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"Alert post failed: {e}")
        return False


def push_latest_snapshot() -> bool:
    """Read the most recent snapshot and post it. Returns True on success."""
    if not DAILY_DIR.exists():
        print("No snapshot dir.")
        return False
    dates = sorted(p.name for p in DAILY_DIR.iterdir() if p.is_dir())
    if not dates:
        print("No snapshots yet.")
        return False
    latest = dates[-1]
    d = DAILY_DIR / latest
    metrics = pd.read_csv(d / "ticker_momentum.csv", dtype={"ticker": str})
    themes = pd.read_json(d / "themes_ranking.json")
    text = build_summary(metrics, themes, latest)
    return post_webhook(text)
