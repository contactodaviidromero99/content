"""Historias: une los temas que son la misma noticia (unas elecciones = «Pedro Sánchez» + «Feijóo» +
«coalición de izquierdas»), cuenta qué ha pasado, sugiere cómo enfocar el vídeo con datos reales y
elige la portada: las cinco historias que más importan ahora, con prioridad para España."""
from __future__ import annotations

import datetime as dt
import re
import time

from .analysis import PHASE_LABELS, SOURCE_ORDER, dedupe_news, story_phrases
from .explain import clean_headline, headline_score, qualifies
from .niches import NICHE_NAMES
from .text import FIRST_NAMES, GENERIC_TOKENS, fmt_number, key, norm, strip_accents, tokens

PORTADA_SIZE = 5
MAX_TOPICS = 7
PHASE_RANK = {"explosivo": 4, "subiendo": 3, "temprana": 2, "pico": 1, "enfriandose": 0}
PHASE_BONUS = {"explosivo": 6, "subiendo": 4, "temprana": 2, "pico": 0, "enfriandose": -12}

# Palabras que nombran un acontecimiento: si una historia junta «Pedro Sánchez» y «Elecciones generales»,
# el título de la historia es el acontecimiento, no la persona.
EVENT_WORDS = {
    "elecciones", "huelga", "juicio", "caso", "sentencia", "dana", "terremoto", "incendio", "incendios", "apagon",
    "final", "debate", "premio", "premios", "gala", "guerra", "cumbre", "investidura", "mocion", "presupuestos", "ley",
    "reforma", "manifestacion", "atentado", "accidente", "crisis", "inundaciones", "temporal", "erupcion", "boda",
    "funeral", "muerte", "detencion", "acuerdo", "aranceles", "eurovision", "mundial", "nobel", "goya", "oscar",
    "oscars", "concierto", "estreno", "dimision", "referendum", "amnistia", "tormenta", "borrasca", "huracan",
    "caida", "coalicion", "pacto", "encuesta", "sondeo", "votacion", "sorteo", "derbi", "clasico",
}

_SPAIN = [
    "espana", "espanol", "espanola", "espanoles", "espanolas", "moncloa", "congreso de los diputados", "senado",
    "psoe", "pp", "partido popular", "vox", "sumar", "podemos", "junts", "erc", "pnv", "bildu", "pedro sanchez",
    "sanchez", "feijoo", "abascal", "yolanda diaz", "ayuso", "puigdemont", "illa", "generalitat", "xunta",
    "junta de andalucia", "guardia civil", "policia nacional", "mossos", "ertzaintza", "aemet", "dgt", "renfe",
    "adif", "aena", "casa real", "rey felipe", "felipe vi", "leonor", "letizia", "juan carlos", "laliga", "la liga",
    "real madrid", "barca", "fc barcelona", "atletico de madrid", "madrid", "barcelona", "cataluna", "catalunya",
    "andalucia", "galicia", "euskadi", "pais vasco", "comunidad valenciana", "comunitat valenciana", "valencia",
    "canarias", "baleares", "mallorca", "aragon", "asturias", "murcia", "navarra", "extremadura", "castilla",
    "cantabria", "la rioja", "ceuta", "melilla", "sevilla", "malaga", "bilbao", "zaragoza", "alicante", "cordoba",
    "valladolid", "vigo", "gijon", "granada", "cadiz", "toledo", "salamanca", "cuenca", "huelva", "almeria",
    "jaen", "leon", "burgos", "tenerife", "las palmas", "san sebastian", "donostia", "pamplona", "santander",
    "inditex", "mercadona", "telefonica", "iberdrola", "repsol", "bbva", "caixabank", "el corte ingles",
    "tribunal supremo", "audiencia nacional", "tribunal constitucional", "fiscal general", "cgpj", "rtve",
    "selección española", "seleccion espanola", "la roja", "franco", "franquismo", "guerra civil",
]
_WORLD = [
    "eeuu", "estados unidos", "trump", "biden", "casa blanca", "washington", "rusia", "putin", "kremlin", "ucrania",
    "zelenski", "kiev", "china", "pekin", "xi jinping", "taiwan", "israel", "gaza", "hamas", "netanyahu", "iran",
    "teheran", "francia", "macron", "paris", "alemania", "merz", "berlin", "reino unido", "londres", "starmer",
    "italia", "meloni", "roma", "mexico", "argentina", "milei", "venezuela", "maduro", "colombia", "brasil",
    "lula", "japon", "corea del norte", "corea del sur", "india", "pakistan", "turquia", "erdogan", "siria",
    "libano", "marruecos", "argelia", "vaticano", "papa leon", "onu", "otan", "bruselas", "union europea",
    "von der leyen", "kamala harris", "cisjordania", "yemen", "afganistan", "irak", "egipto", "sudan", "haiti",
    "cuba", "chile", "peru", "ecuador", "bolivia", "canada", "australia", "polonia", "hungria", "grecia",
    "portugal", "suecia", "noruega", "finlandia", "dinamarca", "groenlandia", "panama",
]
_ROUTINE_TV = [
    "gran hermano", "la revuelta", "el hormiguero", "pasapalabra", "masterchef", "supervivientes", "first dates",
    "la isla de las tentaciones", "operacion triunfo", "tu cara me suena", "la voz", "suenos de libertad",
    "la promesa", "got talent", "bake off", "mask singer", "la ruleta de la suerte", "saber y ganar",
    "el cazador", "ahora caigo", "cuarto milenio", "el desafio", "telediario", "la resistencia", "zapeando",
    "el intermedio", "espejo publico", "el programa de ana rosa", "la familia de la tele", "fiesta",
    "y ahora sonsoles", "la ruleta", "joya de la corona", "gh vip", "gh duo",
]
_FIXTURE = re.compile(r"\S\s+(?:-|–|vs\.?|v)\s+\S", re.I)
_QUESTION = re.compile(r"^(?:que|quien|quienes|por que|porque|como|cuando|donde|cuanto|cuantos|cuantas|cual|cuales|a que)\b")
_OLD_YEAR = re.compile(r"\b(?:1[0-8]\d\d|19[0-6]\d|197[0-5])\b|\ba\.\s?c\.?")

