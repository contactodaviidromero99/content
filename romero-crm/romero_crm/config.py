from __future__ import annotations

import copy
import json
import os
import sys
import threading
from pathlib import Path

from . import APP_NAME

SOURCE_IDS = ("google", "youtube", "x", "wikipedia", "news")

DEFAULT_SETTINGS = {
    "refresh_minutes": 30,
    "hide_utility": True,
    "theme": "system",
    "youtube_topics": 8,
    "name": "",
    "sources": {sid: True for sid in SOURCE_IDS},
}


def data_dir() -> Path:
    override = os.environ.get("ROMERO_CRM_DATA")
    if override:
        path = Path(override).expanduser()
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / APP_NAME
    elif os.name == "nt":
        path = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_NAME
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        path = Path(base) / "romero-crm"
    path.mkdir(parents=True, exist_ok=True)
    (path / "cache").mkdir(exist_ok=True)
    return path


def _clamp_int(value, low, high, default):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


class Settings:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self._data = copy.deepcopy(DEFAULT_SETTINGS)
        if path.exists():
            try:
                self._apply(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                pass

    def get(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._data)

    def update(self, patch: dict) -> dict:
        with self._lock:
            self._apply(patch)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)
            return copy.deepcopy(self._data)

    def _apply(self, patch: dict) -> None:
        if not isinstance(patch, dict):
            return
        if "refresh_minutes" in patch:
            self._data["refresh_minutes"] = _clamp_int(patch["refresh_minutes"], 10, 240, 30)
        if "youtube_topics" in patch:
            self._data["youtube_topics"] = _clamp_int(patch["youtube_topics"], 0, 20, 8)
        if "hide_utility" in patch:
            self._data["hide_utility"] = bool(patch["hide_utility"])
        if isinstance(patch.get("name"), str):
            self._data["name"] = " ".join("".join(c for c in patch["name"] if c.isprintable()).split())[:40]
        if patch.get("theme") in ("system", "light", "dark"):
            self._data["theme"] = patch["theme"]
        sources = patch.get("sources")
        if isinstance(sources, dict):
            for sid in SOURCE_IDS:
                if sid in sources:
                    self._data["sources"][sid] = bool(sources[sid])
