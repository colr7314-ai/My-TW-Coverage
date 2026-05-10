"""Wikilink indexer.

Scans every report under ``Pilot_Reports/`` and builds:
  - ``theme_index.json``    : theme -> tickers + classification
  - ``ticker_themes.json``  : ticker -> themes it references
  - ``companies.json``      : ticker -> canonical company name + sector

A "theme" is any ``[[wikilink]]`` that is NOT the file's own subject company
and not in the generic-word blacklist. Themes are classified into:
  - ``tw_company``  : matches another covered ticker's canonical name
  - ``technology``  : seed list or uppercase acronym heuristic
  - ``other``       : foreign companies, materials, applications, etc.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

WIKILINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")
FILENAME_RE = re.compile(r"^(\d{4,5})_(.+)\.md$")

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS_ROOT = REPO_ROOT / "Pilot_Reports"
DATA_ROOT = REPO_ROOT / "data"

# Seed list of named technologies / materials / applications, from CLAUDE.md.
TECH_SEEDS: frozenset[str] = frozenset({
    # Packaging
    "CoWoS", "InFO", "FOPLP", "CPO", "HBM", "2.5D 封裝", "3D 封裝",
    # Photonics
    "矽光子", "EML", "VCSEL", "光收發模組",
    # Processes
    "EUV", "蝕刻", "CVD", "PVD", "CMP", "微影", "磊晶",
    # Materials
    "光阻液", "研磨液", "超純水", "ABF", "BT 樹脂", "銅箔", "玻纖布",
    # Substrates
    "ABF 載板", "BT 載板", "矽晶圓", "碳化矽", "氮化鎵", "磷化銦",
    # Components
    "MLCC", "MOSFET", "IGBT", "導線架", "探針卡",
    # Applications
    "AI 伺服器", "電動車", "5G", "低軌衛星", "資料中心",
    # Macro
    "AI", "半導體", "物聯網", "IoT", "消費性電子",
})

# Generic category words that should never have been wikilinked but sometimes are.
BLACKLIST: frozenset[str] = frozenset({
    "大廠", "供應商", "客戶", "廠商", "原廠", "經銷商", "製造商",
    "業者", "企業", "公司", "AI 補充", "待 AI 補充", "待補充",
})


def parse_ticker_from_filename(filename: str) -> tuple[str | None, str | None]:
    m = FILENAME_RE.match(filename)
    if not m:
        return None, None
    return m.group(1), m.group(2)


def extract_wikilinks(text: str) -> list[str]:
    return [m.group(1).strip() for m in WIKILINK_RE.finditer(text)]


def classify_theme(theme: str, company_to_ticker: dict[str, str]) -> str:
    if theme in company_to_ticker:
        return "tw_company"
    if theme in TECH_SEEDS:
        return "technology"
    # Uppercase / digit / dash acronym 2-8 chars -> likely a tech term
    if re.fullmatch(r"[A-Z0-9][A-Z0-9\-/]{1,7}", theme):
        return "technology"
    return "other"


def build_index(
    reports_root: Path = REPORTS_ROOT,
    data_root: Path = DATA_ROOT,
) -> dict:
    company_to_ticker: dict[str, str] = {}
    ticker_to_name: dict[str, str] = {}
    ticker_to_canonical: dict[str, str] = {}
    ticker_to_sector: dict[str, str] = {}
    ticker_to_wikilinks: dict[str, list[str]] = {}

    md_files = sorted(reports_root.rglob("*.md"))
    for md in md_files:
        ticker, name = parse_ticker_from_filename(md.name)
        if ticker is None:
            continue
        text = md.read_text(encoding="utf-8")
        ticker_to_name[ticker] = name
        ticker_to_sector[ticker] = md.parent.name

        first_line = text.splitlines()[0] if text else ""
        m = WIKILINK_RE.search(first_line)
        canonical = m.group(1).strip() if m else name
        ticker_to_canonical[ticker] = canonical
        company_to_ticker[canonical] = ticker

        ticker_to_wikilinks[ticker] = extract_wikilinks(text)

    theme_to_tickers: dict[str, set[str]] = defaultdict(set)
    for ticker, links in ticker_to_wikilinks.items():
        own = ticker_to_canonical.get(ticker)
        for link in links:
            if link == own or link in BLACKLIST:
                continue
            theme_to_tickers[link].add(ticker)

    themes: dict[str, dict] = {}
    for theme, tickers in theme_to_tickers.items():
        themes[theme] = {
            "type": classify_theme(theme, company_to_ticker),
            "ticker_count": len(tickers),
            "tickers": sorted(tickers),
            "tw_ticker": company_to_ticker.get(theme),
        }

    ticker_themes: dict[str, dict] = {}
    for ticker, links in ticker_to_wikilinks.items():
        own = ticker_to_canonical.get(ticker)
        cleaned = sorted({l for l in links if l != own and l not in BLACKLIST})
        ticker_themes[ticker] = {
            "name": ticker_to_name[ticker],
            "canonical": ticker_to_canonical.get(ticker),
            "sector": ticker_to_sector[ticker],
            "themes": cleaned,
        }

    companies = {
        t: {"name": ticker_to_name[t],
            "canonical": ticker_to_canonical.get(t),
            "sector": ticker_to_sector[t]}
        for t in sorted(ticker_to_name)
    }

    data_root.mkdir(parents=True, exist_ok=True)
    _write_json(data_root / "theme_index.json", themes, sort=True)
    _write_json(data_root / "ticker_themes.json", ticker_themes, sort=True)
    _write_json(data_root / "companies.json", companies, sort=False)

    return {
        "ticker_count": len(ticker_to_name),
        "theme_count": len(themes),
        "tw_company_themes": sum(1 for t in themes.values() if t["type"] == "tw_company"),
        "technology_themes": sum(1 for t in themes.values() if t["type"] == "technology"),
        "other_themes": sum(1 for t in themes.values() if t["type"] == "other"),
    }


def _write_json(path: Path, obj, sort: bool = False) -> None:
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=sort),
        encoding="utf-8",
    )


def top_themes(themes: dict, type_filter: str | None = None, n: int = 20) -> list[tuple[str, int]]:
    items = themes.items()
    if type_filter:
        items = [(k, v) for k, v in items if v["type"] == type_filter]
    return sorted(((k, v["ticker_count"]) for k, v in items),
                  key=lambda x: -x[1])[:n]


if __name__ == "__main__":
    stats = build_index()
    print(json.dumps(stats, ensure_ascii=False, indent=2))

    themes = json.loads((DATA_ROOT / "theme_index.json").read_text(encoding="utf-8"))
    for label, kind in [("Top technology themes", "technology"),
                         ("Top other themes (foreign cos/materials/apps)", "other"),
                         ("Top tw_company themes (covered TW peers)", "tw_company")]:
        print(f"\n# {label}")
        for theme, count in top_themes(themes, kind, n=15):
            print(f"  {count:>4}  {theme}")