NICHE_TIPS = {
    "politica": "Explica qué cambia para la gente y quién gana o pierde con esto.",
    "internacional": "Cuéntalo desde España: qué significa aquí y qué precedente tiene.",
    "economia": "Tradúcelo a euros: cuánto le cuesta o le ahorra a una persona normal.",
    "actualidad": "Ciñete a lo verificado: cronología clara y fuentes, nada de especular.",
    "deportes": "Más que el resultado, la historia de una persona que hay detrás.",
    "entretenimiento": "Cuenta lo que no se ve: el origen, la polémica o el dato que nadie da.",
    "musica": "Cuenta lo que no se ve: el origen, la polémica o el dato que nadie da.",
    "historia": "Busca el detalle concreto (una persona, un objeto, una cifra) que lo haga visual.",
    "tecnologia": "Explícalo con una imagen que entienda cualquiera, sin tecnicismos.",
    "ciencia": "Explícalo con una imagen que entienda cualquiera, sin tecnicismos.",
    "clima": "Lo útil primero (dónde y cuándo) y después el porqué.",
    "salud": "Datos oficiales y una explicación sencilla; evita el alarmismo.",
}


def _compile(phrases):
    unique = sorted({norm(p) for p in phrases if norm(p)}, key=len, reverse=True)
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(p) for p in unique) + r")(?![a-z0-9])")


_SPAIN_RX = _compile(_SPAIN)
_WORLD_RX = _compile(_WORLD)
_ROUTINE_RX = _compile(_ROUTINE_TV)


def _phrase_rx(phrase: str):
    return re.compile(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])")


def title_phrases(title: str) -> list:
    """Frases que identifican un tema en otros textos. Para personas («Pedro Sánchez») también vale el
    apellido, pero como prueba débil: hay muchos Sánchez."""
    out = [(p, True) for p in story_phrases(title)]
    words = tokens(title)
    if len(words) >= 2 and strip_accents(words[0]) in FIRST_NAMES:
        surname = words[-1]
        if len(surname) >= 5 and surname not in GENERIC_TOKENS:
            out.append((surname, False))
    return out


def _headline_ident(title: str) -> str:
    return key(clean_headline(title or ""))[:60]


