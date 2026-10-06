from __future__ import annotations

import datetime as dt
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from .sources.base import SourceResult

SCHEMA = """
CREATE TABLE IF NOT EXISTS google_trends (
    id TEXT NOT NULL, started INTEGER NOT NULL, title TEXT, query TEXT, niche TEXT,
    volume INTEGER, growth REAL, ended INTEGER, active INTEGER, related TEXT, updated INTEGER,
    PRIMARY KEY (id, started)
);
CREATE TABLE IF NOT EXISTS topic_days (
    day TEXT NOT NULL, key TEXT NOT NULL, title TEXT, niche TEXT, sources TEXT, peak_heat REAL,
    peak_volume INTEGER, first_seen INTEGER, last_seen INTEGER, observations INTEGER,
    PRIMARY KEY (day, key)
);
CREATE TABLE IF NOT EXISTS observations (
    ts INTEGER NOT NULL, key TEXT NOT NULL, heat REAL, potential REAL, rank INTEGER
);
CREATE INDEX IF NOT EXISTS idx_observations_key ON observations (key, ts);
CREATE TABLE IF NOT EXISTS wiki_days (
    day TEXT NOT NULL, project TEXT NOT NULL, article TEXT NOT NULL, title TEXT, views INTEGER,
    rank INTEGER, niche TEXT, PRIMARY KEY (day, project, article)
);
CREATE TABLE IF NOT EXISTS google_snapshots (
    id TEXT NOT NULL, started INTEGER NOT NULL, ts INTEGER NOT NULL, volume INTEGER,
    PRIMARY KEY (id, started, ts)
);
CREATE INDEX IF NOT EXISTS idx_google_snapshots_ts ON google_snapshots (ts);
CREATE TABLE IF NOT EXISTS story_days (
    day TEXT NOT NULL, key TEXT NOT NULL, title TEXT, niche TEXT, scope TEXT, members TEXT, why TEXT,
    peak_heat REAL, peak_volume INTEGER, yt_count INTEGER, yt_top INTEGER, yt_top_title TEXT,
    first_seen INTEGER, last_seen INTEGER, observations INTEGER,
    PRIMARY KEY (day, key)
);
CREATE TABLE IF NOT EXISTS plan_items (
    id TEXT PRIMARY KEY, day TEXT NOT NULL, time TEXT, kind TEXT NOT NULL, title TEXT NOT NULL, notes TEXT,
    platforms TEXT, done INTEGER NOT NULL DEFAULT 0, done_at INTEGER, topic_key TEXT, topic_title TEXT,
    links TEXT, source TEXT, created INTEGER, updated INTEGER
);
CREATE INDEX IF NOT EXISTS idx_plan_items_day ON plan_items (day);
CREATE TABLE IF NOT EXISTS published (
    platform TEXT NOT NULL, vid TEXT NOT NULL, url TEXT, title TEXT, published_at INTEGER, views INTEGER,
    likes INTEGER, comments INTEGER, shares INTEGER, thumbnail TEXT, source TEXT, updated INTEGER,
    PRIMARY KEY (platform, vid)
);
CREATE INDEX IF NOT EXISTS idx_published_at ON published (published_at);
"""

PLAN_KINDS = ("publicar", "grabar", "editar", "guion", "idea", "otro")
PLAN_PLATFORMS = ("instagram", "tiktok", "youtube")


def local_day(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts).date().isoformat()


