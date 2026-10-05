from __future__ import annotations

import datetime as dt
import json
import re
import sys
import tempfile
import time
import traceback
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

from .config import Settings
from .engine import Engine
from .net import APP_UA, TIMEOUT, make_session
from .sources import efemerides, google_trends, news, wikipedia, x_trends, youtube
from .storage import Storage

RESULTS = {}


def section(title: str) -> None:
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78, flush=True)


def show(label: str, value) -> None:
    print(f"  {label}: {value}", flush=True)


def snippet(text, limit: int = 600) -> None:
    clean = re.sub(r"\s+", " ", str(text or ""))[:limit]
    print(f"  >>> {clean}", flush=True)


def list_paths(obj, path="$", depth=0, out=None):
    out = [] if out is None else out
    if depth > 14 or len(out) > 30:
        return out
    if isinstance(obj, list):
        dicts = [x for x in obj if isinstance(x, dict)]
        if dicts:
            out.append((path, len(obj), sorted(dicts[0].keys())[:30]))
        for index, value in enumerate(obj[:2]):
            list_paths(value, f"{path}[{index}]", depth + 1, out)
    elif isinstance(obj, dict):
        for key, value in obj.items():
            list_paths(value, f"{path}.{key}", depth + 1, out)
    return out


def probe(name: str, fn) -> None:
    section(name)
    start = time.time()
    try:
        fn()
        RESULTS[name] = "ok"
    except Exception as exc:
        traceback.print_exc()
        RESULTS[name] = f"ERROR {exc.__class__.__name__}: {exc}"
    show("tiempo", f"{time.time() - start:.1f} s")


def diag_google() -> None:
    session = make_session()
    f_req = json.dumps([[["i0OFE", json.dumps([None, None, "ES", 0, "es", 24, 1]), None, "generic"]]])
    response = session.post(google_trends.BATCH_URL, data={"f.req": f_req}, headers=google_trends._HEADERS, timeout=TIMEOUT)
    show("batch status", response.status_code)
    show("content-type", response.headers.get("content-type"))
    show("longitud", len(response.text))
    snippet(response.text, 300)
    payload = google_trends.parse_batch_response(response.text, "i0OFE")
    rows = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
    show("filas crudas", len(rows))
    if rows:
        show("longitud fila 0", len(rows[0]))
        snippet(json.dumps(rows[0], ensure_ascii=False), 900)
    for index, row in enumerate(rows[:3]):
        tail = row[9:] if isinstance(row, list) else []
        show(f"fila {index} índices 9..", json.dumps(tail, ensure_ascii=False)[:500])
    items = google_trends.parse_trending(payload)
    show("tendencias", len(items))
    for item in items[:12]:
        print(f"   - {item['title']!r} vol={item['volume']} crec={item['growth_pct']} activa={item['active']} "
              f"inicio={item['started_at']} cats={item['categories']} rel={item['related'][:3]} tokens={len(item['news_tokens'])}")
    tokens = next((i["news_tokens"] for i in items if i["news_tokens"]), None)
    show("ejemplo de tokens de noticias", json.dumps(tokens, ensure_ascii=False)[:300] if tokens else None)
    if tokens:
        found = google_trends.fetch_news_by_tokens(tokens[:3])
        show("noticias por token", len(found))
        for item in found[:3]:
            print(f"   - {item['title']!r} ({item['source']}) {item['url']}")
    rss = google_trends.fetch_rss(session)
    show("rss tendencias", len(rss))
    for item in rss[:4]:
        print(f"   - {item['title']!r} vol={item['volume']} noticias={len(item['news'])}")
    week = google_trends.fetch(hours=168)
    show("7 días ok", week.ok)
    show("7 días tendencias", len(week.items))
    show("7 días terminadas", sum(1 for i in week.items if not i["active"]))
    show("7 días error", week.error)