class _Group:
    """Temas que ya sabemos que van juntos (una tendencia de X ligada a su historia de Google)."""

    def __init__(self, topics: list):
        self.topics = sorted(topics, key=lambda t: (-t["heat"], -t["potential"]))
        self.heat = self.topics[0]["heat"]
        self.niches = set()
        for topic in topics:
            self.niches.update(topic.get("niches") or [topic["niche"]])
        self.niches.discard("otros")
        heads = [n.get("title") or "" for t in topics for n in (t.get("news") or {}).get("items") or []]
        self.headline_keys = {_headline_ident(h) for h in heads if h}
        self.headlines_text = "\n".join(norm(h) for h in heads)
        self.related_text = "\n".join(norm(r) for t in topics for r in (t.get("related") or []))
        self.titles_text = "\n".join(norm(t["title"]) for t in topics)
        self.phrases = [(_phrase_rx(p), strong) for t in topics for p, strong in title_phrases(t["title"])]


def _hits(rx, text: str) -> int:
    return len(rx.findall(text)) if text else 0


def evidence(a: _Group, b: _Group) -> int:
    """Cuánto indica que dos grupos de temas son la misma historia."""
    score = 3 * min(len(a.headline_keys & b.headline_keys), 2)
    for x, y in ((a, b), (b, a)):
        for rx, strong in x.phrases:
            if _hits(rx, y.titles_text):
                score += 2 if strong else 1
            if _hits(rx, y.related_text):
                score += 2 if strong else 1
            found = _hits(rx, y.headlines_text)
            if found >= 2:
                score += 2 if strong else 1
            elif found == 1 and strong:
                score += 1
    return score


def _needed(a: _Group, b: _Group) -> int:
    return 3 if (a.niches & b.niches or not a.niches or not b.niches) else 5


def cluster(topics: list) -> list:
    """Agrupa los temas en historias. Cada grupo se une, como mucho, al grupo más caliente con el que
    comparte titulares, búsquedas o nombres: así un tema nunca une dos historias distintas."""
    by_key = {t["key"]: t for t in topics}
    parent = {t["key"]: t["key"] for t in topics}

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for topic in topics:
        anchor = (topic.get("story") or {}).get("key")
        if anchor in by_key:
            parent[find(topic["key"])] = find(anchor)
    seeds = {}
    for topic in topics:
        seeds.setdefault(find(topic["key"]), []).append(topic)
    groups = sorted((_Group(members) for members in seeds.values()), key=lambda g: -g.heat)

    clusters, cluster_of = [], {}
    for index, group in enumerate(groups):
        best, best_score = None, 0
        for other in range(index):
            score = evidence(group, groups[other])
            if score >= _needed(group, groups[other]) and score > best_score:
                best, best_score = other, score
        if best is not None:
            target = cluster_of[best]
            if sum(len(groups[i].topics) for i in clusters[target]) + len(group.topics) <= MAX_TOPICS:
                cluster_of[index] = target
                clusters[target].append(index)
                continue
        cluster_of[index] = len(clusters)
        clusters.append([index])
    return [[t for i in members for t in groups[i].topics] for members in clusters]


def is_event(title: str) -> bool:
    return any(t in EVENT_WORDS for t in tokens(title))


def is_routine(title: str, niche: str) -> bool:
    """Partidos y programas de cada semana: suben mucho, pero rara vez son una noticia para contar."""
    if niche == "deportes" and _FIXTURE.search(title or ""):
        return True
    return bool(_ROUTINE_RX.search(norm(title)))


def scope_of(text: str, niches: list) -> str:
    """«espana» si la historia tiene protagonistas o lugares españoles; «mundo» si es de fuera."""
    plain = norm(text)
    spain = len(_SPAIN_RX.findall(plain))
    world = len(_WORLD_RX.findall(plain))
    if spain and spain >= world:
        return "espana"
    if "internacional" in niches or world:
        return "mundo"
    return "espana"


def _overlap(a: str, b: str) -> float:
    ta, tb = set(tokens(a)), set(tokens(b))
    return len(ta & tb) / max(1, min(len(ta), len(tb)))


def _lead(ordered: list) -> dict:
    root = ordered[0]
    if is_event(root["title"]):
        return root
    for topic in ordered[1:4]:
        if topic["heat"] >= root["heat"] - 12 and is_event(topic["title"]):
            return topic
    return root


