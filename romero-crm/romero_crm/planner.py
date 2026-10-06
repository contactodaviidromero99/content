"""Calendario de producción: tus tareas (grabar, publicar…), tus vídeos publicados, las festividades y
los aniversarios que merecen un vídeo, juntos y día a día."""
from __future__ import annotations

import datetime as dt
import re
import time

from . import festivities
from .sources import efemerides as efem_source
from .storage import PLAN_KINDS, PLAN_PLATFORMS
from .text import tokens

KIND_LABELS = {"publicar": "Publicar", "grabar": "Grabar", "editar": "Editar", "guion": "Guion", "idea": "Idea", "otro": "Otro"}
_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_ID_RE = re.compile(r"^[0-9a-f]{6,32}$")


class InvalidItem(ValueError):
    pass


def _text(value, limit: int) -> str:
    text = "".join(c for c in str(value or "") if c.isprintable() or c == "\n")
    return text.strip()[:limit]


def _url(value) -> str:
    url = str(value or "").strip()
    return url[:500] if url.startswith(("https://", "http://")) else ""


def clean_item(data: dict, partial: bool = False) -> dict:
    """Valida lo que llega de la interfaz. Con partial=True solo se exigen los campos que vienen."""
    if not isinstance(data, dict):
        raise InvalidItem("Datos no válidos.")
    out = {}
    if data.get("id"):
        if not _ID_RE.match(str(data["id"])):
            raise InvalidItem("Identificador no válido.")
        out["id"] = str(data["id"])
    if "day" in data or not partial:
        day = str(data.get("day") or "")
        try:
            if not _DAY_RE.match(day):
                raise ValueError
            dt.date.fromisoformat(day)
        except ValueError:
            raise InvalidItem("Fecha no válida.") from None
        out["day"] = day
    if "time" in data:
        value = str(data.get("time") or "")
        out["time"] = value if _TIME_RE.match(value) else None
    if "kind" in data or not partial:
        kind = data.get("kind") or "publicar"
        if kind not in PLAN_KINDS:
            raise InvalidItem("Tipo de tarea no válido.")
        out["kind"] = kind
    if "title" in data or not partial:
        title = " ".join(_text(data.get("title"), 140).split())
        if not title:
            raise InvalidItem("Ponle un título a la tarea.")
        out["title"] = title
    if "notes" in data:
        out["notes"] = _text(data.get("notes"), 2000)
    if "platforms" in data:
        raw = data.get("platforms") or []
        out["platforms"] = [p for p in PLAN_PLATFORMS if p in raw] if isinstance(raw, list) else []
    if "done" in data:
        out["done"] = bool(data.get("done"))
    for field in ("topic_key", "topic_title"):
        if field in data:
            out[field] = _text(data.get(field), 200) or None
    if "links" in data:
        links = []
        for link in (data.get("links") or [])[:8] if isinstance(data.get("links"), list) else []:
            if not isinstance(link, dict) or not _url(link.get("url")):
                continue
            links.append({
                "url": _url(link["url"]),
                "platform": link.get("platform") if link.get("platform") in PLAN_PLATFORMS else platform_of(link["url"]),
                "title": _text(link.get("title"), 200) or None,
                "thumbnail": _url(link.get("thumbnail")) or None,
                "views": link.get("views") if isinstance(link.get("views"), int) else None,
            })
        out["links"] = links
    return out


def platform_of(url: str):
    host = re.sub(r"^https?://", "", (url or "").lower()).split("/")[0].split(":")[0]

    def on(domain):
        return host == domain or host.endswith("." + domain)

    if on("tiktok.com"):
        return "tiktok"
    if on("instagram.com"):
        return "instagram"
    if on("youtube.com") or on("youtu.be"):
        return "youtube"
    return None


def month_grid(month: str):
    """Primer y último día del mes y la rejilla completa de semanas (de lunes a domingo)."""
    try:
        first = dt.datetime.strptime(month, "%Y-%m").date()
    except (TypeError, ValueError):
        first = dt.date.today().replace(day=1)
    last = (first.replace(day=28) + dt.timedelta(days=4))
    last = last - dt.timedelta(days=last.day)
    start = first - dt.timedelta(days=first.weekday())
    end = last + dt.timedelta(days=6 - last.weekday())
    return first, last, start, end


