from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path

from ..net import APP_UA, TIMEOUT, SourceError, check, make_session
from ..niches import classify
from ..text import norm
from .base import SourceResult, failure

URLS = (
    "https://es.wikipedia.org/api/rest_v1/feed/onthisday/all/{m:02d}/{d:02d}",
    "https://api.wikimedia.org/feed/v1/wikipedia/es/onthisday/all/{m:02d}/{d:02d}",
)
CACHE_DAYS = 30
SPAIN_TERMS = {
    "espana", "espanol", "espanola", "espanoles", "madrid", "barcelona", "sevilla", "valencia", "castilla",
    "aragon", "cataluna", "andalucia", "galicia", "navarra", "granada", "toledo", "cadiz", "malaga",
    "bilbao", "zaragoza", "cordoba", "salamanca", "valladolid", "burgos", "leon", "asturias", "extremadura",
    "reyes catolicos", "franco", "guerra civil espanola", "segunda republica", "transicion", "al andalus",
}
KIND_LABELS = {"selected": "Destacado", "events": "Acontecimiento", "births": "Nacimiento", "deaths": "Fallecimiento"}


def round_level(years: int) -> int:
    if years <= 0:
        return 0
    if years % 100 == 0:
        return 4
    if years % 50 == 0:
        return 3
    if years % 25 == 0:
        return 2
    if years % 10 == 0 and years <= 100:
        return 1
    return 0


def is_highlight(item: dict) -> bool:
    if item["kind"] in ("births", "deaths"):
        return item["round_level"] >= 3 or (item["round_level"] >= 2 and item["spain"])
    return item["round_level"] >= 2 or (item["round_level"] >= 1 and item["spain"])


def pick_highlights(days: list, per_day: int = 3) -> list:
    chosen = []
    for day in days:
        candidates = sorted((i for i in day["items"] if is_highlight(i)), key=lambda i: -i["score"])
        chosen.extend(candidates[:per_day])
    chosen.sort(key=lambda i: (i["date"], -i["score"]))
    return chosen


def is_spanish(text: str) -> bool:
    words = f" {norm(text)} "
    return any(f" {term} " in words for term in SPAIN_TERMS)


def _cache_path(cache_dir: Path, month: int, day: int) -> Path:
    return cache_dir / f"onthisday-{month:02d}-{day:02d}.json"


def fetch_day(session, month: int, day: int, cache_dir: Path) -> dict:
    path = _cache_path(cache_dir, month, day)
    if path.exists() and time.time() - path.stat().st_mtime < CACHE_DAYS * 86400:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    last_error = None
    for template in URLS:
        for attempt in range(2):
            try:
                response = session.get(template.format(m=month, d=day), timeout=TIMEOUT)
                if response.status_code == 429 and attempt == 0:
                    time.sleep(5)
                    continue
                check(response, "Wikipedia (efemérides)")
                data = response.json()
                path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                return data
            except Exception as exc:
                last_error = exc
                break
    raise last_error or SourceError("Sin efemérides")


def build_items(day_data: dict, target: dt.date) -> list:
    items = []
    for kind in ("selected", "events", "births", "deaths"):
        for entry in day_data.get(kind) or []:
            year = entry.get("year")
            text = (entry.get("text") or "").strip()
            if not isinstance(year, int) or not text:
                continue
            years = target.year - year
            level = round_level(years)
            if kind in ("births", "deaths") and level < 2:
                continue
            pages = entry.get("pages") or []
            page = pages[0] if pages else {}
            titles = page.get("titles") or {}
            description = page.get("description") or ""
            spanish = is_spanish(text + " " + description)
            score = level * 10 + (5 if kind == "selected" else 0) + (4 if spanish else 0) + min(len(pages), 3)
            items.append({
                "date": target.isoformat(),
                "year": year,
                "years_ago": years,
                "round_level": level,
                "kind": kind,
                "kind_label": KIND_LABELS[kind],
                "text": text,
                "title": titles.get("normalized") or page.get("normalizedtitle") or page.get("title", "").replace("_", " "),
                "description": description,
                "extract": (page.get("extract") or "")[:400],
                "thumbnail": (page.get("thumbnail") or {}).get("source"),
                "url": ((page.get("content_urls") or {}).get("desktop") or {}).get("page"),
                "spain": spanish,
                "niche": classify(text, description=description)[0],
                "score": score,
            })
    unique, seen = [], set()
    for item in sorted(items, key=lambda i: -i["score"]):
        ident = (item["year"], item["title"] or item["text"][:40])
        if ident in seen:
            continue
        seen.add(ident)
        unique.append(item)
    return unique


def fetch(cache_dir: Path, days: int = 30, today: dt.date = None, budget_s: float = 20.0) -> SourceResult:
    session = make_session(APP_UA, retry_rate_limit=False)
    today = today or dt.date.today()
    all_days, errors, partial = [], [], False
    started = time.monotonic()
    for offset in range(days):
        target = today + dt.timedelta(days=offset)
        cached = _cache_path(cache_dir, target.month, target.day).exists()
        if not cached and offset > 0 and time.monotonic() - started > budget_s:
            partial = True
            continue
        try:
            data = fetch_day(session, target.month, target.day, cache_dir)
            all_days.append({"date": target.isoformat(), "items": build_items(data, target)[:12]})
        except Exception as exc:
            errors.append(f"{target.isoformat()}: {exc}")
            if offset == 0:
                return failure("efemerides", exc)
            if "429" in str(exc):
                break
        if not cached:
            time.sleep(1.0)
    return SourceResult(
        source="efemerides",
        ok=True,
        items=all_days,
        meta={"highlights": pick_highlights(all_days)[:40], "errors": errors[:3], "partial": partial},
    )
