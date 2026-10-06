"""El historial en un vistazo: cada semana resumida en el tema estrella, los nichos que subieron, el tema
de cada día, cuándo arrancan las tendencias y lo que publicaste tú."""
from __future__ import annotations

import datetime as dt
import statistics
import time
from collections import Counter, defaultdict

from .niches import NICHE_NAMES, is_utility
from .stories import is_routine
from .text import norm

WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def week_bounds(offset: int, today: dt.date) -> tuple:
    start = today - dt.timedelta(days=today.weekday()) - dt.timedelta(weeks=offset)
    return start, start + dt.timedelta(days=6)


def _ts(day: dt.date) -> float:
    return time.mktime(day.timetuple())


def _worth(title: str, niche: str) -> bool:
    return bool(title) and not is_utility(title) and not is_routine(title, niche or "")


def _story_rows(storage, start: dt.date, end: dt.date, google_rows: list) -> list:
    """Historias guardadas cada día más las tendencias de Google de esos días (que llegan aunque el
    programa no estuviera abierto): juntas dan la foto completa de la semana."""
    rows = [r for r in storage.story_day_rows(start.isoformat(), end.isoformat()) if _worth(r.get("title"), r.get("niche"))]
    if not rows:
        for row in storage.topic_day_rows(start.isoformat()):
            if row["day"] > end.isoformat() or not _worth(row.get("title"), row.get("niche")):
                continue
            rows.append({"day": row["day"], "key": row["key"], "title": row["title"], "niche": row.get("niche"),
                         "scope": None, "members": [], "why": None, "peak_heat": row.get("peak_heat"),
                         "peak_volume": row.get("peak_volume"), "yt_count": None, "yt_top": None, "yt_top_title": None})
    for row in google_rows:
        day = dt.date.fromtimestamp(row["started"])
        if start <= day <= end and _worth(row.get("title"), row.get("niche")):
            rows.append({"day": day.isoformat(), "key": row["id"], "title": row["title"], "niche": row.get("niche"),
                         "scope": None, "members": [], "why": None, "peak_heat": None, "peak_volume": row.get("volume"),
                         "yt_count": None, "yt_top": None, "yt_top_title": None})
    return rows


def _aggregate(rows: list) -> list:
    groups = {}
    for row in rows:
        ident = norm(row.get("title") or row["key"])
        entry = groups.setdefault(ident, {"key": row["key"], "title": row["title"], "niches": Counter(), "days": set(),
                                          "volume": 0, "heat": 0, "yt_count": 0, "yt_top": 0, "yt_top_title": None,
                                          "members": [], "why": None, "scope": row.get("scope")})
        entry["niches"][row.get("niche") or "otros"] += 1
        entry["days"].add(row["day"])
        entry["volume"] = max(entry["volume"], row.get("peak_volume") or 0)
        entry["heat"] = max(entry["heat"], row.get("peak_heat") or 0)
        entry["yt_count"] = max(entry["yt_count"], row.get("yt_count") or 0)
        if (row.get("yt_top") or 0) > entry["yt_top"]:
            entry["yt_top"], entry["yt_top_title"] = row["yt_top"], row.get("yt_top_title")
        for member in row.get("members") or []:
            if member not in entry["members"] and len(entry["members"]) < 6:
                entry["members"].append(member)
        entry["why"] = entry["why"] or row.get("why")
    out = []
    for entry in groups.values():
        niche = entry["niches"].most_common(1)[0][0]
        out.append({
            "key": entry["key"], "title": entry["title"], "niche": niche, "niche_name": NICHE_NAMES.get(niche, niche),
            "days": len(entry["days"]), "volume": entry["volume"], "heat": round(entry["heat"]),
            "yt_count": entry["yt_count"] or None, "yt_top": entry["yt_top"] or None, "yt_top_title": entry["yt_top_title"],
            "members": entry["members"], "why": entry["why"], "scope": entry["scope"],
        })
    out.sort(key=lambda s: (-(s["volume"] or 0), -s["heat"], -s["days"]))
    return out


def _niche_shares(rows: list) -> tuple:
    counts = Counter(r.get("niche") or "otros" for r in rows if not is_utility(r.get("query") or r.get("title") or ""))
    return counts, sum(counts.values())


def _best_window(hours: list):
    if not any(hours):
        return None
    best = max(range(24), key=lambda h: hours[h] + hours[(h + 1) % 24])
    return {"start": best, "end": (best + 2) % 24}