def _synopsis(lead: dict, ordered: list, news: list) -> list:
    """Qué ha pasado: el titular que lo explica y, si aporta algo nuevo, un segundo titular de otro medio."""
    why = lead.get("why") or next((t["why"] for t in ordered if t.get("why")), None)
    lines = []
    if why:
        lines.append({"text": why["title"], "source": why.get("source"), "published": why.get("published"), "url": why.get("url")})
    for item in news:
        if len(lines) >= 2:
            break
        text = clean_headline(item.get("title") or "")
        if len(text) < 25 or not any(qualifies(t, item) for t in ordered):
            continue
        if lines and (_overlap(text, lines[0]["text"]) >= 0.5 or (item.get("source") and item.get("source") == lines[0].get("source"))):
            continue
        lines.append({"text": text, "source": item.get("source"), "published": item.get("published"), "url": item.get("url")})
    return lines


def _efemeride_match(story_text: str, efemerides: list):
    for item in efemerides or []:
        title = item.get("title") or ""
        phrase = norm(title)
        if len(tokens(title)) < 2 or phrase in GENERIC_TOKENS:
            continue
        if _phrase_rx(phrase).search(story_text):
            return item
    return None


def angle(story: dict, ordered: list, efemerides: list = None) -> dict:
    """Cómo enfocar el vídeo, solo con datos: el momento (fase y competencia en YouTube) y pistas
    concretas sacadas de lo que la gente busca, de lo que ya funciona y de la propia historia."""
    yt = story.get("youtube") or {}
    level = yt.get("level")
    phase = story["phase"]
    count = yt.get("count") or 0
    if phase in ("explosivo", "subiendo"):
        if level == "hueco":
            verdict, urgency = "Hazlo hoy: está despegando y casi nadie lo ha contado en vídeo.", "ahora"
        elif level == "saturado":
            verdict = f"El «qué ha pasado» ya está muy contado ({'20+' if count >= 20 else count} vídeos esta semana). Entra con un ángulo que no tenga nadie."
            urgency = "angulo"
        elif level == "moderado":
            verdict, urgency = "Hazlo hoy: hay algo de competencia, pero aún llegas a tiempo.", "hoy"
        else:
            verdict, urgency = "Está subiendo: si lo publicas en las próximas horas, llegas a tiempo.", "hoy"
    elif phase == "temprana":
        verdict, urgency = "Aún es pequeño, pero crece rápido. Si sigue así en 1-2 h, adelántate a todos.", "vigilar"
    elif phase == "pico":
        verdict, urgency = "Está en su techo: mejor una pieza de fondo que siga funcionando cuando pase la ola.", "fondo"
    else:
        verdict, urgency = "Se está apagando: solo merece la pena con un ángulo que no caduque.", "fondo"

    tips = []
    story_text = "\n".join([norm(t["title"]) for t in ordered] + [norm(n.get("title") or "") for n in story.get("news") or []])
    match = _efemeride_match(story_text, efemerides)
    if match:
        tips.append(f"Coincide con un aniversario: {match['years_ago']} años de «{match['title']}» ({_day_text(match['date'])}).")
    questions = [r for r in story.get("related") or [] if _QUESTION.search(norm(r))]
    if questions:
        tips.append(f"La gente pregunta «{questions[0]}»: respóndelo en los primeros segundos.")
    what = story.get("context") or {}
    if what.get("text") and (_OLD_YEAR.search(what["text"]) or story["niche"] == "historia"):
        tips.append(f"Tiene raíz histórica ({what.get('subject') or story['title']}: {what['text'][:1].lower() + what['text'][1:]}). Ahí está tu diferencia.")
    if yt.get("top_title") and level in ("moderado", "saturado") and (yt.get("top_views") or 0) >= 10_000:
        tips.append(f"Lo que más funciona ahora: «{yt['top_title']}» ({fmt_number(yt['top_views'])} visualizaciones). Cuenta lo que ese vídeo no cuenta.")
    members = [m["title"] for m in story.get("members") or []][:3]
    if len(members) >= 2:
        listed = ", ".join(members[:-1]) + f" y {members[-1]}"
        tips.append(f"Tiene varios frentes ({listed}): elige uno como protagonista en vez de resumirlo todo.")
    if not tips and NICHE_TIPS.get(story["niche"]):
        tips.append(NICHE_TIPS[story["niche"]])
    return {"verdict": verdict, "urgency": urgency, "tips": tips[:2]}