def diag_x() -> None:
    session = make_session()
    for name, url, parser in (
        ("trends24", x_trends.TRENDS24_URL, x_trends.parse_trends24),
        ("getdaytrends", x_trends.GETDAYTRENDS_URL, x_trends.parse_getdaytrends),
    ):
        print(f"\n  -- {name} --")
        try:
            response = session.get(url, timeout=TIMEOUT)
        except Exception as exc:
            show("error", exc)
            continue
        show("status", response.status_code)
        show("url final", response.url)
        show("longitud", len(response.text))
        soup = BeautifulSoup(response.text, "html.parser")
        show("título", soup.title.get_text(strip=True) if soup.title else None)
        show("ol.trend-card__list", len(soup.select("ol.trend-card__list")))
        show("[data-timestamp]", len(soup.find_all(attrs={"data-timestamp": True})))
        show(".tweet-count", len(soup.select(".tweet-count")))
        show("enlaces a búsqueda de X", len(soup.find_all("a", href=x_trends._SEARCH_HREF)))
        show("enlaces /trend/", len(soup.select('a[href*="/trend/"]')))
        first = soup.select_one("ol.trend-card__list") or soup.select_one("ol") or soup.select_one("table")
        snippet(str(first)[:1500] if first else response.text[:1500], 1500)
        if name == "getdaytrends":
            rows = soup.select("table.trends tr")[:3]
            for row in rows:
                snippet(str(row), 1400)
            polylines = []
            for row in soup.select("table.trends tr")[:12]:
                link = row.find("a")
                points = [pl.get("points", "") for pl in row.find_all("polyline") if pl.get("points") and "grid" not in " ".join(pl.get("class") or [])]
                polylines.append((link.get_text(strip=True) if link else "?", points))
            show("polilíneas", polylines)
            for match in list(re.finditer(r"(tweets|posts)", response.text, re.I))[:5]:
                snippet(response.text[max(0, match.start() - 160): match.start() + 60], 220)
            tables = soup.find_all("table")
            show("tablas", [(" ".join(t.get("class") or []), len(t.find_all("tr"))) for t in tables])
            for table in soup.select("table.top")[:2]:
                for row in table.find_all("tr")[:2]:
                    snippet(str(row), 700)
            for heading in soup.find_all(["h1", "h2", "h3", "h4"])[:12]:
                show("encabezado", heading.get_text(" ", strip=True)[:80])
        cards = parser(response.text)
        show("bloques horarios", len(cards))
        if cards:
            show("marcas de tiempo", [c[0] for c in cards[:4]])
        items = x_trends.build_items(cards)
        show("tendencias", len(items))
        for item in items[:10]:
            print(f"   - #{item['rank']} {item['title']!r} posts={item['volume']} horas={item['hours_in_trends']} "
                  f"cambio={item['rank_change']} nuevo={item['is_new']}")
    result = x_trends.fetch()
    show("fetch ok", result.ok)
    show("fetch proveedor", result.meta.get("provider"))
    show("fetch error", result.error)


