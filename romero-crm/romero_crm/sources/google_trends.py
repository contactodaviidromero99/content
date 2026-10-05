from __future__ import annotations

import html
import json
import re
from email.utils import parsedate_to_datetime
from urllib.parse import quote

from ..net import TIMEOUT, SourceError, check, make_session
from ..niches import GOOGLE_TOPICS
from ..text import key, parse_compact_number, smart_title
from .base import SourceResult, failure

BATCH_URL = "https://trends.google.com/_/TrendsUi/data/batchexecute"
RSS_URL = "https://trends.google.com/trending/rss"
GEO = "ES"
LANG = "es"
_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
    "Origin": "https://trends.google.com",
    "Referer": "https://trends.google.com/trending?geo=ES&hl=es",
}


def explore_url(query: str) -> str:
    return f"https://trends.google.com/trends/explore?geo={GEO}&hl=es&date=now%201-d&q={quote(query)}"


def parse_batch_response(text: str, rpc_id: str):
    for line in (text or "").splitlines():
        line = line.strip()
        if not line.startswith("["):
            continue
        try:
            chunk = json.loads(line)
        except ValueError:
            continue
        for entry in chunk if isinstance(chunk, list) else []:
            if isinstance(entry, list) and len(entry) > 2 and entry[0] == "wrb.fr" and entry[1] == rpc_id:
                if not entry[2]:
                    raise SourceError("Google Trends no devolvió datos para esta consulta.")
                return json.loads(entry[2])
    raise SourceError("Google Trends respondió con un formato desconocido.")


def _batch(session, rpc_id: str, payload):
    f_req = json.dumps([[[rpc_id, json.dumps(payload), None, "generic"]]])
    response = session.post(BATCH_URL, data={"f.req": f_req}, headers=_HEADERS, timeout=TIMEOUT)
    check(response, "Google Trends")
    return parse_batch_response(response.text, rpc_id)


def _timestamp(value):
    if isinstance(value, list) and value:
        value = value[0]
    if isinstance(value, (int, float)) and value > 0:
        return int(value)
    return None


def _news_from_list(row):
    if isinstance(row, dict):
        return {
            "title": row.get("title") or row.get("articleTitle"),
            "url": row.get("url"),
            "source": row.get("source"),
            "time": _timestamp(row.get("time")),
            "picture": row.get("picture"),
        }
    if not isinstance(row, list) or len(row) < 3:
        return None
    return {
        "title": row[0],
        "url": row[1],
        "source": row[2],
        "time": _timestamp(row[3]) if len(row) > 3 else None,
        "picture": row[4] if len(row) > 4 and isinstance(row[4], str) else None,
    }


def _news_tokens(raw) -> list:
    tokens = [t for t in (raw or []) if isinstance(t, (list, str)) and t]
    tokens.sort(key=lambda t: 0 if isinstance(t, list) and len(t) > 1 and t[1] == "es" else 1)
    return tokens[:6]


def parse_trending(payload) -> list:
    rows = payload[1] if isinstance(payload, list) and len(payload) > 1 and isinstance(payload[1], list) else []
    items = []
    for row in rows:
        if not isinstance(row, list) or not row or not isinstance(row[0], str):
            continue

        def at(index):
            return row[index] if len(row) > index else None

        keyword = row[0].strip()
        if not keyword:
            continue
        topics = [t for t in (at(10) or []) if isinstance(t, int)]
        categories = [GOOGLE_TOPICS[t] for t in topics if t in GOOGLE_TOPICS]
        news = [n for n in (_news_from_list(r) for r in (at(1) or [])) if n and n.get("title")]
        growth = at(8)
        ended = _timestamp(at(4))
        items.append({
            "id": key(keyword),
            "title": smart_title(keyword),
            "query": keyword,
            "volume": int(at(6) or 0),
            "growth_pct": float(growth) if isinstance(growth, (int, float)) else None,
            "started_at": _timestamp(at(3)),
            "ended_at": ended,
            "active": ended is None,
            "related": [r for r in (at(9) or []) if isinstance(r, str)][:40],
            "topics": topics,
            "categories": categories,
            "news_tokens": _news_tokens(at(11)),
            "news": news[:5],
            "url": explore_url(keyword),
        })
    items.sort(key=lambda i: (not i["active"], -i["volume"], -(i["growth_pct"] or 0)))
    for rank, item in enumerate(items, 1):
        item["rank"] = rank
    return items