def _day_text(iso: str) -> str:
    months = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
              "noviembre", "diciembre")
    try:
        day = dt.date.fromisoformat(iso)
    except (TypeError, ValueError):
        return iso or ""
    return f"{day.day} de {months[day.month - 1]}"


def summary(story: dict) -> str:
    parts = []
    if story.get("volume"):
        parts.append(f"{fmt_number(story['volume'])}+ búsquedas en Google")
    if story.get("x_rank"):
        parts.append(f"nº {story['x_rank']} en X")
    if story.get("wiki_views"):
        parts.append(f"{fmt_number(story['wiki_views'])} lecturas en Wikipedia")
    if (story.get("outlets") or 0) >= 2:
        parts.append(f"lo cuentan {story['outlets']} medios")
    return " · ".join(parts[:3])


def is_alert(story: dict) -> bool:
    """Excepcional: lo busca muchísima gente, se comenta en todas partes y acaba de pasar. Es raro a propósito."""
    if story["routine"] or story["phase"] in ("enfriandose",):
        return False
    elapsed = story.get("elapsed_hours")
    if elapsed is not None and elapsed > 18:
        return False
    floor = 500_000 if story["scope"] == "mundo" else 200_000
    platforms = len([s for s in story["sources"] if s != "news"])
    loud = (story.get("x_rank") or 99) <= 3 or (story.get("outlets") or 0) >= 5
    return story["heat"] >= 85 and (story.get("volume") or 0) >= floor and loud and platforms >= 2


