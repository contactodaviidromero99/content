from __future__ import annotations

import re
import time
from urllib.parse import quote

from bs4 import BeautifulSoup

from ..net import TIMEOUT, SourceError, check, make_session
from ..text import key, parse_compact_number
from .base import SourceResult, failure

TRENDS24_URL = "https://trends24.in/spain/"
GETDAYTRENDS_URL = "https://getdaytrends.com/spain/"
_SEARCH_HREF = re.compile(r"(twitter|x)\.com/search", re.I)
_COUNT_RE = re.compile(r"([\d.,]+\s*[KkMm]?)\s*(?:tweets|posts|publicaciones)", re.I)


def search_url(name: str) -> str:
    return f"https://x.com/search?q={quote(name)}&src=trend_click"


def _count_from(node):
    if node is None:
        return None
    raw = node.get("data-count") if hasattr(node, "get") else None
    if raw and re.fullmatch(r"\d+", str(raw).strip()):
        return int(raw)
    return parse_compact_number(node.get_text(" ", strip=True))


def parse_trends24(html_text: str) -> list:
    soup = BeautifulSoup(html_text or "", "html.parser")
    lists = soup.select("ol.trend-card__list")
    if not lists:
        lists = [ol for ol in soup.find_all("ol") if ol.find("a", href=_SEARCH_HREF)]
    cards = []
    for ol in lists:
        stamp = None
        header = ol.find_previous(attrs={"data-timestamp": True})
        if header is not None:
            try:
                stamp = float(header["data-timestamp"])
            except (TypeError, ValueError):
                stamp = None
        entries = []
        for li in ol.find_all("li"):
            link = li.find("a")
            if link is None:
                continue
            name = link.get_text(" ", strip=True)
            if not name:
                continue
            count = _count_from(li.find(class_=re.compile("tweet-count|count")))
            entries.append((name, count))
        if entries:
            cards.append((stamp, entries))
    return cards


def _polyline_ranks(row) -> dict:
    ranks = {}
    for line in row.find_all("polyline"):
        if "grid" in " ".join(line.get("class") or []):
            continue
        for x_value, y_value in re.findall(r"(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)", line.get("points") or ""):
            slot = int(round(float(x_value) / 20))
            y = float(y_value)
            if 0 <= slot <= 7 and y < 50:
                ranks[slot] = int(round(y)) + 1
    return ranks


def parse_getdaytrends(html_text: str, now: float = None) -> list:
    soup = BeautifulSoup(html_text or "", "html.parser")
    now = now or time.time()
    rows = soup.select("table.trends tr") or soup.select("tr")
    seen, current, history = set(), [], []
    for row in rows:
        link = row.find("a", href=re.compile(r"/trend/"))
        if link is None:
            continue
        name = link.get_text(" ", strip=True)
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        count = None
        match = _COUNT_RE.search(row.get_text(" ", strip=True))
        if match:
            count = parse_compact_number(match.group(1))
        current.append((name, count))
        history.append(_polyline_ranks(row))
        if len(current) >= 50:
            break
    if not current:
        return []
    cards = [(now, current)]
    for slot in range(6, -1, -1):
        entries = sorted(
            ((ranks[slot], name, count) for (name, count), ranks in zip(current, history) if slot in ranks),
            key=lambda entry: entry[0],
        )
        cards.append((now - (7 - slot) * 3600, [(name, count, rank) for rank, name, count in entries]))
    while len(cards) > 1 and not cards[-1][1]:
        cards.pop()
    return cards


def build_items(cards: list, now: float = None) -> list:
    if not cards:
        return []
    now = now or time.time()
    current = cards[0][1][:50]
    history = cards[:24]
    positions = []
    for _, entries in history:
        positions.append({key(entry[0]): (entry[2] if len(entry) > 2 else index + 1) for index, entry in enumerate(entries)})
    items = []
    for rank, (name, count, *_rest) in enumerate(current, 1):
        ident = key(name)
        ranks = [p.get(ident) for p in positions]
        streak = 0
        for value in ranks:
            if value is None:
                break
            streak += 1
        present = [i for i, value in enumerate(ranks) if value is not None]
        first_index = max(present) if present else 0
        first_seen = None
        stamp = history[first_index][0]
        if stamp:
            first_seen = int(stamp)
        elif first_index:
            first_seen = int(now - first_index * 3600)
        previous = ranks[1] if len(ranks) > 1 else None
        items.append({
            "id": ident,
            "title": name,
            "rank": rank,
            "volume": count,
            "rank_change": (previous - rank) if previous else None,
            "is_new": len(ranks) > 1 and previous is None,
            "hours_in_trends": streak,
            "first_seen": first_seen,
            "best_rank": min(v for v in ranks if v) if present else rank,
            "series": [float(51 - v) if v else 0.0 for v in reversed(ranks)],
            "series_step": 3600,
            "url": search_url(name),
        })
    return items


def fetch() -> SourceResult:
    session = make_session()
    errors = []
    for label, url, parser in (
        ("getdaytrends", GETDAYTRENDS_URL, parse_getdaytrends),
        ("trends24", TRENDS24_URL, parse_trends24),
    ):
        try:
            response = check(session.get(url, timeout=TIMEOUT), label)
            items = build_items(parser(response.text))
            if items:
                return SourceResult(source="x", ok=True, items=items, meta={"provider": label})
            errors.append(f"{label}: sin tendencias reconocibles")
        except Exception as exc:
            errors.append(f"{label}: {exc}")
    return failure("x", SourceError("No se pudieron leer las tendencias de X. " + " | ".join(errors)))