_ITEM_RE = re.compile(r"<item>(.*?)</item>", re.S)
_NEWS_RE = re.compile(r"<ht:news_item>(.*?)</ht:news_item>", re.S)


def _tag(block: str, name: str):
    match = re.search(r"<%s(?:\s[^>]*)?>(.*?)</%s>" % (re.escape(name), re.escape(name)), block, re.S)
    if not match:
        return None
    value = match.group(1).strip()
    if value.startswith("<![CDATA["):
        value = value[9:-3]
    return html.unescape(value).strip() or None


def parse_rss(text: str) -> list:
    items = []
    for block in _ITEM_RE.findall(text or ""):
        title = _tag(block, "title")
        if not title:
            continue
        started = None
        pub = _tag(block, "pubDate")
        if pub:
            try:
                started = int(parsedate_to_datetime(pub).timestamp())
            except (TypeError, ValueError):
                started = None
        news = []
        for news_block in _NEWS_RE.findall(block):
            news.append({
                "title": _tag(news_block, "ht:news_item_title"),
                "url": _tag(news_block, "ht:news_item_url"),
                "source": _tag(news_block, "ht:news_item_source"),
                "picture": _tag(news_block, "ht:news_item_picture"),
                "time": None,
            })
        traffic = _tag(block, "ht:approx_traffic")
        items.append({
            "id": key(title),
            "title": smart_title(title),
            "query": title,
            "volume": parse_compact_number(traffic) or 0,
            "growth_pct": None,
            "started_at": started,
            "ended_at": None,
            "active": True,
            "related": [],
            "topics": [],
            "categories": [],
            "news_tokens": [],
            "news": [n for n in news if n.get("title")][:5],
            "picture": _tag(block, "ht:picture"),
            "url": explore_url(title),
        })
    items.sort(key=lambda i: -i["volume"])
    for rank, item in enumerate(items, 1):
        item["rank"] = rank
    return items


def fetch_rss(session) -> list:
    response = session.get(RSS_URL, params={"geo": GEO}, timeout=TIMEOUT)
    check(response, "Google Trends (RSS)")
    return parse_rss(response.text)


def fetch_news_by_tokens(tokens, max_news: int = 4) -> list:
    if not tokens:
        return []
    session = make_session()
    payload = _batch(session, "w4opAf", [list(tokens), max_news])
    rows = payload[0] if isinstance(payload, list) and payload and isinstance(payload[0], list) else []
    return [n for n in (_news_from_list(r) for r in rows) if n and n.get("title")]


def _merge_rss(items: list, rss_items: list) -> None:
    by_id = {i["id"]: i for i in rss_items}
    for item in items:
        extra = by_id.get(item["id"])
        if not extra:
            continue
        if not item.get("news"):
            item["news"] = extra.get("news") or []
        if extra.get("picture"):
            item["picture"] = extra["picture"]


def fetch(hours: int = 24) -> SourceResult:
    source_id = "google" if hours <= 24 else "google_week"
    session = make_session()
    meta = {"mode": "trending_now", "hours": hours}
    try:
        items = parse_trending(_batch(session, "i0OFE", [None, None, GEO, 0, LANG, hours, 1]))
        if not items:
            raise SourceError("Google Trends no devolvió tendencias.")
    except Exception as exc:
        if source_id == "google_week":
            return failure(source_id, exc)
        try:
            items = fetch_rss(session)
            meta.update({"mode": "rss", "fallback_reason": str(exc)[:200]})
        except Exception:
            return failure(source_id, exc)

    if source_id == "google" and meta["mode"] == "trending_now":
        try:
            _merge_rss(items, fetch_rss(session))
        except Exception:
            pass
    return SourceResult(source=source_id, ok=True, items=items, meta=meta)
