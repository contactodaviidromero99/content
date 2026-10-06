from __future__ import annotations

import datetime as dt
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import APP_NAME, APP_SHORT, APP_VERSION, ai, analysis, connections, explain, planner, recap, stories
from .net import APP_UA, SourceError, make_session
from .niches import NICHES, classify
from .sources import efemerides, google_trends, news, wikipedia, x_trends, youtube
from .sources.base import SOURCE_LABELS, SourceResult, failure

CADENCE_MINUTES = {"wikipedia": 180, "google_week": 180, "efemerides": 720}
CONNECTIONS_EVERY = 2 * 3600
INSTAGRAM_TOKEN_REFRESH = 7 * 86400
EXPLAIN_TOP = 24
TREND_NEWS_LIMIT = 14
DESCRIPTION_TTL = 24 * 3600
TREND_NEWS_TTL = 45 * 60


class Engine:
    def __init__(self, settings, storage, demo_loader=None):
        self.settings = settings
        self.storage = storage
        self.demo_loader = demo_loader
        self._lock = threading.RLock()
        self._refresh_lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self.results = storage.load_results()
        self.state = storage.load_state() or {}
        self.progress = {}
        self.refreshing = False
        self.last_error = None
        self._detail_cache = {}
        self._youtube_cache = storage.load_json("youtube-cache.json") or {}
        self._description_cache = storage.load_json("descriptions-cache.json") or {}
        self._trend_news_cache = {}
        self.revision = 0
        self.connections = storage.load_json("connections-status.json") or {}
        self._sync_lock = threading.Lock()
        self._ai_cache = ai.prune(storage.load_json("ai-cache.json") or {})
        self.ai_status = storage.load_json("ai-status.json") or {}
        self._ai_lock = threading.Lock()

    def start(self) -> None:
        threading.Thread(target=self._scheduler, name="romero-scheduler", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def reschedule(self) -> None:
        self._wake.set()

    def _scheduler(self) -> None:
        self.refresh(force=False, blocking=True)
        while not self._stop.is_set():
            minutes = self.settings.get()["refresh_minutes"]
            self._wake.wait(timeout=minutes * 60)
            self._wake.clear()
            if self._stop.is_set():
                break
            self.refresh(force=False, blocking=True)

    def request_refresh(self) -> bool:
        if self.refreshing:
            return False
        threading.Thread(target=self.refresh, kwargs={"force": True, "blocking": True}, daemon=True).start()
        return True

    def _is_stale(self, source: str, minutes: int) -> bool:
        result = self.results.get(source)
        if not result:
            return True
        if source == "efemerides" and result.ok and result.items:
            if (result.meta or {}).get("today", result.items[0].get("date")) != dt.date.today().isoformat():
                return True
        age = time.time() - (result.fetched_at or 0)
        if not result.ok and not (result.meta or {}).get("requires_login"):
            return age > 5 * 60
        if result.ok and (result.meta or {}).get("partial"):
            return age > 10 * 60
        return age > minutes * 60 - 30

    def refresh(self, force: bool = False, blocking: bool = True) -> None:
        if not self._refresh_lock.acquire(blocking=False):
            return
        try:
            self.refreshing = True
            self._do_refresh(force)
            self.last_error = None
        except Exception as exc:
            self.last_error = f"{exc.__class__.__name__}: {exc}"
            traceback.print_exc()
        finally:
            self.refreshing = False
            self._refresh_lock.release()

    def _fetchers(self) -> dict:
        if self.demo_loader:
            return {sid: (lambda sid=sid: self.demo_loader(sid)) for sid in
                    ("google", "google_week", "x", "wikipedia", "news", "efemerides")}
        cache_dir = self.storage.cache_dir
        return {
            "google": lambda: google_trends.fetch(hours=24),
            "google_week": lambda: google_trends.fetch(hours=168),
            "x": x_trends.fetch,
            "wikipedia": wikipedia.fetch,
            "news": news.fetch,
            "efemerides": lambda: efemerides.fetch(cache_dir),
        }

    def _do_refresh(self, force: bool) -> None:
        settings = self.settings.get()
        enabled = settings["sources"]
        base_minutes = settings["refresh_minutes"]
        fetchers = self._fetchers()
        due = []
        for source in fetchers:
            switch = "google" if source == "google_week" else source
            if source != "efemerides" and not enabled.get(switch, True):
                continue
            minutes = CADENCE_MINUTES.get(source, base_minutes)
            if force and source in ("wikipedia", "efemerides"):
                minutes = min(minutes, 30)
            if force or self._is_stale(source, minutes):
                due.append(source)

        self.progress = {source: "pending" for source in due}
        if due:
            with ThreadPoolExecutor(max_workers=6) as pool:
                futures = {pool.submit(self._run_fetch, fetchers[source], source): source for source in due}
                for future in as_completed(futures):
                    source = futures[future]
                    result = future.result()
                    with self._lock:
                        self.results[source] = result
                    self.progress[source] = "ok" if result.ok else "error"
                    self.storage.save_result(result)

        now = time.time()
        analysis.recase_google(self.results)
        week = self.results.get("google_week")
        if week and week.ok and "google_week" in due:
            self.storage.upsert_google(week.items, self._google_niche)
        google = self.results.get("google")
        if google and google.ok and "google" in due:
            self.storage.upsert_google(google.items, self._google_niche)
            self.storage.record_google_snapshots(google.items, google.fetched_at or now)
            if self.demo_loader:
                self.storage.add_google_snapshots((google.meta or {}).get("seed_snapshots") or [])
        if google and google.ok:
            analysis.attach_volume_history(google.items, self.storage.google_snapshots(now - 26 * 3600), now)

        google_rows = self.storage.google_rows(now - 8 * 86400)
        lifecycle = analysis.lifecycle_stats(google_rows)
        active_results = {s: r for s, r in self.results.items() if enabled.get(s if s != "google_week" else "google", True)}
        topics = analysis.build_topics(active_results, lifecycle, now)
        self._enrich(topics, now)

        wiki = self.results.get("wikipedia")
        if wiki and wiki.ok:
            for item in wiki.items:
                item["niche"] = classify(item["title"], description=item.get("description") or "")[0]
            if "wikipedia" in due:
                self.storage.upsert_wiki(wiki.items)

        efem = self.results.get("efemerides")
        nearby = stories.upcoming_efemerides(efem.items if efem and efem.ok else [])
        if enabled.get("youtube", True) and settings["youtube_topics"] > 0:
            preliminary = stories.build_stories(topics, now, nearby)
            self._refresh_youtube(topics, preliminary, settings["youtube_topics"], force)
        self._attach_youtube(topics)
        story_list = stories.build_stories(topics, now, nearby)
        front = stories.portada(story_list)
        ai.attach(story_list, self._ai_cache)

        self.storage.record_topics([t for t in topics if not t["utility"]][:150], now)
        self.storage.record_stories(story_list[:60], now)
        self.storage.prune()
        state = self._compose_state(topics, story_list, front, google_rows, now)
        with self._lock:
            self.state = state
            self.revision += 1
        self.storage.save_state(state)
        self.request_ai(front["keys"])
        if force or time.time() - (self.connections.get("_synced_at") or 0) > CONNECTIONS_EVERY:
            self.sync_connections()

    def _run_fetch(self, fetcher, source: str) -> SourceResult:
        self.progress[source] = "running"
        try:
            result = fetcher()
        except Exception as exc:
            traceback.print_exc()
            result = failure(source, exc)
        if not result.ok and self.results.get(source) and self.results[source].ok:
            previous = self.results[source]
            previous.meta = dict(previous.meta or {}, stale_error=result.error, stale_since=time.time())
            previous.error = result.error
            return previous
        return result

    @staticmethod
    def _google_niche(item: dict) -> str:
        base = (item.get("categories") or [None])[0]
        return classify(item.get("title") or "", item.get("related") or [], [n.get("title") or "" for n in item.get("news") or []], base)[0]

    def _enrich(self, topics: list, now: float) -> None:
        if self.demo_loader:
            return
        targets = [t for t in topics if not t["utility"]][:EXPLAIN_TOP]
        for step in (self._add_descriptions, self._add_headlines):
            try:
                step(targets, now)
            except Exception:
                traceback.print_exc()
        for topic in targets:
            explain.explain(topic, now)

    def _add_descriptions(self, targets: list, now: float) -> None:
        wanted = [t for t in targets if not t.get("description") and not t["title"].startswith("#") and explain.looks_proper(t)]
        pending = [t["title"] for t in wanted
                   if now - (self._description_cache.get(t["title"]) or {}).get("at", 0) > DESCRIPTION_TTL]
        if pending:
            try:
                found = wikipedia.lookup_titles(make_session(APP_UA), pending[:50])
            except SourceError:
                time.sleep(4)
                found = wikipedia.lookup_titles(make_session(APP_UA), pending[:50])
            for title, info in found.items():
                self._description_cache[title] = dict(info, at=now)
            self._description_cache = {k: v for k, v in self._description_cache.items() if now - v.get("at", 0) < 7 * 86400}
            self.storage.save_json("descriptions-cache.json", self._description_cache)
        for topic in wanted:
            info = self._description_cache.get(topic["title"]) or {}
            description = info.get("description")
            if not description or info.get("missing") or info.get("disambiguation"):
                continue
            if not explain.same_entity(topic["title"], info.get("page") or "") or not explain.description_fits(topic, description):
                continue
            topic["extra_description"] = description
            if topic["niche"] == "otros":
                niches = classify(topic["title"], topic.get("related") or [], [], None, description)
                if niches[0] != "otros":
                    topic["niches"], topic["niche"] = niches, niches[0]

    def _add_headlines(self, targets: list, now: float) -> None:
        """Busca el titular que explica cada tema que aún no lo tiene: primero las noticias que Google
        asocia a la tendencia y, si no hay, una búsqueda en Google Noticias de las últimas 48 h."""
        self._trend_news_cache = {k: v for k, v in self._trend_news_cache.items() if now - v["at"] < 2 * 3600}

        def wants_trend_news(topic):
            return bool((topic.get("google") or {}).get("news_tokens")) and not any(
                n.get("from_trend") for n in topic["news"].get("items") or [])

        need = [t for t in targets if wants_trend_news(t) or (not t.get("why") and not t["title"].startswith("#"))]
        need = need[:TREND_NEWS_LIMIT]

        def fetch(topic):
            google = topic.get("google") or {}
            cache_key = f"{topic['key']}:{google.get('started_at') or 0}"
            cached = self._trend_news_cache.get(cache_key)
            if cached and now - cached["at"] < TREND_NEWS_TTL:
                return topic, cached["items"]
            items = []
            if wants_trend_news(topic):
                items = [{"title": n["title"], "url": n["url"], "source": n["source"], "published": n.get("time"),
                          "from_trend": True} for n in google_trends.fetch_news_by_tokens(google["news_tokens"][:3])]
            if not items and not topic.get("why") and not topic["title"].startswith("#"):
                items = [{"title": n["title"], "url": n["url"], "source": n["source"], "published": n.get("published"),
                          "coverage": n.get("coverage") or 1} for n in news.search(topic["query"], limit=8)]
            self._trend_news_cache[cache_key] = {"at": now, "items": items}
            return topic, items

        if not need:
            return
        with ThreadPoolExecutor(max_workers=4) as pool:
            for future in as_completed([pool.submit(fetch, t) for t in need]):
                try:
                    topic, items = future.result()
                except Exception:
                    continue
                if not items:
                    continue
                topic["news"]["items"] = analysis.dedupe_news(items + topic["news"]["items"])[:10]
                if topic["niche"] == "otros":
                    headlines = [n["title"] for n in topic["news"]["items"] if explain.qualifies(topic, n)]
                    niches = classify(topic["title"], topic.get("related") or [], headlines, None, topic.get("description") or "")
                    if niches[0] != "otros":
                        topic["niches"], topic["niche"] = niches, niches[0]

    @staticmethod
    def _youtube_context(topic: dict):
        """Palabra que se añade a la búsqueda de YouTube para no confundir el tema con otro:
        «Ángel Arroyo ciclista»; y «España» para palabras sueltas como «Elecciones» o «Votar»."""
        if topic.get("what") and not topic.get("what_subject"):
            word = explain.context_word(topic["what"])
            if word:
                return word
        if not topic["title"].startswith("#") and not explain.looks_proper(topic):
            return "España"
        return None

    def _refresh_youtube(self, topics: list, story_list: list, limit: int, force: bool) -> None:
        """Mide la competencia en YouTube de las historias de portada primero y luego de las siguientes."""
        by_key = {t["key"]: t for t in topics}
        front = stories.portada(story_list)["keys"]
        ordered = front + [s["key"] for s in story_list if s["key"] not in front]
        candidates = [by_key[k] for k in ordered if k in by_key][:limit]
        self.progress["youtube"] = "running"
        if not candidates:
            result = SourceResult(source="youtube", ok=False, error="Todavía no hay temas calientes que analizar.")
        elif self.demo_loader:
            result = self.demo_loader("youtube")
        else:
            max_age = 1800 if force else 6 * 3600
            result = youtube.fetch_for_topics(
                [{"key": t["key"], "title": t["title"], "query": t["query"], "context": self._youtube_context(t)} for t in candidates],
                self._youtube_cache, max_age=max_age,
            )
            self.storage.save_json("youtube-cache.json", self._prune_youtube_cache())
        with self._lock:
            self.results["youtube"] = result
        self.progress["youtube"] = "ok" if result.ok else "error"

    def _prune_youtube_cache(self) -> dict:
        cutoff = time.time() - 2 * 86400
        self._youtube_cache = {k: v for k, v in self._youtube_cache.items() if v.get("checked_at", 0) > cutoff}
        return self._youtube_cache

    def _attach_youtube(self, topics: list) -> None:
        result = self.results.get("youtube")
        by_key = {i.get("topic_key"): i for i in (result.items if result and result.ok else [])}
        for topic in topics:
            info = by_key.get(topic["key"]) or self._youtube_cache.get(topic["key"])
            if info:
                summary = {k: info[k] for k in ("count", "top_views", "median_views", "level", "label", "checked_at", "search_url") if k in info}
                videos = sorted((v for v in info.get("videos") or [] if v.get("views") is not None), key=lambda v: -v["views"])
                if videos:
                    summary.update(top_title=videos[0].get("title"), top_url=videos[0].get("url"), top_channel=videos[0].get("channel"))
                topic["youtube"] = summary

    def _source_status(self) -> dict:
        settings = self.settings.get()
        status = {}
        for source in ("google", "google_week", "youtube", "x", "wikipedia", "news", "efemerides"):
            result = self.results.get(source)
            switch = "google" if source == "google_week" else source
            status[source] = {
                "label": SOURCE_LABELS.get(source, source),
                "enabled": source == "efemerides" or settings["sources"].get(switch, True),
                "ok": bool(result and result.ok),
                "error": result.error if result else None,
                "fetched_at": result.fetched_at if result else None,
                "count": len(result.items) if result else 0,
                "mode": (result.meta or {}).get("mode") or (result.meta or {}).get("provider") if result else None,
                "stale": bool(result and (result.meta or {}).get("stale_error")),
                "requires_login": bool(result and (result.meta or {}).get("requires_login")),
            }
        return status

    def _compose_state(self, topics: list, story_list: list, front: dict, google_rows: list, now: float) -> dict:
        def result_items(source):
            result = self.results.get(source)
            return result.items if result and result.ok else []

        news_result = self.results.get("news")
        efem = self.results.get("efemerides")
        topic_by_key = {t["key"]: t for t in topics}
        topic_niche = {(s, t[s]["id"]): t["niche"] for t in topics for s in ("google", "x") if t.get(s)}
        google_items = result_items("google")
        for item in google_items:
            item["niche"] = topic_niche.get(("google", item["id"])) or self._google_niche(item)
        x_items = result_items("x")
        for item in x_items:
            item["niche"] = topic_niche.get(("x", item["id"])) or classify(item["title"])[0]
        today = dt.date.fromtimestamp(now).isoformat()
        highlights = [h for h in ((efem.meta or {}).get("highlights", []) if efem and efem.ok else []) if h["date"] >= today]

        return {
            "app": {"name": APP_NAME, "short": APP_SHORT, "version": APP_VERSION, "demo": bool(self.demo_loader)},
            "generated_at": now,
            "niches": [{"id": nid, "name": name} for nid, name in NICHES],
            "sources": self._source_status(),
            "stories": story_list[:150],
            "portada": front,
            "topics": topics[:220],
            "kpis": analysis.kpis(topics, self.results),
            "niche_stats": analysis.niche_stats([t for t in topics if not t["utility"]]),
            "niche_momentum": analysis.niche_momentum(google_rows, now),
            "platforms": {
                "google": google_items,
                "x": x_items,
                "wikipedia": result_items("wikipedia"),
                "news": {
                    "items": result_items("news"),
                    "sections": (news_result.meta or {}).get("sections", {}) if news_result and news_result.ok else {},
                    "labels": news.SECTION_LABELS,
                },
                "youtube": [dict(i, topic=topic_by_key.get(i.get("topic_key"), {}).get("title")) for i in result_items("youtube")],
            },
            "efemerides": {"highlights": highlights[:40]},
        }

    def get_state(self) -> dict:
        with self._lock:
            state = dict(self.state)
        state["sources"] = self._source_status()
        state["refreshing"] = self.refreshing
        state["progress"] = dict(self.progress)
        state["last_error"] = self.last_error
        state["revision"] = self.revision
        state["agenda"] = planner.agenda(self.storage)
        state["horizon"] = planner.horizon(self.results.get("efemerides"))
        state["connections"] = {k: v for k, v in self.connections.items() if not k.startswith("_")}
        state["ai"] = dict(self.ai_status, enabled=bool(self.settings.get().get("ai_key")), available=ai.available(),
                           working=self._ai_lock.locked())
        return state

    def status(self) -> dict:
        return {
            "refreshing": self.refreshing,
            "progress": dict(self.progress),
            "generated_at": self.state.get("generated_at"),
            "revision": self.revision,
            "last_error": self.last_error,
            "syncing": self._sync_lock.locked(),
        }

    # ---------- Ideas con Claude (opcional) ----------

    def request_ai(self, keys: list, force: bool = False) -> bool:
        """Pide en segundo plano las ideas de Claude para las historias de portada que aún no las tienen."""
        api_key = self.settings.get().get("ai_key")
        if not api_key or self.demo_loader or not ai.available() or self._ai_lock.locked():
            return False
        failed_recently = self.ai_status.get("ok") is False and time.time() - (self.ai_status.get("at") or 0) < 3600
        if failed_recently and not force:
            return False
        with self._lock:
            targets = [s for s in self.state.get("stories", []) if s["key"] in keys]
        if all(ai.cached(s, self._ai_cache) for s in targets):
            return False
        threading.Thread(target=self._run_ai, args=(api_key, targets), daemon=True).start()
        return True

    def _run_ai(self, api_key: str, targets: list) -> None:
        if not self._ai_lock.acquire(blocking=False):
            return
        try:
            asked = ai.enrich(api_key, targets, self._ai_cache, self.settings.get().get("name") or "")
            self.ai_status = {"ok": True, "error": None, "at": time.time(), "asked": asked}
        except ai.AIError as exc:
            self.ai_status = {"ok": False, "error": str(exc), "at": time.time(), "asked": 0}
        except Exception as exc:
            traceback.print_exc()
            self.ai_status = {"ok": False, "error": f"{exc.__class__.__name__}: {exc}"[:200], "at": time.time(), "asked": 0}
        finally:
            self._ai_cache = ai.prune(self._ai_cache)
            self.storage.save_json("ai-cache.json", self._ai_cache)
            self.storage.save_json("ai-status.json", self.ai_status)
            self._publish_ai()
            self._ai_lock.release()

    def _publish_ai(self) -> None:
        """Pone las ideas en el estado sustituyendo las historias (no modificándolas en sitio), para no
        tocar nada que otro hilo esté enviando a la interfaz en ese momento."""
        with self._lock:
            updated = []
            for story in self.state.get("stories", []):
                data = ai.cached(story, self._ai_cache)
                updated.append(dict(story, ai=data) if data and story.get("ai") != data else story)
            self.state = dict(self.state, stories=updated)
            self.revision += 1

    def ai_for_story(self, key: str) -> dict:
        """Ideas de Claude para una historia concreta (desde su ficha). Espera a la respuesta."""
        api_key = self.settings.get().get("ai_key")
        if not api_key:
            return {"error": "Añade tu clave de la API de Claude en Ajustes."}
        with self._lock:
            story = next((s for s in self.state.get("stories", []) if s["key"] == key), None)
        if not story:
            return {"error": "Esa historia ya no está en el radar."}
        try:
            ai.enrich(api_key, [story], self._ai_cache, self.settings.get().get("name") or "")
        except ai.AIError as exc:
            return {"error": str(exc)}
        self.storage.save_json("ai-cache.json", self._ai_cache)
        data = ai.cached(story, self._ai_cache)
        if data:
            self._publish_ai()
        return {"ai": data} if data else {"error": "Claude no devolvió ideas para esta historia."}

    def agenda(self) -> dict:
        return {"agenda": planner.agenda(self.storage), "horizon": planner.horizon(self.results.get("efemerides"))}

    def recap(self, offset: int = 0) -> dict:
        return recap.weekly(self.storage, offset)

    def calendar(self, month: str) -> dict:
        return planner.calendar_month(self.storage, self.results.get("efemerides"), month)

    def save_plan(self, data: dict) -> dict:
        item = planner.clean_item(data, partial=bool(data.get("id")))
        if item.get("id") and not self.storage.plan_item(item["id"]):
            raise planner.InvalidItem("Esa tarea ya no existe.")
        return self.storage.save_plan_item(item)

    def delete_plan(self, item_id: str) -> bool:
        return self.storage.delete_plan_item(str(item_id or ""))

    def link_preview(self, url: str) -> dict:
        if self.demo_loader:
            return {"url": url, "platform": planner.platform_of(url), "title": None, "author": None, "thumbnail": None, "views": None}
        return connections.preview(url)

    def request_sync(self) -> bool:
        if self._sync_lock.locked():
            return False
        threading.Thread(target=self.sync_connections, daemon=True).start()
        return True

    def sync_connections(self) -> None:
        """Trae tus vídeos publicados (YouTube, Instagram) y marca como hechas las tareas «Publicar» que encajan."""
        if not self._sync_lock.acquire(blocking=False):
            return
        try:
            settings = self.settings.get()
            status = {"_synced_at": time.time()}
            if self.demo_loader:
                items = self.demo_loader("published") or []
                self.storage.upsert_published(items)
                status["youtube"] = connections.status_line("youtube", [i for i in items if i["platform"] == "youtube"])
                status["instagram"] = connections.status_line("instagram", [i for i in items if i["platform"] == "instagram"])
            else:
                if settings.get("youtube_channel"):
                    try:
                        channel_id = settings.get("youtube_channel_id") or connections.resolve_channel(settings["youtube_channel"])
                        if channel_id != settings.get("youtube_channel_id"):
                            self.settings.update({"youtube_channel_id": channel_id}, trusted=True)
                        items = connections.fetch_youtube(channel_id, known=self.storage.published_dates("youtube"))
                        self.storage.upsert_published(items)
                        status["youtube"] = connections.status_line("youtube", items)
                    except Exception as exc:
                        status["youtube"] = connections.status_line("youtube", [], str(exc)[:200])
                token = settings.get("instagram_token")
                if token:
                    try:
                        if time.time() - (settings.get("instagram_token_at") or 0) > INSTAGRAM_TOKEN_REFRESH:
                            try:
                                token = connections.refresh_instagram_token(token)
                                self.settings.update({"instagram_token": token, "instagram_token_at": time.time()}, trusted=True)
                            except SourceError:
                                pass
                        items = connections.fetch_instagram(token)
                        self.storage.upsert_published(items)
                        status["instagram"] = connections.status_line("instagram", items)
                    except Exception as exc:
                        status["instagram"] = connections.status_line("instagram", [], str(exc)[:200])
            status["matched"] = planner.auto_match(self.storage)
            self.connections = status
            self.storage.save_json("connections-status.json", status)
            with self._lock:
                self.revision += 1
        except Exception:
            traceback.print_exc()
        finally:
            self._sync_lock.release()

    def history(self, days: int = 7) -> dict:
        days = max(1, min(int(days), 30))
        now = time.time()
        since_day = (dt.date.fromtimestamp(now) - dt.timedelta(days=days)).isoformat()
        return analysis.history(
            self.storage.google_rows(now - (days + 1) * 86400),
            self.storage.topic_day_rows(since_day),
            self.storage.wiki_rows(since_day),
            days,
            now,
        )

    def topic_detail(self, topic_key: str) -> dict:
        with self._lock:
            topic = next((t for t in self.state.get("topics", []) if t["key"] == topic_key), None)
        if not topic:
            return {"error": "Tema no encontrado. Puede que ya no esté en tendencia."}
        cached = self._detail_cache.get(topic_key)
        if cached and time.time() - cached["_at"] < 900:
            return cached["data"]

        detail = {"key": topic_key, "news": list(topic["news"]["items"]), "youtube": None, "history": []}
        if self.demo_loader:
            demo = self.demo_loader("detail") or {}
            detail["youtube"] = (demo.get("youtube") or {}).get(topic_key)
            detail["history"] = self.storage.observations(topic_key, time.time() - 3 * 86400)
            return detail

        google = topic.get("google") or {}
        errors = []
        if google.get("news_tokens") and len(detail["news"]) < 4:
            try:
                extra = google_trends.fetch_news_by_tokens(google["news_tokens"][:3])
                detail["news"] = self._dedupe_news(detail["news"] + [
                    {"title": n["title"], "url": n["url"], "source": n["source"], "published": n.get("time")} for n in extra
                ])
            except Exception as exc:
                errors.append(f"Google Trends: {exc}")
        if len(detail["news"]) < 4:
            try:
                found = news.search(topic["query"])
                detail["news"] = self._dedupe_news(detail["news"] + found)
            except Exception as exc:
                errors.append(f"Google News: {exc}")
        cached_youtube = self._youtube_cache.get(topic_key)
        if cached_youtube and time.time() - cached_youtube.get("checked_at", 0) < 6 * 3600:
            detail["youtube"] = cached_youtube
        elif self.settings.get()["sources"].get("youtube", True):
            try:
                result = youtube.competition(topic["query"], self._youtube_context(topic))
                result.update({"topic_key": topic_key, "topic_title": topic["title"]})
                self._youtube_cache[topic_key] = result
                detail["youtube"] = result
            except Exception as exc:
                errors.append(f"YouTube: {exc}")
        if not topic.get("why"):
            detail["why"] = explain.pick_why(topic, detail["news"])
        detail["history"] = self.storage.observations(topic_key, time.time() - 3 * 86400)
        detail["errors"] = errors
        self._detail_cache[topic_key] = {"_at": time.time(), "data": detail}
        return detail

    @staticmethod
    def _dedupe_news(items: list) -> list:
        seen, out = set(), []
        for item in items:
            ident = (item.get("title") or "").strip().lower()[:70]
            if ident and ident not in seen:
                seen.add(ident)
                out.append(item)
        return out[:10]