def _build(ordered: list, now: float, efemerides: list) -> dict:
    root = ordered[0]
    lead = _lead(ordered)
    hottest_phase = lead
    for topic in ordered[:3]:
        if topic["heat"] >= root["heat"] - 8 and PHASE_RANK.get(topic["phase"], 0) > PHASE_RANK.get(hottest_phase["phase"], 0):
            hottest_phase = topic
    volumes = {}
    for topic in ordered:
        google = topic.get("google")
        if google and google.get("volume"):
            volumes[google["id"]] = max(volumes.get(google["id"], 0), google["volume"])
    news = dedupe_news([n for t in ordered for n in (t.get("news") or {}).get("items") or []])
    lead_tokens = set(tokens(lead["title"]))
    news.sort(key=lambda n: -headline_score(n, lead_tokens, now))
    related, seen = [], set()
    for topic in ordered:
        for query in topic.get("related") or []:
            ident = norm(query)
            if ident and ident not in seen:
                seen.add(ident)
                related.append(query)
    youtube = lead.get("youtube") or next((t["youtube"] for t in ordered if t.get("youtube")), None)
    niches = []
    for topic in [lead] + ordered:
        for niche in topic.get("niches") or [topic["niche"]]:
            if niche not in niches and (niche != "otros" or not niches):
                niches.append(niche)
    niches = [n for n in niches if n != "otros"] or ["otros"]
    x_ranks = [t["x"]["rank"] for t in ordered if t.get("x")]
    wiki = [t["wikipedia"]["views"] for t in ordered if t.get("wikipedia")]
    text_for_scope = " ".join([t["title"] for t in ordered] + [n.get("title") or "" for n in news[:5]] + related[:6])
    members = [{"key": t["key"], "title": t["title"], "sources": t["sources"], "heat": t["heat"]}
               for t in ordered if t["key"] != lead["key"]]
    named = {norm(lead["title"])} | {norm(m["title"]) for m in members}
    for topic in ordered:
        extras = [dict(a, sources=a.get("sources") or []) for a in topic.get("angles") or []]
        extras += [{"key": None, "title": a["title"], "sources": [a["source"]]} for a in topic.get("aliases") or []]
        for extra in extras:
            if norm(extra["title"]) in named or extra.get("key") == lead["key"]:
                continue
            named.add(norm(extra["title"]))
            members.append({"key": extra.get("key"), "title": extra["title"], "sources": extra["sources"], "heat": None})
    context = None
    if lead.get("what"):
        context = {"subject": lead.get("what_subject") or lead["title"], "text": lead["what"]}
    story = {
        "key": lead["key"],
        "title": lead["title"],
        "topic_keys": [lead["key"]] + [t["key"] for t in ordered if t["key"] != lead["key"]],
        "members": members[:8],
        "niche": niches[0],
        "niches": niches[:3],
        "heat": max(t["heat"] for t in ordered),
        "potential": max(t["potential"] for t in ordered),
        "phase": hottest_phase["phase"],
        "phase_label": PHASE_LABELS[hottest_phase["phase"]],
        "phase_reason": hottest_phase.get("phase_reason") or "",
        "remaining_hours": hottest_phase.get("remaining_hours"),
        "typical_hours": hottest_phase.get("typical_hours"),
        "elapsed_hours": min((t["elapsed_hours"] for t in ordered if t.get("elapsed_hours") is not None), default=None),
        "started_at": min((t["started_at"] for t in ordered if t.get("started_at")), default=None),
        "volume": sum(volumes.values()),
        "trends": len(volumes),
        "x_rank": min(x_ranks) if x_ranks else None,
        "wiki_views": max(wiki) if wiki else None,
        "outlets": max([(t.get("news") or {}).get("outlets") or 0 for t in ordered] + [0]),
        "sources": [s for s in SOURCE_ORDER if any(s in t["sources"] for t in ordered)],
        "news": news[:10],
        "why": lead.get("why") or next((t["why"] for t in ordered if t.get("why")), None),
        "context": context,
        "related": related[:12],
        "youtube": youtube,
        "image": lead.get("image") or next((t["image"] for t in ordered if t.get("image")), None),
        "series": lead.get("series") or [],
        "series_kind": lead.get("series_kind"),
        "series_label": lead.get("series_label"),
        "series_end": lead.get("series_end"),
        "series_step": lead.get("series_step"),
        "growth_pct": lead.get("growth_pct"),
    }
    story["synopsis"] = _synopsis(lead, ordered, news)
    story["routine"] = is_routine(lead["title"], lead["niche"]) or is_routine(root["title"], root["niche"])
    story["scope"] = scope_of(text_for_scope, niches)
    story["summary"] = summary(story)
    story["angle"] = angle(story, ordered, efemerides)
    story["alert"] = is_alert(story)
    score = story["heat"] + PHASE_BONUS.get(story["phase"], 0) + 2 * min(len(ordered) - 1, 3)
    score += 6 if story["scope"] == "espana" else -6
    if story["routine"]:
        score -= 14
    if not story["why"] and not context:
        score -= 6
    story["score"] = round(score, 1)
    return story


def build_stories(topics: list, now: float = None, efemerides: list = None) -> list:
    now = now or time.time()
    candidates = [t for t in topics if not t["utility"]]
    stories = [_build(sorted(group, key=lambda t: (-t["heat"], -t["potential"])), now, efemerides) for group in cluster(candidates)]
    stories.sort(key=lambda s: (-s["score"], -s["heat"]))
    for rank, story in enumerate(stories, 1):
        story["rank"] = rank
    return stories


def portada(stories: list, size: int = PORTADA_SIZE) -> dict:
    """Las historias de la portada: primero lo excepcional (como mucho dos), después las mejor puntuadas."""
    alerts = [s for s in stories if s["alert"]][:2]
    chosen = list(alerts)
    for story in stories:
        if len(chosen) >= size:
            break
        if story not in chosen:
            chosen.append(story)
    return {"keys": [s["key"] for s in chosen], "alerts": [s["key"] for s in alerts]}


def upcoming_efemerides(days: list, today: dt.date = None, window: int = 10) -> list:
    """Aniversarios destacados cercanos (±window días), para avisar si una historia coincide con uno."""
    today = today or dt.date.today()
    out = []
    for day in days or []:
        try:
            date = dt.date.fromisoformat(day["date"])
        except (KeyError, TypeError, ValueError):
            continue
        if abs((date - today).days) <= window:
            out.extend(i for i in day.get("items") or [] if i.get("round_level", 0) >= 1)
    return out


def niche_label(niche: str) -> str:
    return NICHE_NAMES.get(niche, niche)
