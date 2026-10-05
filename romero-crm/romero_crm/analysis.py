from __future__ import annotations

import datetime as dt
import math
import re
import statistics
import time
from collections import Counter, defaultdict

from .explain import explain
from .niches import NICHE_NAMES, NICHE_ORDER, NICHES, classify, is_utility
from .text import GENERIC_TOKENS, STOPWORDS, casing_map, fmt_number, key, norm, recase, split_hashtag, strip_accents, tokens

SOURCE_ORDER = ("google", "youtube", "x", "wikipedia", "news")
PHASE_LABELS = {
    "explosivo": "Explosivo",
    "subiendo": "En ascenso",
    "temprana": "Señal temprana",
    "pico": "En pico",
    "enfriandose": "Enfriándose",
}
PHASE_WEIGHT = {"explosivo": 1.0, "subiendo": 0.85, "temprana": 0.75, "pico": 0.55, "enfriandose": 0.25}
DEFAULT_LIFETIME_H = 20.0
SERIES_LABELS = {
    "google_volume": "Búsquedas acumuladas en Google · registro de Romero CRM",
    "x": "Posición en tendencias de X · últimas horas",
    "wikipedia": "Lecturas en Wikipedia desde España · últimos días",
}


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def percentiles(values: dict) -> dict:
    present = [(v, k) for k, v in values.items() if v is not None]
    if not present:
        return {}
    present.sort()
    n = len(present)
    out, index = {}, 0
    while index < n:
        end = index
        while end + 1 < n and present[end + 1][0] == present[index][0]:
            end += 1
        pct = ((index + end) / 2 + 1) / n
        for j in range(index, end + 1):
            out[present[j][1]] = pct
        index = end + 1
    return out


VOLUME_BUCKETS = (100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000,
                  1000000, 2000000, 5000000, 10000000)
VOLUME_STEP_SECONDS = 3600
RECENT_WINDOW_H = 2.0


def bucket_index(volume) -> int:
    return sum(1 for floor in VOLUME_BUCKETS[1:] if (volume or 0) >= floor)


def attach_volume_history(items: list, snapshots: list, now: float, hours: int = 24) -> None:
    by_trend = defaultdict(list)
    for row in snapshots:
        by_trend[(row["id"], row["started"])].append((row["ts"], row["volume"] or 0))
    for item in items:
        points = sorted(by_trend.get((item["id"], item.get("started_at") or 0), []))
        item["volume_trend"] = volume_trend(points, now)
        item["volume_series"] = volume_series(points, now, hours)


def volume_trend(points: list, now: float):
    points = [(ts, v) for ts, v in points if v]
    if len(points) < 2 or points[-1][0] - points[0][0] < 900:
        return None
    changes, best = [], 0
    for ts, volume in points:
        if volume > best:
            if best:
                changes.append((ts, best, volume))
            best = volume
    recent = [c for c in changes if now - c[0] <= RECENT_WINDOW_H * 3600]
    last_change = changes[-1][0] if changes else points[0][0]
    return {
        "watched_hours": round((now - points[0][0]) / 3600, 2),
        "current": best,
        "from": recent[0][1] if recent else None,
        "recent_steps": sum(bucket_index(new) - bucket_index(old) for _, old, new in recent),
        "stalled_hours": round((now - last_change) / 3600, 2),
        "changes": len(changes),
    }


