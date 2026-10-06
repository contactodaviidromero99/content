from __future__ import annotations

import copy
import json
import os
import sys
import threading
from pathlib import Path

from . import DATA_FOLDER

SOURCE_IDS = ("google", "youtube", "x", "wikipedia", "news")
SECRET_FIELDS = ("instagram_token", "ai_key")

DEFAULT_SETTINGS = {
    "refresh_minutes": 30,
    "hide_utility": True,
    "theme": "system",
    "effects": True,
    "youtube_topics": 8,
    "name": "",
    "sources": {sid: True for sid in SOURCE_IDS},
    "youtube_channel": "",
    "youtube_channel_id": "",
    "instagram_token": "",
    "instagram_token_at": 0,
    "ai_key": "",
}


def data_dir() -> Path:
    override = os.environ.get("ROMERO_CRM_DATA")
    if override:
        path = Path(override).expanduser()
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / DATA_FOLDER
    elif os.name == "nt":
        path = Path(os.environ.get("APPDATA", str(Path.home()))) / DATA_FOLDER
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


def _clean_secret(value) -> str:
    return "".join(c for c in str(value or "") if c.isprintable() and not c.isspace())[:600]


class Settings:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self._data = copy.deepcopy(DEFAULT_SETTINGS)
        if path.exists():
            try:
                self._apply(json.loads(path.read_text(encoding="utf-8")), trusted=True)
            except (OSError, ValueError):
                pass

    def get(self) -> dict:
        with self._lock:
            return copy.deepcopy(self._data)

    def public(self) -> dict:
        """Los ajustes para la interfaz: las claves nunca salen enteras, solo si están puestas."""
        data = self.get()
        for field in SECRET_FIELDS:
            value = data.pop(field, "")
            data[f"{field}_set"] = bool(value)
            data[f"{field}_hint"] = f"…{value[-4:]}" if len(value) > 8 else ""
        data.pop("instagram_token_at", None)
        return data

    def update(self, patch: dict, trusted: bool = False) -> dict:
        with self._lock:
            self._apply(patch, trusted)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
            tmp.replace(self.path)
            return copy.deepcopy(self._data)

    def _apply(self, patch: dict, trusted: bool = False) -> None:
        if not isinstance(patch, dict):
            return
        if "refresh_minutes" in patch:
            self._data["refresh_minutes"] = _clamp_int(patch["refresh_minutes"], 10, 240, 30)
        if "youtube_topics" in patch:
            self._data["youtube_topics"] = _clamp_int(patch["youtube_topics"], 0, 20, 8)
        for flag in ("hide_utility", "effects"):
            if flag in patch:
                self._data[flag] = bool(patch[flag])
        if isinstance(patch.get("name"), str):
            self._data["name"] = " ".join("".join(c for c in patch["name"] if c.isprintable()).split())[:40]
        if patch.get("theme") in ("system", "light", "dark"):
            self._data["theme"] = patch["theme"]
        sources = patch.get("sources")
        if isinstance(sources, dict):
            for sid in SOURCE_IDS:
                if sid in sources:
                    self._data["sources"][sid] = bool(sources[sid])
        if isinstance(patch.get("youtube_channel"), str):
            channel = " ".join(patch["youtube_channel"].split())[:200]
            if channel != self._data["youtube_channel"]:
                self._data["youtube_channel"] = channel
                self._data["youtube_channel_id"] = ""
        for field in SECRET_FIELDS:
            if field in patch:
                self._data[field] = _clean_secret(patch[field])
                if field == "instagram_token":
                    self._data["instagram_token_at"] = 0
        if trusted:
            if isinstance(patch.get("youtube_channel_id"), str):
                self._data["youtube_channel_id"] = patch["youtube_channel_id"][:40]
            if isinstance(patch.get("instagram_token_at"), (int, float)):
                self._data["instagram_token_at"] = int(patch["instagram_token_at"])
