from __future__ import annotations

import json
import re
import time
import uuid
from urllib.parse import quote

from ..net import TIMEOUT, SourceError, check, make_session
from ..niches import niche_from_tiktok_industry
from ..text import key, parse_compact_number
from .base import SourceResult, failure, pick

CREATIVE_CENTER = "https://ads.tiktok.com/business/creativecenter"
HASHTAG_PAGES = (
    CREATIVE_CENTER + "/inspiration/popular/hashtag/pc/es?countryCode=ES&period=7",
    CREATIVE_CENTER + "/inspiration/popular/hashtag/pc/en?countryCode=ES&period=7",
)
MUSIC_PAGES = (
    CREATIVE_CENTER + "/inspiration/popular/music/pc/es?countryCode=ES&period=7",
    CREATIVE_CENTER + "/inspiration/popular/music/pc/en?countryCode=ES&period=7",
)
HASHTAG_API = "https://ads.tiktok.com/creative_radar_api/v1/popular_trend/hashtag/list"
BROWSE_URL = CREATIVE_CENTER + "/inspiration/popular/hashtag/pc/es?countryCode=ES&period=7"
_NEXT_RE = re.compile(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def extract_next_data(html_text: str):
    match = _NEXT_RE.search(html_text or "")
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except ValueError:
        return None


def find_record_lists(obj, predicate, depth: int = 0):
    if depth > 14:
        return
    if isinstance(obj, list):
        dicts = [x for x in obj if isinstance(x, dict)]
        if dicts and len(dicts) >= max(1, len(obj) // 2) and predicate(dicts[0]):
            yield dicts
            return
        for value in obj:
            yield from find_record_lists(value, predicate, depth + 1)
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from find_record_lists(value, predicate, depth + 1)


def _is_hashtag(record: dict) -> bool:
    return any(k in record for k in ("hashtag_name", "hashtagName"))


def _is_song(record: dict) -> bool:
    has_title = "title" in record
    has_author = any(k in record for k in ("author", "artist", "singer"))
    has_id = any(k in record for k in ("clip_id", "clipId", "song_id", "songId", "music_id", "musicId"))
    return has_title and (has_author or has_id)


def _trend_curve(record: dict) -> list:
    curve = pick(record, "trend", "trends", default=[]) or []
    values = []
    for point in curve if isinstance(curve, list) else []:
        if isinstance(point, dict) and isinstance(point.get("value"), (int, float)):
            values.append(float(point["value"]))
    return values


def _rank_change(record: dict):
    diff = pick(record, "rank_diff", "rankDiff")
    kind = pick(record, "rank_diff_type", "rankDiffType")
    if kind == 3 or str(kind).lower() == "new":
        return None, True
    if isinstance(diff, (int, float)):
        if kind == 2:
            return -abs(int(diff)), False
        return int(diff), False
    return None, False


def _industry(record: dict):
    info = pick(record, "industry_info", "industryInfo")
    if isinstance(info, dict):
        return info.get("value") or info.get("label") or info.get("name")
    if isinstance(info, str):
        return info
    return None


def parse_hashtags(records: list) -> list:
    items = []
    for index, record in enumerate(records, 1):
        name = str(pick(record, "hashtag_name", "hashtagName", default="")).strip().lstrip("#")
        if not name:
            continue
        change, is_new = _rank_change(record)
        industry = _industry(record)
        items.append({
            "id": key(name),
            "title": "#" + name,
            "name": name,
            "rank": int(pick(record, "rank", default=index) or index),
            "posts": parse_compact_number(pick(record, "publish_cnt", "publishCnt", "post_count")),
            "views": parse_compact_number(pick(record, "video_views", "videoViews", "views")),
            "rank_change": change,
            "is_new": is_new,
            "industry": industry,
            "niche_hint": niche_from_tiktok_industry(industry) if industry else None,
            "series": _trend_curve(record),
            "series_step": 86400,
            "url": f"https://www.tiktok.com/tag/{quote(name)}",
        })
    items.sort(key=lambda i: i["rank"])
    return items


def parse_songs(records: list) -> list:
    items = []
    for index, record in enumerate(records, 1):
        title = str(pick(record, "title", default="")).strip()
        if not title:
            continue
        author = str(pick(record, "author", "artist", "singer", default="")).strip()
        change, is_new = _rank_change(record)
        link = pick(record, "link", "url")
        query = quote(f"{title} {author}".strip())
        items.append({
            "id": key(f"{title} {author}"),
            "title": title,
            "author": author,
            "rank": int(pick(record, "rank", default=index) or index),
            "rank_change": change,
            "is_new": is_new,
            "cover": pick(record, "cover", "cover_url", "coverUrl"),
            "duration": pick(record, "duration"),
            "series": _trend_curve(record),
            "url": link if isinstance(link, str) and link.startswith("http") else f"https://www.tiktok.com/search?q={query}",
        })
    items.sort(key=lambda i: i["rank"])
    return items


def _from_pages(session, pages, predicate):
    for url in pages:
        try:
            response = check(session.get(url, timeout=TIMEOUT, headers={"Accept": "text/html"}), "TikTok Creative Center")
        except Exception:
            continue
        data = extract_next_data(response.text)
        if data is None:
            continue
        for records in find_record_lists(data, predicate):
            return records
    return []


def _from_api(session):
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Referer": BROWSE_URL,
        "anonymous-user-id": str(uuid.uuid4()),
        "timestamp": str(int(time.time())),
        "lang": "es",
    }
    params = {"page": 1, "limit": 50, "period": 7, "country_code": "ES", "sort_by": "popular"}
    response = check(session.get(HASHTAG_API, params=params, headers=headers, timeout=TIMEOUT), "TikTok Creative Center")
    payload = response.json()
    for records in find_record_lists(payload, _is_hashtag):
        return records
    return []


def fetch() -> SourceResult:
    session = make_session()
    hashtags_raw = _from_pages(session, HASHTAG_PAGES, _is_hashtag)
    provider = "creative_center_page"
    if not hashtags_raw:
        try:
            hashtags_raw = _from_api(session)
            provider = "creative_center_api"
        except Exception:
            hashtags_raw = []
    songs_raw = _from_pages(session, MUSIC_PAGES, _is_song)
    hashtags, songs = parse_hashtags(hashtags_raw), parse_songs(songs_raw)
    if not hashtags and not songs:
        return failure("tiktok", SourceError(
            "TikTok no ha devuelto datos públicos ahora mismo. Puedes consultarlos en Creative Center desde el botón de esta sección."
        ))
    meta = {"provider": provider, "songs": songs, "browse_url": BROWSE_URL, "period_days": 7}
    return SourceResult(source="tiktok", ok=True, items=hashtags, meta=meta)
