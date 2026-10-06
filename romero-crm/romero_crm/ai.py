"""Ideas con Claude (opcional).

Con una clave de la API de Claude (Ajustes → Ideas con Claude), cada historia nueva de la portada recibe
una sinopsis, un enfoque de vídeo y un posible gancho escritos por Claude a partir de los datos reales
(titulares, cifras, lo que busca la gente y la competencia en YouTube). Sin clave no se hace ninguna
llamada y el programa funciona igual con su enfoque basado en datos.

Cada historia se pide una sola vez mientras no cambie su titular, así que el gasto es pequeño."""
from __future__ import annotations

import hashlib
import json
import time

try:
    import anthropic
except ImportError:  # el componente es opcional: si no está instalado, la función queda desactivada
    anthropic = None

MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
CACHE_TTL = 18 * 3600
MAX_STORIES = 6

SCHEMA = {
    "type": "object",
    "properties": {
        "historias": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "clave": {"type": "string"},
                    "titular": {"type": "string"},
                    "que_ha_pasado": {"type": "string"},
                    "enfoque": {"type": "string"},
                    "gancho": {"type": "string"},
                },
                "required": ["clave", "titular", "que_ha_pasado", "enfoque", "gancho"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["historias"],
    "additionalProperties": False,
}

SYSTEM = """Eres el colaborador de guion de {who}, que hace vídeos cortos (Reels, TikTok y Shorts) narrativos e históricos, de alta intensidad emocional e intelectual, en español de España.

Recibes varias historias que son tendencia ahora mismo en España, cada una con datos reales: titulares de medios, cifras de búsqueda, temas relacionados, lo que pregunta la gente y la competencia en YouTube.

Para cada historia devuelve:
- titular: la historia en 4 a 9 palabras, concreta y sin sensacionalismo.
- que_ha_pasado: una o dos frases claras con los hechos que dan los titulares. No añadas datos que no estén en el material; si algo no está claro, dilo.
- enfoque: cómo plantearías un vídeo corto sobre esto, en una o dos frases: el ángulo narrativo concreto que no es el obvio, por qué puede funcionar y qué conviene evitar. Ten en cuenta la competencia en YouTube y el margen que le queda a la tendencia.
- gancho: una posible primera frase del vídeo, de 15 palabras como mucho.

Escribe con precisión y sin fórmulas hechas: nada de tono épico forzado, preguntas retóricas vacías ni cierres cursis. Distingue hechos de interpretaciones. Si una historia no da para un vídeo de este estilo, dilo en el enfoque. Copia la clave de cada historia tal cual."""


class AIError(Exception):
    pass


def available() -> bool:
    return anthropic is not None


def fingerprint(story: dict) -> str:
    """Cambia cuando cambia lo esencial de la historia (su titular o sus temas), no con cada actualización."""
    basis = "|".join([story["key"], (story.get("why") or {}).get("title") or "",
                      ",".join(sorted(m["title"] for m in story.get("members") or []))])
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def story_brief(story: dict) -> dict:
    yt = story.get("youtube") or {}
    return {
        "clave": story["key"],
        "tema": story["title"],
        "incluye": [m["title"] for m in story.get("members") or []][:6],
        "nicho": story.get("niche"),
        "ambito": "internacional" if story.get("scope") == "mundo" else "España",
        "fase": story.get("phase_label"),
        "margen_horas": story.get("remaining_hours"),
        "cifras": story.get("summary"),
        "titulares": [n.get("title") for n in (story.get("news") or [])[:6] if n.get("title")],
        "contexto": (story.get("context") or {}).get("text"),
        "busquedas_relacionadas": (story.get("related") or [])[:8],
        "youtube": {
            "nivel": yt.get("label"),
            "videos_esta_semana": yt.get("count"),
            "mas_visto": yt.get("top_title"),
            "visualizaciones_del_mas_visto": yt.get("top_views"),
        } if yt else None,
    }


def cached(story: dict, cache: dict, now: float = None):
    entry = cache.get(story["key"])
    now = now or time.time()
    if entry and entry.get("fp") == fingerprint(story) and now - entry.get("at", 0) < CACHE_TTL:
        return entry["data"]
    return None


def attach(stories: list, cache: dict) -> None:
    for story in stories:
        data = cached(story, cache)
        if data:
            story["ai"] = data


def prune(cache: dict, now: float = None) -> dict:
    now = now or time.time()
    return {k: v for k, v in cache.items() if now - v.get("at", 0) < 3 * 86400}


def request(api_key: str, stories: list, who: str = "") -> list:
    """Pide a Claude las ideas de varias historias en una sola llamada. Devuelve una lista de dicts."""
    if anthropic is None:
        raise AIError("Falta el componente de Claude. Vuelve a ejecutar el instalador para añadirlo.")
    if not stories:
        return []
    client = anthropic.Anthropic(api_key=api_key, timeout=120.0, max_retries=2)
    payload = json.dumps({"historias": [story_brief(s) for s in stories]}, ensure_ascii=False, indent=1)
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
            system=SYSTEM.format(who=who or "un creador de contenido"),
            messages=[{"role": "user", "content": f"Historias de hoy:\n{payload}"}],
        )
    except anthropic.AuthenticationError:
        raise AIError("La clave de la API de Claude no es válida. Revísala en Ajustes.") from None
    except anthropic.PermissionDeniedError:
        raise AIError("Esa clave no tiene permiso para usar este modelo.") from None
    except anthropic.RateLimitError:
        raise AIError("Claude ha limitado las peticiones por ahora. Se reintentará más tarde.") from None
    except anthropic.BadRequestError as exc:
        message = str(getattr(exc, "message", "") or exc)
        if "credit" in message.lower() or "billing" in message.lower():
            raise AIError("No queda saldo en tu cuenta de la API de Claude (console.anthropic.com → Billing).") from None
        raise AIError(f"Claude rechazó la petición: {message[:200]}") from None
    except anthropic.APIStatusError as exc:
        raise AIError(f"La API de Claude respondió con un error ({exc.status_code}). Se reintentará más tarde.") from None
    except anthropic.APIConnectionError:
        raise AIError("Sin conexión con la API de Claude.") from None

    if response.stop_reason == "refusal":
        raise AIError("Claude no ha querido escribir sobre estas historias.")
    if response.stop_reason == "max_tokens":
        raise AIError("La respuesta de Claude se quedó a medias. Se reintentará más tarde.")
    text = next((block.text for block in response.content if block.type == "text"), "")
    try:
        data = json.loads(text)
    except ValueError:
        raise AIError("La respuesta de Claude no se pudo leer.") from None
    wanted = {s["key"] for s in stories}
    out = []
    for item in data.get("historias") or []:
        if isinstance(item, dict) and item.get("clave") in wanted:
            out.append({k: str(item.get(k) or "").strip()[:600] for k in ("clave", "titular", "que_ha_pasado", "enfoque", "gancho")})
    return out


def enrich(api_key: str, stories: list, cache: dict, who: str = "", now: float = None) -> int:
    """Rellena la caché con las ideas de las historias que aún no las tienen. Devuelve cuántas se pidieron."""
    now = now or time.time()
    missing = [s for s in stories if cached(s, cache, now) is None][:MAX_STORIES]
    if not missing:
        return 0
    by_key = {s["key"]: s for s in missing}
    for item in request(api_key, missing, who):
        story = by_key.get(item["clave"])
        if story:
            cache[story["key"]] = {"fp": fingerprint(story), "at": now, "data": {k: v for k, v in item.items() if k != "clave"}}
    return len(missing)