def diag_wikipedia() -> None:
    session = make_session(APP_UA)
    day = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
    url = wikipedia.TOP_COUNTRY_URL.format(y=day.year, m=day.month, d=day.day)
    response = session.get(url, timeout=TIMEOUT)
    show("top-per-country status", response.status_code)
    if response.ok:
        payload = response.json()
        items = payload.get("items") or []
        show("claves", list(payload.keys()))
        if items:
            show("claves item", list(items[0].keys()))
            snippet(json.dumps(items[0].get("articles", [])[:5], ensure_ascii=False), 500)
    else:
        snippet(response.text, 300)
    result = wikipedia.fetch()
    show("fetch ok", result.ok)
    show("fetch error", result.error)
    show("artículos", len(result.items))
    show("días", result.meta.get("days"))
    for item in result.items[:10]:
        print(f"   - #{item['rank']} {item['title']!r} ({item['lang']}) {item['views']} lecturas cambio={item['change_pct']} desc={item['description']!r}")
    today = dt.date.today()
    for template in efemerides.URLS:
        response = session.get(template.format(m=today.month, d=today.day), timeout=TIMEOUT)
        show(f"onthisday {template.split('/')[2]}", response.status_code)
        if response.ok:
            data = response.json()
            show("tipos", {k: len(v) for k, v in data.items() if isinstance(v, list)})
            selected = (data.get("selected") or data.get("events") or [{}])[0]
            snippet(json.dumps(selected, ensure_ascii=False)[:700], 700)
    with tempfile.TemporaryDirectory() as tmp:
        result = efemerides.fetch(Path(tmp), days=4)
    show("efemérides ok", result.ok)
    show("efemérides error", result.error)
    for day_block in result.items[:2]:
        for item in day_block["items"][:3]:
            print(f"   - {item['date']} {item['year']} (hace {item['years_ago']}) [{item['kind']}] {item['text'][:90]!r} españa={item['spain']}")


def diag_news() -> None:
    result = news.fetch()
    show("ok", result.ok)
    show("error", result.error)
    show("titulares", len(result.items))
    show("por sección", {k: len(v) for k, v in (result.meta.get("sections") or {}).items()})
    show("errores de sección", result.meta.get("errors"))
    for item in result.items[:6]:
        print(f"   - {item['title']!r} ({item['source']}) cobertura={item['coverage']} sección={item['section']}")
    found = news.search("Real Madrid")
    show("búsqueda", len(found))


def diag_youtube() -> None:
    session = make_session()
    youtube.prepare_session(session)
    params = youtube.search_params(sort=youtube.SORT_VIEWS, upload=youtube.UPLOAD_WEEK, kind=youtube.TYPE_VIDEO)
    body = {"context": {"client": youtube.CLIENT}, "query": "Real Madrid", "params": params}
    response = session.post(youtube.SEARCH_API, params={"prettyPrint": "false"}, json=body,
                            headers={"Content-Type": "application/json", "X-Youtube-Client-Name": "1",
                                     "X-Youtube-Client-Version": youtube.CLIENT["clientVersion"]}, timeout=TIMEOUT)
    show("innertube status", response.status_code)
    show("longitud", len(response.text))
    if response.ok:
        data = response.json()
        counts = Counter()

        def walk(node, depth=0):
            if depth > 40:
                return
            if isinstance(node, dict):
                for key, value in node.items():
                    if key.endswith(("Renderer", "ViewModel")):
                        counts[key] += 1
                    walk(value, depth + 1)
            elif isinstance(node, list):
                for value in node:
                    walk(value, depth + 1)

        walk(data)
        show("renderers", counts.most_common(14))
        videos = youtube.parse_search(data)
        show("vídeos", len(videos))
        for video in videos[:6]:
            print(f"   - {video['title']!r} | {video['channel']!r} | vistas={video['views']} | {video['published']!r} | dur={video['duration']} | short={video['is_short']}")
    else:
        snippet(response.text, 400)
    summary = youtube.competition("Batalla de Lepanto")
    show("competencia", {k: summary[k] for k in ("count", "top_views", "median_views", "level")})
    page = session.get(youtube.RESULTS_URL, params={"search_query": "Lepanto", "hl": "en", "gl": "ES"}, timeout=TIMEOUT)
    show("html status", page.status_code)
    show("html url final", page.url)
    show("ytInitialData", "ytInitialData" in page.text)