class Storage:
    def __init__(self, root: Path):
        self.root = root
        self.cache_dir = root / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(root / "romero.db"), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.executescript(SCHEMA)
            self._db.commit()

    def _write_json(self, path: Path, data) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    def _read_json(self, path: Path):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def save_result(self, result: SourceResult) -> None:
        self._write_json(self.cache_dir / f"source-{result.source}.json", result.to_dict())

    def load_results(self) -> dict:
        results = {}
        for path in self.cache_dir.glob("source-*.json"):
            data = self._read_json(path)
            if isinstance(data, dict) and data.get("source"):
                results[data["source"]] = SourceResult.from_dict(data)
        return results

    def save_state(self, state: dict) -> None:
        self._write_json(self.root / "state.json", state)

    def load_state(self):
        return self._read_json(self.root / "state.json")

    def load_json(self, name: str):
        return self._read_json(self.cache_dir / name)

    def save_json(self, name: str, data) -> None:
        self._write_json(self.cache_dir / name, data)

    def upsert_google(self, items: list, niche_of) -> None:
        now = int(time.time())
        rows = []
        for item in items:
            started = item.get("started_at") or 0
            rows.append((
                item["id"], started, item.get("title"), item.get("query"), niche_of(item),
                int(item.get("volume") or 0), item.get("growth_pct"), item.get("ended_at"),
                1 if item.get("active") else 0, json.dumps(item.get("related") or [], ensure_ascii=False), now,
            ))
        with self._lock:
            self._db.executemany(
                """INSERT INTO google_trends (id, started, title, query, niche, volume, growth, ended, active, related, updated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id, started) DO UPDATE SET
                     title=excluded.title, niche=excluded.niche, volume=MAX(volume, excluded.volume),
                     growth=excluded.growth, ended=excluded.ended, active=excluded.active,
                     related=excluded.related, updated=excluded.updated""",
                rows,
            )
            self._db.commit()

    def record_google_snapshots(self, items: list, ts: float) -> None:
        rows = [(i["id"], i.get("started_at") or 0, int(ts), int(i.get("volume") or 0))
                for i in items if i.get("active") and i.get("volume")]
        self.add_google_snapshots(rows)

    def add_google_snapshots(self, rows: list) -> None:
        with self._lock:
            self._db.executemany(
                "INSERT OR IGNORE INTO google_snapshots (id, started, ts, volume) VALUES (?, ?, ?, ?)", rows
            )
            self._db.commit()

    def google_snapshots(self, since_ts: float) -> list:
        with self._lock:
            cur = self._db.execute(
                "SELECT id, started, ts, volume FROM google_snapshots WHERE ts >= ? ORDER BY ts", (int(since_ts),)
            )
            return [dict(r) for r in cur.fetchall()]

    def record_topics(self, topics: list, ts: float) -> None:
        day = local_day(ts)
        with self._lock:
            for rank, topic in enumerate(topics, 1):
                volume = int((topic.get("metric") or {}).get("value") or 0)
                self._db.execute(
                    """INSERT INTO topic_days (day, key, title, niche, sources, peak_heat, peak_volume, first_seen, last_seen, observations)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                       ON CONFLICT(day, key) DO UPDATE SET
                         title=excluded.title, niche=excluded.niche,
                         sources=CASE WHEN length(excluded.sources) > length(sources) THEN excluded.sources ELSE sources END,
                         peak_heat=MAX(peak_heat, excluded.peak_heat), peak_volume=MAX(peak_volume, excluded.peak_volume),
                         last_seen=excluded.last_seen, observations=observations + 1""",
                    (day, topic["key"], topic["title"], topic["niche"], ",".join(topic["sources"]),
                     topic["heat"], volume, int(ts), int(ts)),
                )
                if rank <= 80:
                    self._db.execute(
                        "INSERT INTO observations (ts, key, heat, potential, rank) VALUES (?, ?, ?, ?, ?)",
                        (int(ts), topic["key"], topic["heat"], topic["potential"], rank),
                    )
            self._db.commit()

    def record_stories(self, stories: list, ts: float) -> None:
        day = local_day(ts)
        with self._lock:
            for story in stories:
                yt = story.get("youtube") or {}
                members = json.dumps([m["title"] for m in story.get("members") or []][:8], ensure_ascii=False)
                self._db.execute(
                    """INSERT INTO story_days (day, key, title, niche, scope, members, why, peak_heat, peak_volume,
                         yt_count, yt_top, yt_top_title, first_seen, last_seen, observations)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                       ON CONFLICT(day, key) DO UPDATE SET
                         title=excluded.title, niche=excluded.niche, scope=excluded.scope,
                         members=CASE WHEN length(excluded.members) > length(members) THEN excluded.members ELSE members END,
                         why=COALESCE(excluded.why, why),
                         peak_heat=MAX(peak_heat, excluded.peak_heat), peak_volume=MAX(peak_volume, excluded.peak_volume),
                         yt_count=MAX(COALESCE(yt_count, 0), COALESCE(excluded.yt_count, 0)),
                         yt_top=MAX(COALESCE(yt_top, 0), COALESCE(excluded.yt_top, 0)),
                         yt_top_title=CASE WHEN COALESCE(excluded.yt_top, 0) >= COALESCE(yt_top, 0)
                                           THEN COALESCE(excluded.yt_top_title, yt_top_title) ELSE yt_top_title END,
                         last_seen=excluded.last_seen, observations=observations + 1""",
                    (day, story["key"], story["title"], story["niche"], story.get("scope"), members,
                     (story.get("why") or {}).get("title"), story["heat"], int(story.get("volume") or 0),
                     yt.get("count"), yt.get("top_views"), yt.get("top_title"), int(ts), int(ts)),
                )
            self._db.commit()

    def story_day_rows(self, since_day: str, until_day: str = "9999-12-31") -> list:
        with self._lock:
            cur = self._db.execute(
                "SELECT * FROM story_days WHERE day >= ? AND day <= ? ORDER BY day DESC, peak_heat DESC", (since_day, until_day)
            )
            rows = [dict(r) for r in cur.fetchall()]
        for row in rows:
            try:
                row["members"] = json.loads(row.get("members") or "[]")
            except ValueError:
                row["members"] = []
        return rows

    # ---------- Calendario: tareas propias ----------

    @staticmethod
    def _plan_row(row) -> dict:
        item = dict(row)
        item["done"] = bool(item.get("done"))
        item["platforms"] = [p for p in (item.get("platforms") or "").split(",") if p]
        try:
            item["links"] = json.loads(item.get("links") or "[]")
        except ValueError:
            item["links"] = []
        return item

    def plan_items(self, since_day: str, until_day: str) -> list:
        with self._lock:
            cur = self._db.execute(
                "SELECT * FROM plan_items WHERE day >= ? AND day <= ? ORDER BY day, COALESCE(time, '99:99'), created",
                (since_day, until_day),
            )
            return [self._plan_row(r) for r in cur.fetchall()]

    def plan_item(self, item_id: str):
        with self._lock:
            row = self._db.execute("SELECT * FROM plan_items WHERE id = ?", (item_id,)).fetchone()
        return self._plan_row(row) if row else None

    def save_plan_item(self, data: dict) -> dict:
        """Crea o actualiza una tarea. `data` ya viene validado (planner.clean_item)."""
        now = int(time.time())
        current = self.plan_item(data["id"]) if data.get("id") else None
        item = dict(current or {"id": uuid.uuid4().hex[:12], "created": now, "done": False, "done_at": None, "links": [],
                                "platforms": [], "notes": "", "time": None, "topic_key": None, "topic_title": None,
                                "source": "manual"})
        item.update({k: v for k, v in data.items() if k != "id"})
        if item.get("done") and not (current or {}).get("done"):
            item["done_at"] = now
        elif not item.get("done"):
            item["done_at"] = None
        item["updated"] = now
        with self._lock:
            self._db.execute(
                """INSERT OR REPLACE INTO plan_items (id, day, time, kind, title, notes, platforms, done, done_at, topic_key,
                     topic_title, links, source, created, updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item["id"], item["day"], item.get("time"), item["kind"], item["title"], item.get("notes") or "",
                 ",".join(item.get("platforms") or []), 1 if item.get("done") else 0, item.get("done_at"),
                 item.get("topic_key"), item.get("topic_title"), json.dumps(item.get("links") or [], ensure_ascii=False),
                 item.get("source") or "manual", item["created"], item["updated"]),
            )
            self._db.commit()
        return self.plan_item(item["id"])

    def delete_plan_item(self, item_id: str) -> bool:
        with self._lock:
            cur = self._db.execute("DELETE FROM plan_items WHERE id = ?", (item_id,))
            self._db.commit()
            return cur.rowcount > 0

    # ---------- Vídeos publicados (conexiones) ----------

    def upsert_published(self, items: list) -> None:
        now = int(time.time())
        with self._lock:
            self._db.executemany(
                """INSERT INTO published (platform, vid, url, title, published_at, views, likes, comments, shares, thumbnail, source, updated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(platform, vid) DO UPDATE SET
                     url=excluded.url, title=COALESCE(excluded.title, title), published_at=COALESCE(excluded.published_at, published_at),
                     views=COALESCE(excluded.views, views), likes=COALESCE(excluded.likes, likes),
                     comments=COALESCE(excluded.comments, comments), shares=COALESCE(excluded.shares, shares),
                     thumbnail=COALESCE(excluded.thumbnail, thumbnail), source=excluded.source, updated=excluded.updated""",
                [(i["platform"], i["vid"], i.get("url"), i.get("title"), i.get("published_at"), i.get("views"), i.get("likes"),
                  i.get("comments"), i.get("shares"), i.get("thumbnail"), i.get("source"), now) for i in items],
            )
            self._db.commit()

    def published_between(self, since_ts: float, until_ts: float) -> list:
        with self._lock:
            cur = self._db.execute(
                "SELECT * FROM published WHERE published_at >= ? AND published_at < ? ORDER BY published_at",
                (int(since_ts), int(until_ts)),
            )
            return [dict(r) for r in cur.fetchall()]

    def upsert_wiki(self, items: list) -> None:
        with self._lock:
            self._db.executemany(
                """INSERT OR REPLACE INTO wiki_days (day, project, article, title, views, rank, niche)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [(i["day"], i["project"], i["url"].rsplit("/", 1)[-1], i["title"], i["views"], i["rank"], i.get("niche"))
                 for i in items if i.get("day")],
            )
            self._db.commit()

    def google_rows(self, since_ts: float) -> list:
        with self._lock:
            cur = self._db.execute(
                "SELECT * FROM google_trends WHERE started >= ? ORDER BY started DESC", (int(since_ts),)
            )
            return [dict(r) for r in cur.fetchall()]

    def oldest_day(self):
        """El primer día del que hay historial (para saber cuántas semanas se pueden consultar)."""
        with self._lock:
            days = [self._db.execute(f"SELECT MIN(day) FROM {table}").fetchone()[0] for table in ("story_days", "topic_days")]
            started = self._db.execute("SELECT MIN(started) FROM google_trends WHERE started > 0").fetchone()[0]
        if started:
            days.append(local_day(started))
        days = [d for d in days if d]
        return min(days) if days else None

    def topic_day_rows(self, since_day: str) -> list:
        with self._lock:
            cur = self._db.execute(
                "SELECT * FROM topic_days WHERE day >= ? ORDER BY day DESC, peak_heat DESC", (since_day,)
            )
            return [dict(r) for r in cur.fetchall()]

    def wiki_rows(self, since_day: str) -> list:
        with self._lock:
            cur = self._db.execute("SELECT * FROM wiki_days WHERE day >= ? ORDER BY day DESC, rank ASC", (since_day,))
            return [dict(r) for r in cur.fetchall()]

    def observations(self, key: str, since_ts: float) -> list:
        with self._lock:
            cur = self._db.execute(
                "SELECT ts, heat, potential, rank FROM observations WHERE key = ? AND ts >= ? ORDER BY ts",
                (key, int(since_ts)),
            )
            return [dict(r) for r in cur.fetchall()]

    def prune(self, keep_days: int = 180) -> None:
        cutoff = time.time() - keep_days * 86400
        day = local_day(cutoff)
        with self._lock:
            self._db.execute("DELETE FROM observations WHERE ts < ?", (int(time.time() - 45 * 86400),))
            self._db.execute("DELETE FROM google_snapshots WHERE ts < ?", (int(time.time() - 3 * 86400),))
            self._db.execute("DELETE FROM google_trends WHERE started < ?", (int(cutoff),))
            self._db.execute("DELETE FROM topic_days WHERE day < ?", (day,))
            self._db.execute("DELETE FROM story_days WHERE day < ?", (day,))
            self._db.execute("DELETE FROM wiki_days WHERE day < ?", (day,))
            self._db.commit()

    def clear_history(self) -> None:
        with self._lock:
            for table in ("google_trends", "topic_days", "story_days", "observations", "wiki_days", "google_snapshots"):
                self._db.execute(f"DELETE FROM {table}")
            self._db.commit()
        for path in self.cache_dir.glob("source-*.json"):
            path.unlink(missing_ok=True)
        (self.root / "state.json").unlink(missing_ok=True)