def weekly(storage, offset: int = 0, now: float = None) -> dict:
    now = now or time.time()
    today = dt.date.fromtimestamp(now)
    offset = max(0, min(int(offset), 25))
    start, end = week_bounds(offset, today)
    prev_start, prev_end = week_bounds(offset + 1, today)

    google = [r for r in storage.google_rows(_ts(prev_start) - 86400) if r.get("started")]
    this_week = [r for r in google if start <= dt.date.fromtimestamp(r["started"]) <= end]
    last_week = [r for r in google if prev_start <= dt.date.fromtimestamp(r["started"]) <= prev_end]
    week_rows = _story_rows(storage, start, end, this_week)
    stories = _aggregate(week_rows)

    counts, total = _niche_shares(this_week)
    prev_counts, prev_total = _niche_shares(last_week)
    star_by_niche = {}
    for story in stories:
        star_by_niche.setdefault(story["niche"], story)
    niches = []
    for niche, count in counts.most_common():
        if niche == "otros":
            continue
        share = count / total * 100 if total else 0
        prev_share = prev_counts.get(niche, 0) / prev_total * 100 if prev_total else None
        star = star_by_niche.get(niche) or {}
        niches.append({
            "id": niche, "name": NICHE_NAMES.get(niche, niche), "count": count, "share": round(share, 1),
            "delta": round(share - prev_share, 1) if prev_share is not None else None,
            "star": {"title": star.get("title"), "volume": star.get("volume")} if star else None,
        })

    days = []
    by_day = defaultdict(list)
    for story_row in week_rows:
        by_day[story_row["day"]].append(story_row)
    google_by_day = Counter(dt.date.fromtimestamp(r["started"]).isoformat() for r in this_week)
    for index in range(7):
        day = start + dt.timedelta(days=index)
        iso = day.isoformat()
        top = sorted(by_day.get(iso, []), key=lambda r: (-(r.get("peak_volume") or 0), -(r.get("peak_heat") or 0)))
        days.append({
            "day": iso, "weekday": WEEKDAYS[index], "future": day > today, "count": google_by_day.get(iso, 0),
            "top": {"title": top[0]["title"], "niche": top[0].get("niche"), "volume": top[0].get("peak_volume"),
                    "heat": round(top[0].get("peak_heat") or 0)} if top else None,
        })

    hours = [0] * 24
    for row in this_week:
        hours[dt.datetime.fromtimestamp(row["started"]).hour] += 1

    durations = defaultdict(list)
    for row in google:
        if row.get("ended") and row["ended"] > row["started"]:
            length = (row["ended"] - row["started"]) / 3600
            if 0.25 <= length <= 96:
                durations[row.get("niche") or "otros"].append(length)
    lifetimes = sorted(({"id": n, "name": NICHE_NAMES.get(n, n), "median": round(statistics.median(v), 1)}
                        for n, v in durations.items() if len(v) >= 3 and n != "otros"), key=lambda d: d["median"])
    every = [x for values in durations.values() for x in values]

    week_ts = (_ts(start), _ts(end + dt.timedelta(days=1)))
    published = storage.published_between(*week_ts)
    done = [i for i in storage.plan_items(start.isoformat(), end.isoformat()) if i["done"]]

    oldest = storage.oldest_day()
    weeks_available = 0
    if oldest:
        weeks_available = max(0, (week_bounds(0, today)[0] - week_bounds(0, dt.date.fromisoformat(oldest))[0]).days // 7)

    label = "Esta semana" if offset == 0 else "La semana pasada" if offset == 1 else f"Hace {offset} semanas"
    return {
        "week": {"offset": offset, "start": start.isoformat(), "end": end.isoformat(), "label": label,
                 "weeks_available": weeks_available, "trends": total},
        "star": stories[0] if stories else None,
        "top": stories[1:6],
        "niches": niches[:7],
        "days": days,
        "hours": hours,
        "best_window": _best_window(hours),
        "lifetimes": lifetimes,
        "lifetime_all": round(statistics.median(every), 1) if len(every) >= 3 else None,
        "mine": {
            "published": [{"platform": p["platform"], "title": p.get("title"), "url": p.get("url"), "views": p.get("views"),
                           "published_at": p.get("published_at"), "thumbnail": p.get("thumbnail")} for p in published],
            "done": [{"title": i["title"], "kind": i["kind"], "day": i["day"]} for i in done],
        },
    }
