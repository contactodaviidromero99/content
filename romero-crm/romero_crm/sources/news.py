from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import quote

from ..net import TIMEOUT, check, make_session
from ..text import key
from .base import SourceResult, failure

BASE = "https://news.google.com/rss"
PARAMS = "hl=es&gl=ES&ceid=ES:es"
SECTIONS = (
    ("portada", None, "Portada"),
    ("espana", "NATION", "España"),
    ("internacional", "WORLD", "Internacional"),
    ("economia", "BUSINESS", "Economía"),
    ("tecnologia", "TECHNOLOGY", "Tecnología"),
    ("entretenimiento", "ENTERTAINMENT", "Entretenimiento"),
    ("deportes", "SPORTS", "Deportes"),
    ("ciencia", "SCIENCE", "Ciencia"),
    ("salud", "HEALTH", "Salud"),
)
SECTION_LABELS = {sid: label for sid, _, label in SECTIONS}


def section_url(topic) -> str:
    if topic is None:
        return f"{BASE}?{PARAMS}"
    return f"{BASE}/headlines/section/topic/{topic}?{PARAMS}"


def search_url(query: str) -> str:
    return f"{BASE}/search?q={quote(query)}+when:2d&{PARAMS}"


def parse_rss(text: str, section: str = None) -> list:
    try:
        root = ET.fromstring((text or "").encode("utf-8"))
    except ET.ParseError:
        return []
    items = []
    for node in root.iter("item"):
        title = (node.findtext("title") or "").strip()
        if not title:
            continue
        source_node = node.find("source")
        source = (source_node.text or "").strip() if source_node is not None else ""
        if source and title.endswith(" - " + source):
            title = title[: -len(source) - 3].strip()
        published = None
        raw_date = node.findtext("pubDate")
        if raw_date:
            try:
                published = int(parsedate_to_datetime(raw_date).timestamp())
            except (TypeError, ValueError):
                published = None
        description = node.findtext("description") or ""
        coverage = max(1, description.count("<li"))
        items.append({
            "id": key(title)[:80],
            "title": title,
            "url": (node.findtext("link") or "").strip(),
            "source": source,
            "published": published,
            "coverage": coverage,
            "section": section,
        })
    return items


def search(query: str, limit: int = 6) -> list:
    session = make_session()
    response = check(session.get(search_url(query), timeout=TIMEOUT), "Google News")
    return parse_rss(response.text)[:limit]


def fetch() -> SourceResult:
    session = make_session()
    sections, errors = {}, []
    for section_id, topic, _label in SECTIONS:
        try:
            response = check(session.get(section_url(topic), timeout=TIMEOUT), "Google News")
            sections[section_id] = parse_rss(response.text, section_id)[:40]
        except Exception as exc:
            errors.append(f"{section_id}: {exc}")
        time.sleep(0.2)
    if not any(sections.values()):
        return failure("news", Exception(errors[0] if errors else "Sin noticias"))
    items, seen = [], set()
    for section_id, _topic, _label in SECTIONS:
        for item in sections.get(section_id, []):
            if item["id"] in seen:
                continue
            seen.add(item["id"])
            items.append(item)
    meta = {"sections": {sid: [i["id"] for i in rows] for sid, rows in sections.items()}, "errors": errors}
    return SourceResult(source="news", ok=True, items=items, meta=meta)
