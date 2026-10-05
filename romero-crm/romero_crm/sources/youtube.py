from __future__ import annotations

import base64
import json
import re
import statistics
import time
from urllib.parse import quote

from ..net import TIMEOUT, SourceError, check, make_session
from ..text import parse_ago_seconds, parse_compact_number, parse_duration
from .base import SourceResult

SEARCH_API = "https://www.youtube.com/youtubei/v1/search"
RESULTS_URL = "https://www.youtube.com/results"
CLIENT = {"clientName": "WEB", "clientVersion": "2.20260708.00.00", "hl": "es", "gl": "ES"}
_INITIAL_DATA_RE = re.compile(r"(?:var\s+ytInitialData|window\[\"ytInitialData\"\])\s*=\s*(\{.*?\});\s*</script>", re.S)

SORT_VIEWS = 3
UPLOAD_WEEK = 3
TYPE_VIDEO = 1


def search_params(sort=None, upload=None, kind=None, duration=None) -> str:
    filters = b""
    if upload:
        filters += bytes([0x08, upload])
    if kind:
        filters += bytes([0x10, kind])
    if duration:
        filters += bytes([0x18, duration])
    raw = b""
    if sort:
        raw += bytes([0x08, sort])
    if filters:
        raw += bytes([0x12, len(filters)]) + filters
    return base64.b64encode(raw).decode("ascii")


def _text(node) -> str:
    if isinstance(node, str):
        return node
    if not isinstance(node, dict):
        return ""
    if "simpleText" in node:
        return str(node["simpleText"])
    if "content" in node and isinstance(node["content"], str):
        return node["content"]
    runs = node.get("runs")
    if isinstance(runs, list):
        return "".join(str(r.get("text", "")) for r in runs if isinstance(r, dict))
    return ""


def _views(text: str):
    if not text or text.lower().startswith("no "):
        return 0 if text else None
    return parse_compact_number(text)


def _from_video_renderer(r: dict):
    video_id = r.get("videoId")
    if not video_id:
        return None
    url_path = (((r.get("navigationEndpoint") or {}).get("commandMetadata") or {}).get("webCommandMetadata") or {}).get("url", "")
    duration = parse_duration(_text(r.get("lengthText")))
    styles = [
        ((o.get("thumbnailOverlayTimeStatusRenderer") or {}).get("style"))
        for o in (r.get("thumbnailOverlays") or []) if isinstance(o, dict)
    ]
    is_short = "/shorts/" in url_path or "SHORTS" in styles
    published = _text(r.get("publishedTimeText"))
    return {
        "id": video_id,
        "title": _text(r.get("title") or r.get("headline")),
        "channel": _text(r.get("ownerText") or r.get("shortBylineText")),
        "views": _views(_text(r.get("viewCountText")) or _text(r.get("shortViewCountText"))),
        "published": published,
        "age_seconds": parse_ago_seconds(published),
        "duration": duration,
        "is_short": bool(is_short),
        "url": f"https://www.youtube.com/shorts/{video_id}" if is_short else f"https://www.youtube.com/watch?v={video_id}",
        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",
    }


def _from_lockup(r: dict):
    video_id = r.get("contentId")
    if not video_id or r.get("contentType") not in (None, "LOCKUP_CONTENT_TYPE_VIDEO"):
        return None
    meta = ((r.get("metadata") or {}).get("lockupMetadataViewModel")) or {}
    rows = (((meta.get("metadata") or {}).get("contentMetadataViewModel")) or {}).get("metadataRows") or []
    parts = [[_text((p or {}).get("text")) for p in (row.get("metadataParts") or [])] for row in rows if isinstance(row, dict)]
    channel = parts[0][0] if parts and parts[0] else ""
    views_text, published = "", ""
    for row in parts[1:] or parts:
        if len(row) >= 2:
            views_text, published = row[0], row[-1]
    duration_text = ""
    overlays = (((r.get("contentImage") or {}).get("thumbnailViewModel")) or {}).get("overlays") or []
    for overlay in overlays:
        for holder in ("thumbnailBottomOverlayViewModel", "thumbnailOverlayBadgeViewModel"):
            badges = (overlay.get(holder) or {}).get("badges") or (overlay.get(holder) or {}).get("thumbnailBadges") or []
            for badge in badges:
                text = ((badge or {}).get("thumbnailBadgeViewModel") or {}).get("text")
                if text:
                    duration_text = text
    duration = parse_duration(duration_text)
    return {
        "id": video_id,
        "title": _text(meta.get("title")),
        "channel": channel,
        "views": _views(views_text),
        "published": published,
        "age_seconds": parse_ago_seconds(published),
        "duration": duration,
        "is_short": False,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",
    }