def _local_day(ts) -> str:
    return dt.datetime.fromtimestamp(ts).date().isoformat()


def efemeride_reasons(item: dict) -> list:
    reasons = []
    if item.get("round_level", 0) >= 1:
        reasons.append(f"{item['years_ago']} años")
    if item.get("spain"):
        reasons.append("España")
    if item.get("kind") == "selected":
        reasons.append("Destacado")
    return reasons


def _efemerides_by_day(efem_result) -> dict:
    by_day = {}
    if not efem_result or not efem_result.ok:
        return by_day
    for day in efem_result.items or []:
        items = []
        for item in day.get("items") or []:
            entry = dict(item)
            entry["highlight"] = efem_source.is_highlight(item)
            entry["reasons"] = efemeride_reasons(item)
            items.append(entry)
        items.sort(key=lambda i: (not i["highlight"], -i["score"]))
        by_day[day["date"]] = items
    return by_day


def calendar_month(storage, efem_result, month: str, today: dt.date = None) -> dict:
    today = today or dt.date.today()
    first, last, start, end = month_grid(month)
    items = storage.plan_items(start.isoformat(), end.isoformat())
    start_ts = time.mktime(start.timetuple())
    end_ts = time.mktime((end + dt.timedelta(days=1)).timetuple())
    published = storage.published_between(start_ts, end_ts)
    fests = festivities.for_range(start, end)
    efems = _efemerides_by_day(efem_result)
    days = []
    cursor = start
    while cursor <= end:
        iso = cursor.isoformat()
        days.append({
            "date": iso,
            "in_month": cursor.month == first.month,
            "today": cursor == today,
            "past": cursor < today,
            "items": [i for i in items if i["day"] == iso],
            "published": [p for p in published if _local_day(p["published_at"]) == iso],
            "festivities": fests.get(iso, []),
            "efemerides": efems.get(iso, []),
        })
        cursor += dt.timedelta(days=1)
    covered = sorted(efems)
    return {
        "month": first.strftime("%Y-%m"),
        "first": first.isoformat(),
        "last": last.isoformat(),
        "today": today.isoformat(),
        "days": days,
        "efemerides_range": [covered[0], covered[-1]] if covered else None,
    }


def agenda(storage, today: dt.date = None) -> dict:
    """Lo que toca hoy y mañana, más lo que se quedó sin hacer en los últimos días."""
    today = today or dt.date.today()
    tomorrow = today + dt.timedelta(days=1)
    rows = storage.plan_items((today - dt.timedelta(days=7)).isoformat(), (today + dt.timedelta(days=7)).isoformat())
    return {
        "today": [r for r in rows if r["day"] == today.isoformat()],
        "tomorrow": [r for r in rows if r["day"] == tomorrow.isoformat()],
        "overdue": [r for r in rows if r["day"] < today.isoformat() and not r["done"] and r["kind"] != "idea"],
        "next": [r for r in rows if r["day"] > tomorrow.isoformat() and not r["done"]][:5],
    }


def _similar(plan_title: str, video_title: str) -> bool:
    wanted = set(tokens(plan_title))
    found = set(tokens(video_title))
    if not wanted or not found:
        return False
    return len(wanted & found) / len(wanted) >= 0.6


def auto_match(storage, days_back: int = 21) -> int:
    """Marca como hechas las tareas «Publicar» cuando aparece un vídeo tuyo con ese título ese día o el siguiente."""
    today = dt.date.today()
    since = today - dt.timedelta(days=days_back)
    pending = [i for i in storage.plan_items(since.isoformat(), today.isoformat()) if i["kind"] == "publicar" and not i["done"]]
    if not pending:
        return 0
    videos = storage.published_between(time.mktime(since.timetuple()), time.time() + 86400)
    matched = 0
    for item in pending:
        day = dt.date.fromisoformat(item["day"])
        hits = [v for v in videos if v.get("published_at") and abs((dt.date.fromtimestamp(v["published_at"]) - day).days) <= 1
                and _similar(item["title"], v.get("title") or "")]
        if not hits:
            continue
        links = list(item.get("links") or [])
        known = {link["url"] for link in links}
        for video in hits:
            if video.get("url") and video["url"] not in known:
                links.append({"url": video["url"], "platform": video["platform"], "title": video.get("title"),
                              "thumbnail": video.get("thumbnail"), "views": video.get("views")})
        platforms = sorted(set(item.get("platforms") or []) | {v["platform"] for v in hits})
        storage.save_plan_item({"id": item["id"], "done": True, "links": links[:8], "platforms": platforms})
        matched += 1
    return matched


