from __future__ import annotations

import datetime as dt
import json
import sqlite3
import threading
import time
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
"""


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
            self._db.execute("DELETE FROM google_trends WHERE started < ?", (int(cutoff),))
            self._db.execute("DELETE FROM topic_days WHERE day < ?", (day,))
            self._db.execute("DELETE FROM wiki_days WHERE day < ?", (day,))
            self._db.commit()

    def clear_history(self) -> None:
        with self._lock:
            for table in ("google_trends", "topic_days", "observations", "wiki_days"):
                self._db.execute(f"DELETE FROM {table}")
            self._db.commit()
        for path in self.cache_dir.glob("source-*.json"):
            path.unlink(missing_ok=True)
        (self.root / "state.json").unlink(missing_ok=True)