def _from_short(r: dict):
    video_id = (((r.get("onTap") or {}).get("innertubeCommand") or {}).get("reelWatchEndpoint") or {}).get("videoId") or r.get("videoId")
    if not video_id:
        return None
    overlay = r.get("overlayMetadata") or {}
    return {
        "id": video_id,
        "title": _text(overlay.get("primaryText")) or _text(r.get("headline")),
        "channel": "",
        "views": _views(_text(overlay.get("secondaryText")) or _text(r.get("viewCountText"))),
        "published": "",
        "age_seconds": None,
        "duration": None,
        "is_short": True,
        "url": f"https://www.youtube.com/shorts/{video_id}",
        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",
    }


_RENDERERS = {
    "videoRenderer": _from_video_renderer,
    "lockupViewModel": _from_lockup,
    "shortsLockupViewModel": _from_short,
    "reelItemRenderer": _from_short,
}


def parse_search(data) -> list:
    found, seen = [], set()

    def walk(node, depth=0):
        if depth > 40:
            return
        if isinstance(node, dict):
            for name, parser in _RENDERERS.items():
                inner = node.get(name)
                if isinstance(inner, dict):
                    video = parser(inner)
                    if video and video["id"] not in seen and video["title"]:
                        seen.add(video["id"])
                        found.append(video)
            for value in node.values():
                walk(value, depth + 1)
        elif isinstance(node, list):
            for value in node:
                walk(value, depth + 1)

    walk(data)
    return found


def prepare_session(session) -> None:
    session.cookies.set("SOCS", "CAI", domain=".youtube.com", path="/")


def search(query: str, params: str = None) -> list:
    session = make_session()
    prepare_session(session)
    params = params or search_params(sort=SORT_VIEWS, upload=UPLOAD_WEEK, kind=TYPE_VIDEO)
    body = {"context": {"client": CLIENT}, "query": query, "params": params}
    headers = {
        "Content-Type": "application/json",
        "X-Youtube-Client-Name": "1",
        "X-Youtube-Client-Version": CLIENT["clientVersion"],
        "Origin": "https://www.youtube.com",
        "Referer": "https://www.youtube.com/",
    }
    try:
        response = check(session.post(SEARCH_API, params={"prettyPrint": "false"}, json=body, headers=headers, timeout=TIMEOUT), "YouTube")
        videos = parse_search(response.json())
        if videos:
            return videos
    except Exception:
        pass
    response = check(session.get(RESULTS_URL, params={"search_query": query, "sp": params, "hl": "es", "gl": "ES"}, timeout=TIMEOUT), "YouTube")
    match = _INITIAL_DATA_RE.search(response.text)
    if not match:
        raise SourceError("YouTube no devolvió resultados reconocibles.")
    return parse_search(json.loads(match.group(1)))


def competition(query: str) -> dict:
    return summarize(query, search(query))


def summarize(query: str, found: list) -> dict:
    videos = [v for v in found if v.get("views") is not None][:20]
    views = sorted((v["views"] for v in videos), reverse=True)
    count = len(videos)
    top = views[0] if views else 0
    median = int(statistics.median(views)) if views else 0
    strong = sum(1 for v in views if v >= 100_000)
    if count < 5 or top < 20_000:
        level, label = "hueco", "Hueco claro"
    elif strong >= 6 or median >= 150_000:
        level, label = "saturado", "Muy competido"
    else:
        level, label = "moderado", "Competencia moderada"
    return {
        "query": query,
        "count": count,
        "top_views": top,
        "median_views": median,
        "strong_videos": strong,
        "shorts": sum(1 for v in videos if v.get("is_short")),
        "level": level,
        "label": label,
        "videos": videos[:10],
        "checked_at": int(time.time()),
        "search_url": f"https://www.youtube.com/results?search_query={quote(query)}&sp={quote(search_params(sort=SORT_VIEWS, upload=UPLOAD_WEEK, kind=TYPE_VIDEO))}",
    }


def fetch_for_topics(topics: list, cache: dict, max_age: int = 6 * 3600) -> SourceResult:
    items, errors, now = [], [], time.time()
    for topic in topics:
        cached = cache.get(topic["key"])
        if cached and now - cached.get("checked_at", 0) < max_age:
            items.append(cached)
            continue
        try:
            result = competition(topic["query"])
            result.update({"topic_key": topic["key"], "topic_title": topic["title"]})
            cache[topic["key"]] = result
            items.append(result)
        except Exception as exc:
            errors.append(str(exc)[:160])
        time.sleep(0.6)
    if not items and errors:
        return SourceResult(source="youtube", ok=False, error="YouTube no respondió: " + errors[0])
    return SourceResult(source="youtube", ok=True, items=items, meta={"errors": errors[:3]})