ROUND_POINTS = {1: 0, 2: 8, 3: 18, 4: 28}
# Un acontecimiento da más vídeo que un cumpleaños: «50 años del atentado de…» antes que «X cumpliría 50».
KIND_POINTS = {"selected": 25, "events": 15, "deaths": 5, "births": -10}


def worth_a_video(item: dict) -> bool:
    """Aniversarios que merecen un vídeo: acontecimientos españoles con cifra redonda y nacimientos o muertes
    españoles de 50 o 100 años; de fuera, solo acontecimientos de 50 o 100 años y personas centenarias."""
    level = item.get("round_level", 0)
    if not item.get("highlight", True) or level < 1:
        return False
    people = item.get("kind") in ("births", "deaths")
    if item.get("spain"):
        return level >= 3 if people else (level >= 2 or item.get("kind") == "selected")
    return level >= 4 if people else level >= 3


def efemeride_title(item: dict) -> str:
    """Para personas, su nombre; para acontecimientos, el propio hecho (el título de la página sería
    «Barbados» para el atentado contra el vuelo 455 de Cubana, y eso no dice nada)."""
    if item.get("kind") in ("births", "deaths") and item.get("title"):
        return item["title"]
    text = (item.get("text") or "").strip().rstrip(".")
    text = text[:1].upper() + text[1:]
    if len(text) <= 80:
        return text
    cut = text[:78].rsplit(" ", 1)[0].rstrip(",;:")
    return cut + "…"


def horizon(efem_result, today: dt.date = None, days: int = 21, limit: int = 8, max_world: int = 2) -> list:
    """Lo que viene en las próximas semanas y merece un vídeo: festividades con historia y aniversarios
    redondos. Primero lo español; de fuera, como mucho `max_world`, y solo lo más grande."""
    today = today or dt.date.today()
    end = today + dt.timedelta(days=days)
    candidates = []
    for iso, items in festivities.for_range(today, end).items():
        for fest in items:
            if fest["idea"] or fest["kind"] in ("nacional", "aviso"):
                points = 90 if fest["kind"] == "nacional" else 75 if fest["idea"] else 60
                candidates.append((points, {"date": iso, "type": "fest", "title": fest["name"], "sub": fest["kind_label"],
                                            "idea": fest["idea"], "kind": fest["kind"], "spain": fest["spain"]}))
    for iso, items in _efemerides_by_day(efem_result).items():
        if not today.isoformat() <= iso <= end.isoformat():
            continue
        for item in items:
            if not worth_a_video(item):
                continue
            points = ROUND_POINTS.get(item["round_level"], 0) + KIND_POINTS.get(item["kind"], 0) + (25 if item.get("spain") else 0)
            candidates.append((points, {"date": iso, "type": "efem", "title": efemeride_title(item), "kind": item["kind"],
                                        "sub": item["text"], "years": item["years_ago"], "spain": item.get("spain"),
                                        "url": item.get("url"), "reasons": efemeride_reasons(item)}))
    candidates.sort(key=lambda c: (-c[0], c[1]["date"]))
    chosen, world, seen = [], 0, set()
    for points, entry in candidates:
        ident = (entry["date"], entry["title"])
        if ident in seen:
            continue
        if entry["type"] == "efem" and not entry["spain"]:
            if world >= max_world:
                continue
            world += 1
        seen.add(ident)
        chosen.append(dict(entry, points=points))
        if len(chosen) >= limit:
            break
    chosen.sort(key=lambda h: (h["date"], h["type"] != "fest"))
    return chosen
