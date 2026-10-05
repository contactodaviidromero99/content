from __future__ import annotations

import datetime as dt
import time
from urllib.parse import quote

from ..net import APP_UA, TIMEOUT, SourceError, check, make_session
from ..text import key
from .base import SourceResult, failure

TOP_COUNTRY_URL = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top-per-country/ES/all-access/{y}/{m:02d}/{d:02d}"
DAYS = 8
TOP_N = 60
_NAMESPACES = {
    "special", "especial", "wikipedia", "archivo", "file", "ayuda", "help", "usuario", "user", "plantilla",
    "template", "categoria", "categoría", "category", "portal", "talk", "discusion", "discusión", "media",
    "mediawiki", "modulo", "módulo", "module", "fitxer", "fitxategi", "viquipèdia", "wikiproyecto",
}
_MAIN_PAGES = {"main_page", "portada", "wikipedia:portada", "pàgina_principal", "azala", "portada_galega", "-"}
PROJECTS = {"es.wikipedia", "ca.wikipedia", "gl.wikipedia", "eu.wikipedia", "ast.wikipedia", "en.wikipedia"}
_NOISE = {"cookie_(informatique)", "http_cookie", "cookie_http", "cookie_(informática)", "galleta_informática", "xxx", "xnxx", "xvideos", "pornhub"}


def is_article(title: str) -> bool:
    if not title or title.lower() in _MAIN_PAGES or title.lower() in _NOISE:
        return False
    if ":" in title:
        prefix = title.split(":", 1)[0].lower()
        if prefix in _NAMESPACES:
            return False
    return True


def parse_top_per_country(payload: dict) -> list:
    items = (payload or {}).get("items") or []
    if not items:
        return []
    out = []
    for row in items[0].get("articles") or []:
        project = str(row.get("project", ""))
        article = str(row.get("article", ""))
        if project not in PROJECTS or not is_article(article):
            continue
        views = row.get("views_ceil", row.get("views"))
        out.append({"project": project, "article": article, "views": int(views or 0), "rank": row.get("rank")})
    return out


def _day_list(session, day: dt.date):
    url = TOP_COUNTRY_URL.format(y=day.year, m=day.month, d=day.day)
    response = session.get(url, timeout=TIMEOUT)
    if response.status_code == 404:
        return None
    check(response, "Wikipedia")
    return parse_top_per_country(response.json())


def _lang(project: str) -> str:
    return project.split(".", 1)[0]


def fetch_descriptions(session, project: str, articles: list) -> dict:
    lang = _lang(project)
    result = {}
    for start in range(0, len(articles), 50):
        chunk = articles[start:start + 50]
        params = {
            "action": "query", "format": "json", "formatversion": "2", "redirects": "1",
            "prop": "description|pageimages", "piprop": "thumbnail", "pithumbsize": "240",
            "titles": "|".join(a.replace("_", " ") for a in chunk),
        }
        response = check(session.get(f"https://{lang}.wikipedia.org/w/api.php", params=params, timeout=TIMEOUT), "Wikipedia")
        query = response.json().get("query") or {}
        alias = {}
        for mapping in (query.get("normalized") or []) + (query.get("redirects") or []):
            alias[mapping.get("from")] = mapping.get("to")
        pages = {p.get("title"): p for p in query.get("pages") or []}
        for article in chunk:
            title = article.replace("_", " ")
            seen = set()
            while title in alias and title not in seen:
                seen.add(title)
                title = alias[title]
            page = pages.get(title) or {}
            result[article] = {
                "description": page.get("description"),
                "thumbnail": (page.get("thumbnail") or {}).get("source"),
            }
    return result


def build_items(days: list, descriptions: dict) -> list:
    latest_day, latest = days[0]
    previous = {(r["project"], r["article"]): r["views"] for r in days[1][1]} if len(days) > 1 else {}
    history = [{(r["project"], r["article"]): r["views"] for r in rows} for _, rows in days]
    items = []
    for rank, row in enumerate(latest[:TOP_N], 1):
        ident = (row["project"], row["article"])
        prev = previous.get(ident)
        change = ((row["views"] - prev) / prev * 100.0) if prev else None
        title = row["article"].replace("_", " ")
        info = descriptions.get(ident, {})
        series = [float(h.get(ident, 0)) for h in reversed(history)]
        items.append({
            "id": key(title),
            "title": title,
            "project": row["project"],
            "lang": _lang(row["project"]),
            "views": row["views"],
            "rank": rank,
            "previous_views": prev,
            "change_pct": change,
            "is_new": bool(previous) and prev is None,
            "days_in_top": sum(1 for h in history if ident in h),
            "description": info.get("description"),
            "thumbnail": info.get("thumbnail"),
            "series": series,
            "series_step": 86400,
            "day": latest_day.isoformat(),
            "url": f"https://{row['project']}.org/wiki/{quote(row['article'])}",
        })
    return items


_DESC_CACHE = {}


def _describe(session, rows: list, errors: list) -> None:
    if len(_DESC_CACHE) > 5000:
        _DESC_CACHE.clear()
    by_project = {}
    for row in rows:
        if (row["project"], row["article"]) not in _DESC_CACHE:
            by_project.setdefault(row["project"], []).append(row["article"])
    for project, articles in by_project.items():
        for attempt in range(2):
            try:
                for article, info in fetch_descriptions(session, project, articles).items():
                    _DESC_CACHE[(project, article)] = info
                break
            except Exception as exc:
                if attempt == 0:
                    time.sleep(2.5)
                else:
                    errors.append(f"descripciones {project}: {exc}")


def fetch(today: dt.date = None) -> SourceResult:
    session = make_session(APP_UA)
    today = today or dt.datetime.now(dt.timezone.utc).date()
    days = []
    try:
        for offset in range(1, DAYS + 4):
            if len(days) >= DAYS:
                break
            cursor = today - dt.timedelta(days=offset)
            rows = _day_list(session, cursor)
            if rows is None and days:
                break
            if rows:
                days.append((cursor, rows))
        if not days:
            raise SourceError("Wikipedia aún no ha publicado los datos de ayer.")
        errors = []
        _describe(session, days[0][1][:TOP_N], errors)
        items = build_items(days, _DESC_CACHE)
    except Exception as exc:
        return failure("wikipedia", exc)
    meta = {
        "day": days[0][0].isoformat(),
        "days": len(days),
        "described": sum(1 for i in items if i.get("description")),
        "errors": errors[:3],
    }
    return SourceResult(source="wikipedia", ok=True, items=items, meta=meta)