def volume_series(points: list, now: float, hours: int = 24) -> list:
    points = [(ts, v) for ts, v in points if v]
    if not points:
        return []
    span = min(hours, int((now - points[0][0]) // VOLUME_STEP_SECONDS))
    if span < 2:
        return []
    out = []
    for back in range(span, -1, -1):
        cutoff = now - back * VOLUME_STEP_SECONDS
        seen = [v for ts, v in points if ts <= cutoff]
        out.append(float(max(seen)) if seen else 0.0)
    return out


class _Entry:
    __slots__ = ("source", "item", "key", "tokens", "related")

    def __init__(self, source: str, item: dict):
        title = item.get("query") or item.get("name") or item.get("title") or ""
        self.source = source
        self.item = item
        self.key = key(title)
        self.tokens = set(tokens(title))
        self.related = {key(r) for r in item.get("related") or []} if source == "google" else set()


def _match(a: _Entry, b: _Entry) -> bool:
    if a.key and a.key == b.key:
        return True
    if a.source == b.source:
        return False
    if a.source == "google" and b.key in a.related:
        return True
    if b.source == "google" and a.key in b.related:
        return True
    if a.tokens and b.tokens:
        small, big = (a.tokens, b.tokens) if len(a.tokens) <= len(b.tokens) else (b.tokens, a.tokens)
        if len(small) >= 2 and small <= big:
            return True
        if len(small) == 1:
            (token,) = tuple(small)
            if len(token) >= 6 and token not in GENERIC_TOKENS and token in big and len(big) <= 4:
                return True
    short, long_ = sorted((a.key, b.key), key=len)
    return len(short) >= 8 and short in long_ and len(short) >= 0.6 * len(long_)


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def _headline_index(news_items: list) -> list:
    index = []
    for item in news_items:
        index.append((set(tokens(item["title"])), key(item["title"]), item))
    return index


def _headline_match(token_sets: list, keys: list, headline_tokens: set, headline_key: str) -> bool:
    for token_set in token_sets:
        if len(token_set) >= 2 and token_set <= headline_tokens:
            return True
        if len(token_set) == 1:
            (token,) = tuple(token_set)
            if len(token) >= 6 and token not in GENERIC_TOKENS and token in headline_tokens:
                return True
    return any(len(k) >= 8 and k in headline_key for k in keys)


def lifecycle_stats(google_rows: list) -> dict:
    durations = defaultdict(list)
    for row in google_rows:
        started, ended = row.get("started"), row.get("ended")
        if started and ended and ended > started:
            hours = (ended - started) / 3600.0
            if 0.25 <= hours <= 96:
                durations[row.get("niche") or "otros"].append(hours)
                durations["_all"].append(hours)
    stats = {}
    for niche, values in durations.items():
        if len(values) >= 3:
            stats[niche] = {"median": round(statistics.median(values), 1), "count": len(values)}
    return stats


def typical_lifetime(lifecycle: dict, niche: str) -> float:
    for candidate in (niche, "_all"):
        info = lifecycle.get(candidate)
        if info and info.get("count", 0) >= (5 if candidate != "_all" else 3):
            return float(info["median"])
    return DEFAULT_LIFETIME_H


def _phase(topic: dict, now: float):
    google, x, wiki = topic.get("google"), topic.get("x"), topic.get("wikipedia")
    elapsed = topic.get("elapsed_hours")
    if google:
        if not google.get("active"):
            return "enfriandose", "Google ya la da por terminada."
        growth = google.get("growth_pct") or 0
        volume = google.get("volume") or 0
        trend = google.get("volume_trend")
        since = f"hace {_hours_text(elapsed)}" if elapsed is not None else "hace poco"
        stalled = trend and trend["watched_hours"] >= 2 and trend["stalled_hours"] >= 2
        if trend and trend["recent_steps"]:
            climb = f"de {fmt_number(trend['from'])}+ a {fmt_number(trend['current'])}+ búsquedas"
            young = elapsed is not None and elapsed <= 3
            if trend["recent_steps"] >= 2 or young:
                prefix = f"Arrancó {since} y ha pasado" if young else "Ha pasado"
                return "explosivo", f"{prefix} {climb} en menos de 2 h."
            return "subiendo", f"Ha subido {climb} en las últimas 2 h."
        if elapsed is not None and elapsed <= 4 and volume <= 5000 and growth >= 500 and len(topic["sources"]) <= 1 and not stalled:
            return "temprana", f"Aún pequeño ({fmt_number(volume)}+ búsquedas), pero crece un {_pct(growth)} % desde {since}: puede despegar."
        if stalled:
            return "pico", f"Lleva {_hours_text(trend['stalled_hours'])} estable en {fmt_number(volume)}+ búsquedas; empezó {since}."
        if elapsed is not None and elapsed <= 6 and growth >= 500:
            return "explosivo", f"Arrancó {since} y ya crece un {_pct(growth)} %."
        if elapsed is not None and elapsed <= 12:
            return "subiendo", f"Tendencia activa que empezó {since}."
        return "pico", f"Tendencia activa desde {since}."
    if x:
        if x.get("is_new") and x.get("rank", 99) <= 15:
            return ("temprana" if len(topic["sources"]) <= 1 else "explosivo"), "Acaba de entrar en las tendencias de X."
        change = x.get("rank_change")
        if change and change > 0:
            return "subiendo", f"Sube {change} puestos en X en la última hora."
        if change and change < 0:
            return "enfriandose", f"Baja {abs(change)} puestos en X en la última hora."
        return "pico", "Se mantiene en las tendencias de X."
    if wiki:
        change = wiki.get("change_pct")
        if wiki.get("is_new"):
            return "subiendo", "Entra hoy en lo más leído desde España."
        if change is not None and change >= 100:
            return "subiendo", "Las lecturas se han más que duplicado respecto al día anterior."
        if change is not None and change <= -30:
            return "enfriandose", "Las lecturas bajan respecto al día anterior."
        return "pico", "Lecturas estables en lo más leído."
    return "pico", ""


def _hours_text(hours: float) -> str:
    if hours < 1:
        return f"{max(1, int(round(hours * 60)))} min"
    if hours < 10:
        return f"{hours:.1f}".rstrip("0").rstrip(".").replace(".", ",") + " h"
    return f"{hours:.0f} h"


def _pct(value) -> str:
    return f"{float(value):,.0f}".replace(",", ".") if abs(float(value)) >= 10000 else f"{float(value):.0f}"


def _signals(topic: dict) -> list:
    out = []
    google, x, wiki, news = (topic.get(s) for s in ("google", "x", "wikipedia", "news"))
    if google:
        text = f"{fmt_number(google.get('volume'))}+ búsquedas en Google"
        if google.get("growth_pct"):
            text += f" (+{_pct(google['growth_pct'])} %)"
        out.append({"source": "google", "text": text})
    if x:
        text = f"Nº {x['rank']} en tendencias de X"
        if x.get("hours_in_trends", 0) > 1:
            text += f" · lleva {x['hours_in_trends']} h"
        if x.get("volume"):
            text += f" · {fmt_number(x['volume'])} posts"
        out.append({"source": "x", "text": text})
    if wiki:
        text = f"{fmt_number(wiki['views'])} lecturas en Wikipedia desde España"
        if wiki.get("change_pct") is not None:
            sign = "+" if wiki["change_pct"] >= 0 else "−"
            text += f" ({sign}{_pct(abs(wiki['change_pct']))} % vs. día anterior)"
        out.append({"source": "wikipedia", "text": text})
    if news and news.get("count"):
        outlets = news.get("outlets") or 1
        text = f"Lo cuentan {outlets} medios españoles" if outlets > 1 else "Lo cuenta 1 medio español"
        out.append({"source": "news", "text": text})
    return out




def build_topics(results: dict, lifecycle: dict, now: float = None) -> list:
    now = now or time.time()
    entries = []
    for source in ("google", "x", "wikipedia"):
        result = results.get(source)
        if result and result.ok:
            for item in result.items:
                entries.append(_Entry(source, item))

    finder = _UnionFind(len(entries))
    by_key = defaultdict(list)
    for index, entry in enumerate(entries):
        if entry.key:
            by_key[entry.key].append(index)
    for indices in by_key.values():
        for other in indices[1:]:
            finder.union(indices[0], other)
    for index, entry in enumerate(entries):
        for related_key in entry.related:
            for other in by_key.get(related_key, []):
                if entries[other].source != entry.source:
                    finder.union(index, other)
    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            if entries[i].source != entries[j].source and _match(entries[i], entries[j]):
                finder.union(i, j)

    groups = defaultdict(list)
    for index in range(len(entries)):
        groups[finder.find(index)].append(entries[index])

    news_result = results.get("news")
    headlines = _headline_index(news_result.items if news_result and news_result.ok else [])

    topics = []
    for members in groups.values():
        topic = _aggregate(members, now)
        if topic:
            _attach_news(topic, members, headlines)
            topics.append(topic)

    link_stories(topics)
    for topic in topics:
        explain(topic, now)
    _score(topics, results, lifecycle, now)
    topics.sort(key=lambda t: (-t["heat"], -t["potential"]))
    for rank, topic in enumerate(topics, 1):
        topic["rank"] = rank
    return topics


_DATE_SHORT_RE = re.compile(r"^(\d{1,2}) ([efmajsond])$")
_MONTHS_BY_INITIAL = {
    "e": ("enero",), "f": ("febrero",), "m": ("marzo", "mayo"), "a": ("abril", "agosto"), "j": ("junio", "julio"),
    "s": ("septiembre",), "o": ("octubre",), "n": ("noviembre",), "d": ("diciembre",),
}
MAX_ANGLES = 8


def _plain(text: str, keep_accents: bool) -> str:
    text = split_hashtag(text or "").lower()
    if not keep_accents:
        text = strip_accents(text)
    return " ".join(re.sub(r"[^\w]+|_", " ", text).split())


def story_phrases(title: str) -> list:
    base = norm(title)
    match = _DATE_SHORT_RE.match(base)
    if match:
        return [f"{match.group(1)} de {month}" for month in _MONTHS_BY_INITIAL[match.group(2)]]
    words = base.split()
    if len(base.replace(" ", "")) < 4 or base in GENERIC_TOKENS or all(w in STOPWORDS for w in words):
        return []
    return [base]


def _count_phrase(phrase: str, text: str) -> int:
    return len(re.findall(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text)) if phrase and text else 0


def link_stories(topics: list) -> None:
    anchors = sorted(
        (t for t in topics if t.get("google") and not t["utility"]),
        key=lambda t: -((t["google"] or {}).get("volume") or 0),
    )[:60]
    contexts = []
    for anchor in anchors:
        headlines = anchor.get("_headlines") or []
        related = anchor["google"].get("related") or []
        contexts.append((
            anchor,
            "\n".join(norm(r) for r in related),
            "\n".join(_plain(h, False) for h in headlines),
            "\n".join(_plain(h, True) for h in headlines),
            math.sqrt(max(len(related), 1)),
            math.sqrt(max(len(headlines), 1)),
        ))
    for topic in topics:
        if topic.get("google") or topic["utility"]:
            continue
        phrases = story_phrases(topic["title"])
        exact = _plain(topic["title"], True)
        accented = exact != _plain(topic["title"], False)
        specific = bool(phrases) and (phrases[0] != norm(topic["title"]) or len(exact.replace(" ", "")) >= 5)
        threshold = 1 if specific else 2
        candidates = []
        for anchor, related_text, plain_text, accented_text, related_size, headline_size in contexts:
            if accented:
                related_hits, headline_hits = 0, _count_phrase(exact, accented_text) if phrases else 0
            else:
                related_hits = sum(min(1, _count_phrase(p, related_text)) for p in phrases)
                headline_hits = sum(_count_phrase(p, plain_text) for p in phrases)
            evidence = 2 * related_hits + headline_hits
            if evidence >= threshold:
                affinity = 2 * related_hits / related_size + headline_hits / headline_size
                candidates.append((affinity, evidence, anchor))
        if not candidates:
            continue
        best = max(candidates, key=lambda c: (c[0], c[1]))[2]
        topic["story"] = {"key": best["key"], "title": best["title"]}
        if topic["niche"] == "otros" and best["niche"] != "otros":
            topic["niche"] = best["niche"]
            topic["niches"] = [best["niche"]] + [n for n in topic["niches"] if n not in (best["niche"], "otros")]
        angles = best.setdefault("angles", [])
        if len(angles) < MAX_ANGLES:
            angles.append({"key": topic["key"], "title": topic["title"], "sources": list(topic["sources"])})
    for topic in topics:
        topic.pop("_headlines", None)


def _aggregate(members: list, now: float):
    def best(source, sort_key):
        candidates = [m.item for m in members if m.source == source]
        return min(candidates, key=sort_key) if candidates else None

    google = best("google", lambda i: (not i.get("active"), -(i.get("volume") or 0)))
    x = best("x", lambda i: i.get("rank") or 999)
    wiki = best("wikipedia", lambda i: i.get("rank") or 999)
    primary = google or x or wiki
    if not primary:
        return None

    if google:
        title, topic_key = google["title"], google["id"]
    elif wiki:
        title, topic_key = wiki["title"], wiki["id"]
    else:
        title, topic_key = x["title"], x["id"]

    sources = [s for s in SOURCE_ORDER if any(m.source == s for m in members)]
    started = google.get("started_at") if google else (x.get("first_seen") if x else None)
    elapsed = (now - started) / 3600.0 if started else None

    google_series = (google or {}).get("volume_series") or []
    if len(set(google_series)) >= 2:
        series, series_kind = google_series, "google_volume"
    elif x and any(x.get("series") or []):
        series, series_kind = x["series"], "x"
    elif wiki and wiki.get("series"):
        series, series_kind = wiki["series"], "wikipedia"
    elif google_series:
        series, series_kind = google_series, "google_volume"
    else:
        series, series_kind = [], None

    if google:
        metric = {"value": google.get("volume"), "kind": "búsquedas", "plus": True}
    elif x and x.get("volume"):
        metric = {"value": x["volume"], "kind": "posts en X", "plus": False}
    elif wiki:
        metric = {"value": wiki["views"], "kind": "lecturas", "plus": False}
    else:
        metric = {"value": None, "kind": "", "plus": False}

    query = (google or {}).get("query") or (wiki or {}).get("title") or title.lstrip("#")
    return {
        "key": topic_key,
        "title": title,
        "query": query,
        "sources": sources,
        "google": google,
        "x": x,
        "wikipedia": wiki,
        "news": {"count": 0, "items": []},
        "related": (google or {}).get("related", [])[:10],
        "image": (google or {}).get("picture") or (wiki or {}).get("thumbnail"),
        "description": (wiki or {}).get("description"),
        "started_at": started,
        "elapsed_hours": round(elapsed, 2) if elapsed is not None else None,
        "series": series,
        "series_kind": series_kind,
        "series_label": SERIES_LABELS.get(series_kind, ""),
        "series_end": int(now) if series_kind == "google_volume" else None,
        "series_step": {"google_volume": VOLUME_STEP_SECONDS, "x": 3600, "wikipedia": 86400}.get(series_kind),
        "volume_trend": (google or {}).get("volume_trend"),
        "metric": metric,
        "growth_pct": (google or {}).get("growth_pct"),
        "utility": is_utility(query),
        "_member_tokens": [m.tokens for m in members if m.tokens],
        "_member_keys": [m.key for m in members if m.key],
    }


_TOPICAL_SECTIONS = ("deportes", "economia", "tecnologia", "entretenimiento", "ciencia", "salud", "internacional")


def dedupe_news(items: list) -> list:
    """Quita titulares repetidos sin perder lo que aporta cada copia: cobertura, origen y datos que falten."""
    kept_by_ident, unique = {}, []
    for item in items:
        ident = key(item.get("title") or "")[:60]
        if not ident:
            continue
        kept = kept_by_ident.get(ident)
        if kept is None:
            kept_by_ident[ident] = dict(item)
            unique.append(kept_by_ident[ident])
            continue
        if item.get("coverage"):
            kept["coverage"] = max(kept.get("coverage") or 1, item["coverage"])
        if item.get("from_trend"):
            kept["from_trend"] = True
        for field in ("url", "source", "published"):
            if not kept.get(field) and item.get(field):
                kept[field] = item[field]
    return unique


def _attach_news(topic: dict, members: list, headlines: list) -> None:
    token_sets = topic.pop("_member_tokens")
    keys = topic.pop("_member_keys")
    matched = []
    for headline_tokens, headline_key, item in headlines:
        if _headline_match(token_sets, keys, headline_tokens, headline_key):
            matched.append(item)
    google_news = (topic.get("google") or {}).get("news") or []
    combined = [{"title": n.get("title"), "url": n.get("url"), "source": n.get("source"), "published": n.get("time"),
                 "from_trend": True} for n in google_news]
    combined += [{"title": n["title"], "url": n["url"], "source": n["source"], "published": n.get("published"),
                  "coverage": n.get("coverage") or 1} for n in matched]
    unique = dedupe_news(combined)
    sources = {n["source"] for n in matched if n.get("source")}
    outlets = max([len(sources)] + [n.get("coverage") or 1 for n in matched]) if matched else 0
    topic["news"] = {"count": len(matched), "outlets": outlets, "items": unique[:10]}
    topic["_headlines"] = [n["title"] for n in unique if n.get("title")]
    if matched and "news" not in topic["sources"]:
        topic["sources"].append("news")
    headlines_text = [n["title"] for n in unique if n.get("title")]
    base, prior = None, None
    if topic.get("google") and topic["google"].get("categories"):
        base = topic["google"]["categories"][0]
    elif matched:
        sections = Counter(m.get("section") for m in matched if m.get("section") in _TOPICAL_SECTIONS)
        if sections:
            section, votes = sections.most_common(1)[0]
            if votes * 2 >= len(matched):
                base, prior = section, 1.5
    niches = classify(topic["title"], topic.get("related") or [], headlines_text, base, topic.get("description") or "", prior=prior)
    topic["niches"] = niches
    topic["niche"] = niches[0]


def _score(topics: list, results: dict, lifecycle: dict, now: float) -> None:
    def items(source):
        result = results.get(source)
        return result.items if result and result.ok else []

    google_volume = percentiles({i["id"]: i.get("volume") for i in items("google")})
    google_growth = percentiles({i["id"]: i.get("growth_pct") for i in items("google") if i.get("active")})
    x_items = items("x")
    x_volume = percentiles({i["id"]: i.get("volume") for i in x_items})
    x_total = max(len(x_items), 1)
    wiki_views = percentiles({i["id"] + i.get("project", ""): i.get("views") for i in items("wikipedia")})

    for topic in topics:
        google, x, wiki = topic["google"], topic["x"], topic["wikipedia"]
        reach, momentum = [], []
        if google:
            reach.append(google_volume.get(google["id"], 0.3))
            if google.get("active"):
                momentum.append(_google_momentum(google_growth.get(google["id"], 0.3), google.get("volume_trend")))
            else:
                momentum.append(0.1)
        if x:
            rank_score = 1 - (x["rank"] - 1) / max(x_total - 1, 1)
            reach.append(max(rank_score, x_volume.get(x["id"], 0)) * 0.9)
            change = x.get("rank_change")
            if x.get("is_new"):
                momentum.append(0.85)
            elif change and change > 0:
                momentum.append(min(1.0, 0.5 + change / 20))
            elif change and change < 0:
                momentum.append(0.2)
            else:
                momentum.append(0.4)
        if wiki:
            reach.append(wiki_views.get(wiki["id"] + wiki.get("project", ""), 0.3) * 0.8)
            change = wiki.get("change_pct")
            if change is None:
                momentum.append(0.7 if wiki.get("is_new") else 0.4)
            elif change <= -30:
                momentum.append(0.15)
            elif change < 20:
                momentum.append(0.35)
            else:
                momentum.append(min(1.0, 0.45 + math.log10(1 + change / 100) * 0.5))
        news_count = topic["news"]["count"]
        if news_count:
            reach.append(min(1.0, news_count / 6) * 0.7)

        if topic["sources"] == ["x"] and not topic.get("story") and topic["niche"] == "otros":
            reach = [r * 0.8 for r in reach]
        if google and not google.get("active"):
            reach = [r * 0.75 for r in reach]
            momentum = [min(m, 0.5) for m in momentum]
        platforms = len([s for s in topic["sources"] if s != "news"])
        breadth = min(1.0, (platforms - 1) / 3) + (0.15 if news_count else 0)
        elapsed = topic.get("elapsed_hours")
        freshness = math.exp(-elapsed / 18) if elapsed is not None else 0.4
        heat = 100 * (0.40 * max(reach or [0]) + 0.30 * max(momentum or [0]) + 0.20 * clamp(breadth) + 0.10 * freshness)
        topic["heat"] = int(round(clamp(heat, 0, 100)))
        topic["heat_parts"] = {
            "alcance": round(max(reach or [0]), 2),
            "impulso": round(max(momentum or [0]), 2),
            "multiplataforma": round(clamp(breadth), 2),
            "frescura": round(freshness, 2),
        }

        phase, reason = _phase(topic, now)
        lifetime = typical_lifetime(lifecycle, topic["niche"])
        remaining = max(0.0, lifetime - elapsed) if elapsed is not None else None
        if phase == "enfriandose" and remaining is not None:
            remaining = min(remaining, lifetime * 0.15)
        fraction = clamp(remaining / lifetime) if remaining is not None and lifetime else 0.5
        topic["phase"] = phase
        topic["phase_label"] = PHASE_LABELS[phase]
        topic["phase_reason"] = reason
        topic["typical_hours"] = round(lifetime, 1)
        topic["remaining_hours"] = round(remaining, 1) if remaining is not None else None
        topic["potential"] = int(round(topic["heat"] * PHASE_WEIGHT[phase] * (0.6 + 0.4 * fraction)))
        topic["signals"] = _signals(topic)


def _google_momentum(growth_rank: float, trend) -> float:
    momentum = growth_rank * 0.9
    if not trend:
        return momentum
    if trend["recent_steps"] >= 2:
        return 1.0
    if trend["recent_steps"] == 1:
        return max(momentum, 0.8)
    if trend["watched_hours"] >= 2 and trend["stalled_hours"] >= 3:
        return min(momentum, 0.4)
    if trend["watched_hours"] >= 2 and trend["stalled_hours"] >= 2:
        return min(momentum, 0.6)
    return momentum


def niche_stats(topics: list) -> list:
    stats = {}
    for topic in topics:
        entry = stats.setdefault(topic["niche"], {"id": topic["niche"], "name": NICHE_NAMES.get(topic["niche"], topic["niche"]),
                                                  "count": 0, "heat_total": 0, "volume": 0, "top": []})
        entry["count"] += 1
        entry["heat_total"] += topic["heat"]
        if topic["google"]:
            entry["volume"] += topic["google"].get("volume") or 0
        if len(entry["top"]) < 3:
            entry["top"].append({"key": topic["key"], "title": topic["title"], "heat": topic["heat"]})
    rows = list(stats.values())
    for row in rows:
        row["heat_avg"] = round(row["heat_total"] / row["count"]) if row["count"] else 0
    rows.sort(key=lambda r: (-r["heat_total"], NICHE_ORDER.get(r["id"], 99)))
    return rows


def kpis(topics: list, results: dict) -> dict:
    visible = [t for t in topics if not t["utility"]]
    google_items = [i for i in (results["google"].items if results.get("google") and results["google"].ok else [])]
    active = [i for i in google_items if i.get("active")]
    top_volume = max(active, key=lambda i: i.get("volume") or 0, default=None)
    top_growth = max(active, key=lambda i: i.get("growth_pct") or 0, default=None)
    multi = [t for t in visible if len([s for s in t["sources"] if s != "news"]) >= 2]
    rising = [t for t in visible if t["phase"] in ("explosivo", "subiendo", "temprana")]
    niche_counts = Counter(t["niche"] for t in visible[:60] if t["niche"] != "otros")
    dominant = niche_counts.most_common(1)[0] if niche_counts else None
    return {
        "topics": len(visible),
        "rising": len(rising),
        "google_active": len(active),
        "top_volume": {"title": top_volume["title"], "value": top_volume.get("volume"), "key": top_volume["id"]} if top_volume else None,
        "top_growth": {"title": top_growth["title"], "value": top_growth.get("growth_pct"), "key": top_growth["id"]} if top_growth else None,
        "multiplatform": len(multi),
        "dominant_niche": {"id": dominant[0], "name": NICHE_NAMES.get(dominant[0]), "count": dominant[1]} if dominant else None,
    }


def recase_google(results: dict) -> None:
    texts = []
    for source in ("news", "x", "wikipedia"):
        result = results.get(source)
        if result and result.ok:
            texts.extend(i.get("title") or "" for i in result.items)
    for source in ("google", "google_week"):
        result = results.get(source)
        if result and result.ok:
            for item in result.items:
                texts.extend(n.get("title") or "" for n in item.get("news") or [])
    mapping = casing_map(texts)
    for source in ("google", "google_week"):
        result = results.get(source)
        if result and result.ok:
            for item in result.items:
                item["title"] = recase(item.get("query") or item.get("title") or "", mapping)


def niche_momentum(google_rows: list, now: float = None) -> list:
    now = now or time.time()
    windows = defaultdict(Counter)
    for row in google_rows:
        started = row.get("started")
        if not started:
            continue
        age = int((now - started) // 86400)
        if 0 <= age <= 6:
            windows[age][row.get("niche") or "otros"] += 1
    current_counts = windows.get(0, Counter())
    total_now = sum(current_counts.values())
    past = [counts for age, counts in windows.items() if age > 0 and sum(counts.values())]
    if total_now < 5 or len(past) < 2:
        return []
    out = []
    for niche, _name in NICHES:
        if niche == "otros":
            continue
        shares = [counts[niche] / sum(counts.values()) for counts in past]
        average = sum(shares) / len(shares)
        current = current_counts[niche] / total_now
        if average == 0 and current == 0:
            continue
        out.append({
            "id": niche,
            "name": NICHE_NAMES[niche],
            "today_share": round(current * 100, 1),
            "avg_share": round(average * 100, 1),
            "delta": round((current - average) * 100, 1),
        })
    out.sort(key=lambda r: -abs(r["delta"]))
    return out[:10]


def start_hours(google_rows: list) -> list:
    counts = Counter()
    for row in google_rows:
        if row.get("started"):
            counts[dt.datetime.fromtimestamp(row["started"]).hour] += 1
    return [counts.get(h, 0) for h in range(24)]


def history(google_rows: list, topic_rows: list, wiki_rows: list, days: int, now: float = None) -> dict:
    now = now or time.time()
    today = dt.datetime.fromtimestamp(now).date()
    day_list = [(today - dt.timedelta(days=i)).isoformat() for i in range(days)]
    google_by_day = defaultdict(list)
    for row in google_rows:
        if row.get("started"):
            google_by_day[dt.datetime.fromtimestamp(row["started"]).date().isoformat()].append(row)
    topics_by_day = defaultdict(list)
    for row in topic_rows:
        topics_by_day[row["day"]].append(row)
    wiki_by_day = defaultdict(list)
    for row in wiki_rows:
        wiki_by_day[row["day"]].append(row)

    day_summaries = []
    matrix = {}
    for day in day_list:
        g_rows = sorted(google_by_day.get(day, []), key=lambda r: -(r.get("volume") or 0))
        niches = Counter(r.get("niche") or "otros" for r in g_rows)
        matrix[day] = dict(niches)
        top = []
        for row in g_rows[:12]:
            duration = None
            if row.get("ended") and row.get("started"):
                duration = round((row["ended"] - row["started"]) / 3600, 1)
            top.append({
                "key": row["id"], "title": row["title"], "niche": row.get("niche"), "volume": row.get("volume"),
                "growth": row.get("growth"), "started": row.get("started"), "duration_hours": duration,
                "active": bool(row.get("active")), "utility": is_utility(row.get("query") or row.get("title") or ""),
            })
        multi = [
            {"key": r["key"], "title": r["title"], "niche": r["niche"], "sources": (r.get("sources") or "").split(","),
             "peak_heat": r.get("peak_heat")}
            for r in topics_by_day.get(day, [])[:12]
        ]
        wiki = [{"title": r["title"], "views": r["views"], "niche": r.get("niche")} for r in wiki_by_day.get(day, [])[:10]]
        day_summaries.append({
            "day": day,
            "google_count": len(g_rows),
            "google_volume": sum(r.get("volume") or 0 for r in g_rows),
            "top_searches": top,
            "top_topics": multi,
            "top_wikipedia": wiki,
        })

    recurrence = defaultdict(set)
    titles = {}
    for row in google_rows:
        if row.get("started"):
            recurrence[row["id"]].add(dt.datetime.fromtimestamp(row["started"]).date().isoformat())
            titles[row["id"]] = (row["title"], row.get("niche"))
    for row in topic_rows:
        recurrence[row["key"]].add(row["day"])
        titles.setdefault(row["key"], (row["title"], row.get("niche")))
    recurring = [
        {"key": k, "title": titles[k][0], "niche": titles[k][1], "days": len(v)}
        for k, v in recurrence.items() if len(v) >= 2 and k in titles and not is_utility(titles[k][0] or "")
    ]
    recurring.sort(key=lambda r: -r["days"])

    niche_ids = [n for n, _ in NICHES if any(matrix[d].get(n) for d in day_list)]
    niche_ids.sort(key=lambda n: -sum(matrix[d].get(n, 0) for d in day_list))
    return {
        "days": day_summaries,
        "heatmap": {
            "days": day_list,
            "niches": [{"id": n, "name": NICHE_NAMES[n]} for n in niche_ids[:10]],
            "values": [[matrix[d].get(n, 0) for d in day_list] for n in niche_ids[:10]],
        },
        "start_hours": start_hours(google_rows),
        "lifecycle": [
            {"id": n, "name": NICHE_NAMES.get(n, n), **info}
            for n, info in sorted(lifecycle_stats(google_rows).items(), key=lambda kv: -kv[1]["count"]) if n != "_all"
        ],
        "lifecycle_all": lifecycle_stats(google_rows).get("_all"),
        "recurring": recurring[:15],
    }
