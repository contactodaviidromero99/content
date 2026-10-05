from __future__ import annotations

import datetime as dt
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import APP_NAME, APP_VERSION, analysis
from .niches import NICHES, classify
from .sources import efemerides, google_trends, news, tiktok, wikipedia, x_trends, youtube
from .sources.base import SOURCE_LABELS, SourceResult, failure

TOPIC_SOURCES = ("google", "x", "tiktok", "wikipedia", "news")
CADENCE_MINUTES = {"tiktok": 360, "wikipedia": 180, "google_week": 180, "efemerides": 720}


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
            if result.items[0].get("date") != dt.date.today().isoformat():
                return True
        age = time.time() - (result.fetched_at or 0)
        if not result.ok:
            return age > 5 * 60
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
                    ("google", "google_week", "x", "tiktok", "wikipedia", "news", "efemerides")}
        cache_dir = self.storage.cache_dir
        return {
            "google": lambda: google_trends.fetch(hours=24),
            "google_week": lambda: google_trends.fetch(hours=168, timeline_limit=0),
            "x": x_trends.fetch,
            "tiktok": tiktok.fetch,
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
            if force and source in ("tiktok", "wikipedia", "efemerides"):
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

        google_rows = self.storage.google_rows(now - 8 * 86400)
        lifecycle = analysis.lifecycle_stats(google_rows)
        active_results = {s: r for s, r in self.results.items() if enabled.get(s if s != "google_week" else "google", True)}
        topics = analysis.build_topics(active_results, lifecycle, now)

        wiki = self.results.get("wikipedia")
        if wiki and wiki.ok:
            for item in wiki.items:
                item["niche"] = classify(item["title"], description=item.get("description") or "")[0]
            if "wikipedia" in due:
                self.storage.upsert_wiki(wiki.items)

        if enabled.get("youtube", True) and settings["youtube_topics"] > 0:
            self._refresh_youtube(topics, settings["youtube_topics"], force)
        self._attach_youtube(topics)

        self.storage.record_topics([t for t in topics if not t["utility"]][:150], now)
        self.storage.prune()
        state = self._compose_state(topics, google_rows, now)
        with self._lock:
            self.state = state
        self.storage.save_state(state)

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

    def _refresh_youtube(self, topics: list, limit: int, force: bool) -> None:
        candidates = [t for t in topics if not t["utility"]][:limit]
        self.progress["youtube"] = "running"
        if not candidates:
            result = SourceResult(source="youtube", ok=False, error="Todavía no hay temas calientes que analizar.")
        elif self.demo_loader:
            result = self.demo_loader("youtube")
        else:
            max_age = 1800 if force else 6 * 3600
            result = youtube.fetch_for_topics(
                [{"key": t["key"], "title": t["title"], "query": t["query"]} for t in candidates],
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
                topic["youtube"] = {k: info[k] for k in ("count", "top_views", "median_views", "level", "label", "checked_at") if k in info}

    def _source_status(self) -> dict:
        settings = self.settings.get()
        status = {}
        for source in ("google", "google_week", "youtube", "tiktok", "x", "wikipedia", "news", "efemerides"):
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
            }
        return status

    def _compose_state(self, topics: list, google_rows: list, now: float) -> dict:
        def result_items(source):
            result = self.results.get(source)
            return result.items if result and result.ok else []

        tiktok_result = self.results.get("tiktok")
        news_result = self.results.get("news")
        efem = self.results.get("efemerides")
        topic_by_key = {t["key"]: t for t in topics}
        rising = [t for t in topics if t["phase"] in ("explosivo", "subiendo", "temprana") and not t["utility"]]
        rising.sort(key=lambda t: -t["potential"])
        google_items = result_items("google")
        for item in google_items:
            item["niche"] = self._google_niche(item)
        x_items = result_items("x")
        for item in x_items:
            item["niche"] = classify(item["title"])[0]
        for item in result_items("tiktok"):
            item["niche"] = classify(item["name"], base=item.get("niche_hint"), prior=1.0)[0]

        return {
            "app": {"name": APP_NAME, "version": APP_VERSION, "demo": bool(self.demo_loader)},
            "generated_at": now,
            "niches": [{"id": nid, "name": name} for nid, name in NICHES],
            "sources": self._source_status(),
            "topics": topics[:220],
            "kpis": analysis.kpis(topics, self.results),
            "niche_stats": analysis.niche_stats([t for t in topics if not t["utility"]]),
            "predictions": {
                "rising": [t["key"] for t in rising[:20]],
                "niche_momentum": analysis.niche_momentum(google_rows, now),
                "lifecycle": analysis.lifecycle_stats(google_rows),
            },
            "platforms": {
                "google": google_items,
                "x": x_items,
                "tiktok": {
                    "hashtags": result_items("tiktok"),
                    "songs": (tiktok_result.meta or {}).get("songs", []) if tiktok_result and tiktok_result.ok else [],
                    "browse_url": tiktok.BROWSE_URL,
                },
                "wikipedia": result_items("wikipedia"),
                "news": {
                    "items": result_items("news"),
                    "sections": (news_result.meta or {}).get("sections", {}) if news_result and news_result.ok else {},
                    "labels": news.SECTION_LABELS,
                },
                "youtube": [dict(i, topic=topic_by_key.get(i.get("topic_key"), {}).get("title")) for i in result_items("youtube")],
            },
            "efemerides": {
                "days": efem.items if efem and efem.ok else [],
                "highlights": (efem.meta or {}).get("highlights", []) if efem and efem.ok else [],
            },
        }

    def get_state(self) -> dict:
        with self._lock:
            state = dict(self.state)
        state["sources"] = self._source_status()
        state["refreshing"] = self.refreshing
        state["progress"] = dict(self.progress)
        state["last_error"] = self.last_error
        return state

    def status(self) -> dict:
        return {
            "refreshing": self.refreshing,
            "progress": dict(self.progress),
            "generated_at": self.state.get("generated_at"),
            "last_error": self.last_error,
        }

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
            detail["youtube"] = (demo.get("youtube") or {}).get(topic_key) or next(iter((demo.get("youtube") or {}).values()), None)
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
                result = youtube.competition(topic["query"])
                result.update({"topic_key": topic_key, "topic_title": topic["title"]})
                self._youtube_cache[topic_key] = result
                detail["youtube"] = result
            except Exception as exc:
                errors.append(f"YouTube: {exc}")
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
