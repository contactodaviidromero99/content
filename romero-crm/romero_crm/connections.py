"""Tus vídeos publicados, para el calendario y el historial.

- YouTube: el feed público de tu canal (sin cuentas ni claves) y, si YouTube no lo sirve, las pestañas
  «Vídeos» y «Shorts» del canal.
- Instagram: la API oficial de Instagram con tu token (gratis; se configura una vez en Ajustes).
- Enlaces sueltos (TikTok, YouTube, Instagram): al pegar el enlace de un vídeo publicado se rellenan su
  título y su miniatura con oEmbed y, cuando la página lo deja ver, sus visualizaciones.

TikTok no permite leer la lista de vídeos de una cuenta sin una aplicación aprobada por TikTok; por eso
sus vídeos entran pegando el enlace (o desde Metricool, si algún día se activa su API)."""
from __future__ import annotations

import datetime as dt
import json
import re
import time
import xml.etree.ElementTree as ET
from urllib.parse import quote, urlparse

import requests

from .net import TIMEOUT, SourceError, check, make_session
from .planner import platform_of
from .sources import youtube as yt_search

YT_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
YT_TAB = "https://www.youtube.com/channel/{cid}/{tab}"
YT_WATCH = "https://www.youtube.com/watch?v={vid}"
APPROX = "youtube-aprox"
YT_OEMBED = "https://www.youtube.com/oembed?format=json&url={url}"
TT_OEMBED = "https://www.tiktok.com/oembed?url={url}"
IG_GRAPH = "https://graph.instagram.com"
_CHANNEL_ID = re.compile(r"(UC[\w-]{22})")
_CHANNEL_IN_PAGE = (
    re.compile(r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"'),
    re.compile(r'"externalId":"(UC[\w-]{22})"'),
    re.compile(r'"channelId":"(UC[\w-]{22})"'),
)
_NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015", "media": "http://search.yahoo.com/mrss/"}


def _session():
    session = make_session()
    session.cookies.set("SOCS", "CAI", domain=".youtube.com", path="/")
    return session


# ---------- YouTube ----------

def channel_page_url(value: str):
    value = (value or "").strip()
    if not value:
        return None
    if value.startswith("@"):
        return f"https://www.youtube.com/{quote(value, safe='@')}"
    if re.match(r"^[\w.-]{3,40}$", value) and not value.startswith("UC"):
        return f"https://www.youtube.com/@{quote(value)}"
    if value.startswith(("https://", "http://")) and "youtube.com" in urlparse(value).netloc:
        return value
    return None


def resolve_channel(value: str, session=None) -> str:
    """Acepta el ID (UC…), la URL del canal o tu @usuario y devuelve el ID del canal."""
    match = _CHANNEL_ID.search(value or "")
    if match and ("/channel/" in value or value.strip().startswith("UC")):
        return match.group(1)
    url = channel_page_url(value)
    if not url:
        raise SourceError("Escribe tu canal como @usuario o pega su enlace.")
    session = session or _session()
    response = check(session.get(url, timeout=TIMEOUT), "YouTube")
    for pattern in _CHANNEL_IN_PAGE:
        found = pattern.search(response.text)
        if found:
            return found.group(1)
    raise SourceError("No he encontrado ese canal de YouTube.")


def _iso_ts(text):
    if not text:
        return None
    try:
        return int(dt.datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())
    except ValueError:
        try:
            return int(dt.datetime.strptime(text, "%Y-%m-%dT%H:%M:%S%z").timestamp())
        except ValueError:
            return None


def parse_youtube_feed(text: str) -> list:
    try:
        root = ET.fromstring((text or "").encode("utf-8"))
    except ET.ParseError:
        return []
    items = []
    for entry in root.findall("a:entry", _NS):
        vid = entry.findtext("yt:videoId", default="", namespaces=_NS)
        if not vid:
            continue
        link = entry.find("a:link[@rel='alternate']", _NS)
        url = link.get("href") if link is not None else f"https://www.youtube.com/watch?v={vid}"
        group = entry.find("media:group", _NS)
        views = likes = None
        thumbnail = None
        if group is not None:
            thumb = group.find("media:thumbnail", _NS)
            thumbnail = thumb.get("url") if thumb is not None else None
            stats = group.find("media:community/media:statistics", _NS)
            if stats is not None and (stats.get("views") or "").isdigit():
                views = int(stats.get("views"))
            rating = group.find("media:community/media:starRating", _NS)
            if rating is not None and (rating.get("count") or "").isdigit():
                likes = int(rating.get("count"))
        items.append({
            "platform": "youtube", "vid": vid, "url": url, "title": (entry.findtext("a:title", default="", namespaces=_NS) or "").strip(),
            "published_at": _iso_ts(entry.findtext("a:published", default="", namespaces=_NS)),
            "views": views, "likes": likes, "comments": None, "shares": None,
            "thumbnail": thumbnail or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg", "source": "youtube",
        })
    return items


_WATCH_DATE = (
    re.compile(r'<meta itemprop="datePublished" content="([^"]+)"'),
    re.compile(r'"publishDate":"([^"]+)"'),
    re.compile(r'<meta itemprop="uploadDate" content="([^"]+)"'),
    re.compile(r'"uploadDate":"([^"]+)"'),
)


def fetch_youtube(channel_id: str, session=None, known: dict = None) -> list:
    """Tus vídeos de YouTube. Primero el feed del canal (fechas y visualizaciones exactas); si YouTube no
    lo sirve (a veces responde 404), las pestañas «Vídeos» y «Shorts» del canal."""
    session = session or _session()
    try:
        response = session.get(YT_FEED.format(cid=channel_id), timeout=TIMEOUT)
        if response.ok:
            return parse_youtube_feed(response.text)
        problem = f"error {response.status_code}"
    except requests.RequestException as exc:
        problem = exc.__class__.__name__
    items = fetch_youtube_tabs(channel_id, session, known)
    if items is None:
        raise SourceError(f"YouTube no ha dejado leer tu canal (feed: {problem}; pestañas: sin respuesta).")
    return items


def parse_channel_tab(text: str, shorts: bool = False):
    """Vídeos de una pestaña del canal (lo que YouTube pinta en la página). None si la página no se entiende."""
    match = yt_search._INITIAL_DATA_RE.search(text or "")
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return None
    videos = yt_search.parse_search(data)
    for video in videos:
        if shorts:
            video["is_short"] = True
            video["url"] = f"https://www.youtube.com/shorts/{video['id']}"
    return videos


def watch_date(vid: str, session) -> int:
    """Fecha exacta de publicación de un vídeo, leída de su página."""
    try:
        response = session.get(YT_WATCH.format(vid=vid), timeout=TIMEOUT)
    except requests.RequestException:
        return None
    if response.status_code >= 400:
        return None
    for pattern in _WATCH_DATE:
        found = pattern.search(response.text)
        if found and _iso_ts(found.group(1)):
            return _iso_ts(found.group(1))
    return None


def fetch_youtube_tabs(channel_id: str, session, known: dict = None, per_tab: int = 15, lookups: int = 8):
    """Las pestañas «Vídeos» y «Shorts». Las visualizaciones vienen en la página; la fecha exacta se lee
    de cada vídeo nuevo (como mucho `lookups` por vez). Si no se consigue, queda la aproximada
    («hace 2 días») marcada como tal, y se reintenta en la siguiente sincronización."""
    known = known or {}
    now = time.time()
    videos, understood = [], False
    for tab in ("videos", "shorts"):
        try:
            response = session.get(YT_TAB.format(cid=channel_id, tab=tab), params={"hl": "es", "gl": "ES"}, timeout=TIMEOUT)
        except requests.RequestException:
            continue
        if response.status_code >= 400:
            continue
        found = parse_channel_tab(response.text, shorts=tab == "shorts")
        if found is None:
            continue
        understood = True
        videos.extend(found[:per_tab])
    if not understood:
        return None
    items, seen = [], set()
    for video in videos:
        if video["id"] in seen:
            continue
        seen.add(video["id"])
        published, source = known.get(video["id"]), "youtube"
        if published is None and lookups > 0:
            lookups -= 1
            published = watch_date(video["id"], session)
            time.sleep(0.3)
        if published is None and video.get("age_seconds") is not None:
            published, source = int(now - video["age_seconds"]), APPROX
        items.append({
            "platform": "youtube", "vid": video["id"], "url": video["url"], "title": video.get("title") or "",
            "published_at": published, "views": video.get("views"), "likes": None, "comments": None, "shares": None,
            "thumbnail": f"https://i.ytimg.com/vi/{video['id']}/hqdefault.jpg", "source": source,
        })
    return items


# ---------- Instagram (API oficial) ----------

def _ig_get(session, path: str, params: dict):
    response = session.get(f"{IG_GRAPH}/{path}", params=params, timeout=TIMEOUT)
    try:
        data = response.json()
    except ValueError:
        data = {}
    if response.status_code >= 400 or "error" in data:
        message = ((data.get("error") or {}).get("message") or f"error {response.status_code}")[:200]
        raise SourceError(f"Instagram: {message}")
    return data


def _insight_value(data: dict):
    for metric in data.get("data") or []:
        total = (metric.get("total_value") or {}).get("value")
        if isinstance(total, int):
            return total
        for value in metric.get("values") or []:
            if isinstance(value.get("value"), int):
                return value["value"]
    return None


def parse_instagram_media(rows: list) -> list:
    items = []
    for row in rows or []:
        if not row.get("id") or row.get("media_type") not in ("VIDEO", "REELS", "CAROUSEL_ALBUM", "IMAGE"):
            continue
        caption = (row.get("caption") or "").strip()
        title = caption.split("\n", 1)[0][:120] if caption else "Publicación de Instagram"
        items.append({
            "platform": "instagram", "vid": str(row["id"]), "url": row.get("permalink"), "title": title,
            "published_at": _iso_ts(row.get("timestamp")), "views": row.get("views"), "likes": row.get("like_count"),
            "comments": row.get("comments_count"), "shares": None,
            "thumbnail": row.get("thumbnail_url") or (row.get("media_url") if row.get("media_type") == "IMAGE" else None),
            "source": "instagram", "is_video": row.get("media_type") == "VIDEO" or row.get("media_product_type") == "REELS",
        })
    return items


def fetch_instagram(token: str, limit: int = 25, session=None) -> list:
    session = session or make_session()
    fields = "id,caption,media_type,media_product_type,permalink,thumbnail_url,media_url,timestamp,like_count,comments_count"
    data = _ig_get(session, "me/media", {"fields": fields, "limit": limit, "access_token": token})
    items = parse_instagram_media(data.get("data") or [])
    for item in items[:limit]:
        if not item.pop("is_video", False):
            continue
        try:
            item["views"] = _insight_value(_ig_get(session, f"{item['vid']}/insights", {"metric": "views", "access_token": token}))
        except SourceError:
            pass
    for item in items:
        item.pop("is_video", None)
    return items


def refresh_instagram_token(token: str, session=None) -> str:
    """Los tokens de Instagram duran 60 días; renovándolo de vez en cuando no caduca nunca."""
    session = session or make_session()
    data = _ig_get(session, "refresh_access_token", {"grant_type": "ig_refresh_token", "access_token": token})
    return data.get("access_token") or token


# ---------- Enlaces sueltos ----------

_TT_PLAYS = (re.compile(r'"playCount":\s?(\d+)'),)
_YT_VIEWS = (
    re.compile(r'"viewCount":"(\d+)"'),
    re.compile(r'itemprop="interactionCount" content="(\d+)"'),
    re.compile(r'"originalViewCount":"(\d+)"'),
)


def preview(url: str) -> dict:
    """Título, autor, miniatura y (si la página lo deja ver) visualizaciones de un vídeo publicado."""
    platform = platform_of(url)
    out = {"url": url, "platform": platform, "title": None, "author": None, "thumbnail": None, "views": None}
    if platform not in ("youtube", "tiktok"):
        return out
    session = _session()
    endpoint = (YT_OEMBED if platform == "youtube" else TT_OEMBED).format(url=quote(url, safe=""))
    try:
        data = check(session.get(endpoint, timeout=TIMEOUT), "oEmbed").json()
        out.update(title=data.get("title"), author=data.get("author_name"), thumbnail=data.get("thumbnail_url"))
    except Exception:
        pass
    out["views"] = views_of(url, session)
    return out


def views_of(url: str, session=None):
    platform = platform_of(url)
    patterns = _TT_PLAYS if platform == "tiktok" else _YT_VIEWS if platform == "youtube" else ()
    if not patterns:
        return None
    session = session or _session()
    try:
        response = session.get(url, timeout=TIMEOUT)
        if response.status_code >= 400:
            return None
        for pattern in patterns:
            found = pattern.search(response.text)
            if found:
                return int(found.group(1))
    except Exception:
        return None
    return None


def status_line(platform: str, items: list, error: str = None) -> dict:
    return {"platform": platform, "ok": error is None, "count": len(items), "error": error, "checked_at": time.time()}
