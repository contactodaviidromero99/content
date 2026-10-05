from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Optional

SOURCE_LABELS = {
    "google": "Google Trends",
    "youtube": "YouTube",
    "x": "X (Twitter)",
    "wikipedia": "Wikipedia",
    "news": "Noticias",
    "efemerides": "Efemérides",
    "google_week": "Google (7 días)",
}


@dataclass
class SourceResult:
    source: str
    ok: bool
    items: list = field(default_factory=list)
    error: Optional[str] = None
    fetched_at: float = field(default_factory=time.time)
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SourceResult":
        return cls(
            source=data.get("source", ""),
            ok=bool(data.get("ok")),
            items=data.get("items") or [],
            error=data.get("error"),
            fetched_at=float(data.get("fetched_at") or 0),
            meta=data.get("meta") or {},
        )


def failure(source: str, exc: Exception) -> SourceResult:
    message = str(exc) or exc.__class__.__name__
    if "ConnectionError" in exc.__class__.__name__ or "Max retries" in message:
        message = "Sin conexión con el servicio. Revisa tu conexión a internet."
    elif "Timeout" in exc.__class__.__name__:
        message = "El servicio tardó demasiado en responder."
    return SourceResult(source=source, ok=False, error=message[:300])


def pick(data: dict, *names, default=None):
    for name in names:
        if isinstance(data, dict) and data.get(name) not in (None, ""):
            return data[name]
    return default