def diag_pipeline() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "cache").mkdir()
        engine = Engine(Settings(root / "settings.json"), Storage(root))
        engine.refresh(force=True)
        state = engine.get_state()
    show("error interno", state.get("last_error"))
    for source, info in state["sources"].items():
        print(f"   · {source:<12} ok={info['ok']} n={info['count']} modo={info['mode']} cuenta={info.get('requires_login')} "
              f"error={(info['error'] or '')[:120]}")
    wiki_items = (state.get("platforms") or {}).get("wikipedia") or []
    show("wikipedia con descripción", f"{sum(1 for i in wiki_items if i.get('description'))}/{len(wiki_items)}")
    topics = state.get("topics") or []
    show("temas", len(topics))
    for topic in topics[:30]:
        print(f"   {topic['rank']:>2}. calor={topic['heat']:>3} pot={topic['potential']:>3} {topic['phase']:<11} {topic['niche']:<15} "
              f"{','.join(topic['sources']):<34} {topic['title']!r}{' [utilitaria]' if topic['utility'] else ''}")
        print(f"       razón: {topic['phase_reason']}")
        if topic.get("story") or topic.get("angles"):
            print(f"       historia: {(topic.get('story') or {}).get('title')} · ángulos: {[a['title'] for a in topic.get('angles', [])]}")
    section("EXPLICACIONES (lo que verá el usuario en el radar)")
    top = [t for t in topics if not t["utility"]][:20]
    show("con «qué pasa»", f"{sum(1 for t in top if t.get('why'))}/{len(top)}")
    show("con «qué es»", f"{sum(1 for t in top if t.get('what'))}/{len(top)}")
    for topic in top:
        why, chip = topic.get("why") or {}, topic.get("youtube") or {}
        print(f"   {topic['rank']:>2}. {topic['title']!r} [{topic['niche']}]")
        print(f"       qué pasa: {why.get('title')!r} ({why.get('source')})")
        subject = f"{topic['what_subject']}: " if topic.get("what_subject") else ""
        print(f"       qué es:   {subject}{topic.get('what')!r}")
        print(f"       cifras:   {topic.get('summary')!r}")
        if chip:
            print(f"       youtube:  {chip.get('label')} · {chip.get('count')} vídeos · máx {chip.get('top_views')}")
    for item in ((state.get("platforms") or {}).get("youtube") or [])[:6]:
        print(f"   · youtube «{item.get('query')}» busca {item.get('search_url', '').split('search_query=')[-1].split('&')[0]!r}: "
              f"{[(v['title'][:60], v['views']) for v in (item.get('videos') or [])[:3]]}")
    linked = [t for t in topics if t.get("story")]
    show("temas enlazados a una historia", len(linked))
    for topic in linked[:25]:
        print(f"   - {topic['title']!r} ({','.join(topic['sources'])}, {topic['niche']}) -> {topic['story']['title']!r}")
    visible = [t for t in topics if not t["utility"]]
    others = [t for t in visible if t["niche"] == "otros"]
    show("sin nicho (otros)", f"{len(others)}/{len(visible)} · {[t['title'] for t in others[:25]]}")
    show("kpis", json.dumps(state.get("kpis"), ensure_ascii=False))
    show("nichos", [(n["id"], n["count"]) for n in state.get("niche_stats", [])][:12])
    show("efemérides destacadas", [(h["date"], h["years_ago"], h["title"]) for h in state["efemerides"]["highlights"][:8]])


CHECKS = {
    "google": ("GOOGLE TRENDS", diag_google),
    "x": ("X (TRENDS24 / GETDAYTRENDS)", diag_x),
    "wikipedia": ("WIKIPEDIA Y EFEMÉRIDES", diag_wikipedia),
    "news": ("GOOGLE NEWS", diag_news),
    "youtube": ("YOUTUBE", diag_youtube),
    "pipeline": ("RADAR COMPLETO", diag_pipeline),
}


def main(argv=None) -> None:
    requested = argv if argv is not None else sys.argv[1:]
    selected = [name for name in requested if name in CHECKS] or list(CHECKS)
    for name in selected:
        title, fn = CHECKS[name]
        probe(title, fn)
        time.sleep(1)
    section("RESUMEN")
    for name, outcome in RESULTS.items():
        print(f"  {name}: {outcome}")


if __name__ == "__main__":
    main()
