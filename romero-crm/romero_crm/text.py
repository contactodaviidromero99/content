from __future__ import annotations

import re
import unicodedata

STOPWORDS = {
    "el", "la", "los", "las", "lo", "de", "del", "y", "e", "o", "u", "en", "a", "al",
    "un", "una", "unos", "unas", "con", "por", "para", "sin", "que", "se", "su", "sus",
    "vs", "v", "the", "of", "and", "in", "on", "to", "for", "es", "hoy",
}

GENERIC_TOKENS = {
    "madrid", "barcelona", "valencia", "sevilla", "malaga", "bilbao", "zaragoza", "espana",
    "partido", "gobierno", "liga", "real", "club", "futbol", "final", "copa", "premio",
    "premios", "serie", "pelicula", "nuevo", "nueva", "ultima", "ultimo", "manana", "directo",
    "video", "noticias", "resultado", "resultados", "horario", "donde", "programa", "temporada",
    "capitulo", "estreno", "muerte", "muere", "fallece", "elecciones", "spain", "spanish",
}

ACRONYMS = {
    "ia", "ai", "dgt", "psoe", "pp", "vox", "erc", "pnv", "bce", "ipc", "smi", "nba", "ufc",
    "f1", "gta", "ps5", "eeuu", "usa", "onu", "otan", "ue", "aemet", "dana", "ibex", "cis",
    "ere", "ave", "itv", "ebau", "evau", "pau", "sepe", "dni", "nie", "iva", "irpf", "cgpj",
    "tve", "rtve", "ot", "uefa", "fifa", "acb", "atp", "wta", "mlb", "nfl", "pc", "tv",
}

LOWER_WORDS = {"de", "del", "la", "las", "el", "los", "y", "e", "o", "u", "en", "a", "al", "con", "por", "para", "vs", "sin"}

BRANDS = {
    "whatsapp": "WhatsApp", "iphone": "iPhone", "ipad": "iPad", "ios": "iOS", "macbook": "MacBook",
    "youtube": "YouTube", "tiktok": "TikTok", "chatgpt": "ChatGPT", "openai": "OpenAI", "playstation": "PlayStation",
    "laliga": "LaLiga", "linkedin": "LinkedIn", "xbox": "Xbox", "paypal": "PayPal", "ebay": "eBay",
    "netflix": "Netflix", "spotify": "Spotify", "instagram": "Instagram", "facebook": "Facebook",
    "deepseek": "DeepSeek", "mediamarkt": "MediaMarkt", "bizum": "Bizum", "renfe": "Renfe", "aena": "Aena",
}

_WORD_RE = re.compile(r"[0-9A-Za-zÁÉÍÓÚÑÜáéíóúñü]+")

FIRST_NAMES = set("""
adrian agustin alba alberto alejandra alejandro alex alfonso alicia alvaro amaia ana andrea andres angel angela
antonio aitana alexia belen beatriz borja bruno carla carlos carmen carolina cayetana cesar clara cristina cristiano
dani daniel david diego dolores eduardo elena elsa emilio enrique ernesto esperanza esteban eva fernando federico
felipe francisco fran gabriel gerard gloria gonzalo guillermo hector ignacio ines irene isabel isco ivan jaime javier
jesus joan joaquin jordi jorge jose josep juan julia julian julio laura leo leonor lionel lola lorena lucas lucia
luis luka manuel manu marc marcos margarita maria mario marta martin mateo miguel monica nacho natalia nerea nico
nicolas norma oscar pablo paco paola patricia pau paula pedro pepe pilar rafa rafael ramon raquel raul ricardo
roberto rocio rodrigo rosa rosalia ruben salvador samuel santiago sara sergio silvia sofia susana teresa tomas
vanesa vicente victor vinicius xavi yolanda donald kamala emmanuel vladimir volodimir benjamin giorgia ursula
estrella macarena inmaculada montserrat nuria eugenia blanca concha encarna pastora rocio isabel lourdes amparo
jaume jordi joan pere marti arnau oriol aitor iker unai jon mikel asier inigo gorka xabier
taylor kylian jude lamine novak jannik max lewis kim elon mark steve bill jeff sam
mariano alfredo arturo benito cristobal domingo emiliano fermin gregorio gustavo hugo jacinto jeronimo lorenzo
marcelino mauricio nestor octavio pascual rogelio sebastian valentin adela agata amelia angeles anabel araceli aurora
barbara candela celia consuelo diana elisa emma esther fatima gema gemma helena julieta leticia lidia luisa marina
mercedes miriam noelia olga pepa rebeca sandra sonia tamara veronica victoria virginia ximena zoe rosario remedios
matilde maribel mila chari mari juanpi kiko kico toni quique santi chema josema txema ana belen alberto
""".split())


def _fold(word: str) -> str:
    lower = word.lower()
    return strip_accents(lower) if len(lower) >= 5 else lower


def casing_map(texts) -> dict:
    counts = {}
    for text in texts:
        for index, match in enumerate(_WORD_RE.finditer(text or "")):
            word = match.group(0)
            if index == 0 or len(word) < 2:
                continue
            bucket = counts.setdefault(_fold(word), {})
            bucket[word] = bucket.get(word, 0) + 1
    mapping = {}
    for folded, forms in counts.items():
        best = max(forms.items(), key=lambda kv: kv[1])[0]
        if best != folded and forms.get(best, 0) >= forms.get(folded, 0):
            mapping[folded] = best
    return mapping


def recase(text: str, mapping: dict) -> str:
    text = (text or "").strip()
    if not text or any(c.isupper() for c in text):
        return text

    def fix(match):
        word = match.group(0)
        base = strip_accents(word).lower()
        if base in BRANDS:
            return BRANDS[base]
        if base in ACRONYMS:
            return word.upper()
        return mapping.get(_fold(word), word)

    out = _WORD_RE.sub(fix, text)
    words = out.split(" ")
    for index, word in enumerate(words[:-1]):
        if strip_accents(word).lower() in FIRST_NAMES:
            words[index] = word[:1].upper() + word[1:]
            for nxt in range(index + 1, min(index + 3, len(words))):
                following = words[nxt]
                if strip_accents(following).lower() not in LOWER_WORDS:
                    words[nxt] = following[:1].upper() + following[1:]
                    break
    out = " ".join(words)
    out = re.sub(r"\bc\. ?f\.", "C. F.", out)
    out = out[:1].upper() + out[1:]
    return re.sub(r"(\s[-–]\s)(\w)", lambda m: m.group(1) + m.group(2).upper(), out)

_CAMEL_RE = re.compile(r"(?<=[a-záéíóúñü])(?=[A-ZÁÉÍÓÚÑÜ])|(?<=[A-Za-zÁÉÍÓÚÑÜáéíóúñü])(?=\d)|(?<=\d)(?=[A-Za-z])")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def split_hashtag(text: str) -> str:
    return _CAMEL_RE.sub(" ", (text or "").strip().lstrip("#"))


def norm(text: str) -> str:
    text = strip_accents(split_hashtag(text or "")).lower()
    return " ".join(_NON_ALNUM.sub(" ", text).split())


def key(text: str) -> str:
    return norm(text).replace(" ", "")


def tokens(text: str) -> list:
    return [t for t in norm(text).split() if t not in STOPWORDS and len(t) > 1]


def smart_title(text: str) -> str:
    text = (text or "").strip()
    if not text or any(c.isupper() for c in text):
        return text
    words = text.split(" ")
    out = []
    for index, word in enumerate(words):
        base = strip_accents(word).lower()
        if base in BRANDS:
            out.append(BRANDS[base])
        elif base in ACRONYMS:
            out.append(word.upper())
        elif index > 0 and base in LOWER_WORDS:
            out.append(word)
        else:
            out.append(word[:1].upper() + word[1:])
    return " ".join(out)


_NUM_RE = re.compile(
    r"(\d+(?:[.,]\d+)*)\s*(millones|millon|million|thousand|mil|bn|k|m|b)?(?![a-z])",
    re.I,
)
_MULTIPLIERS = {
    "k": 1e3, "mil": 1e3, "thousand": 1e3,
    "m": 1e6, "millon": 1e6, "millones": 1e6, "million": 1e6,
    "b": 1e9, "bn": 1e9,
}


def parse_compact_number(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = strip_accents(str(value)).lower().replace("\xa0", " ").strip()
    match = _NUM_RE.search(text)
    if not match:
        return None
    number, unit = match.group(1), (match.group(2) or "").lower()
    try:
        if unit:
            number = number.replace(",", ".")
            if number.count(".") > 1:
                head, _, tail = number.rpartition(".")
                number = head.replace(".", "") + "." + tail
            amount = float(number) * _MULTIPLIERS[unit]
        else:
            amount = float(re.sub(r"[.,]", "", number))
    except (ValueError, KeyError):
        return None
    return int(round(amount))


def parse_duration(text):
    if not text:
        return None
    parts = re.findall(r"\d+", str(text))
    if not parts or ":" not in str(text):
        return None
    seconds = 0
    for part in parts[-3:]:
        seconds = seconds * 60 + int(part)
    return seconds


_AGO_UNITS = (
    (("second", "segundo", "sec", "seg"), 1),
    (("minute", "minuto", "min"), 60),
    (("hour", "hora", "hr", "h"), 3600),
    (("day", "dia", "d"), 86400),
    (("week", "semana"), 7 * 86400),
    (("month", "mes"), 30 * 86400),
    (("year", "ano"), 365 * 86400),
)


def parse_ago_seconds(text):
    if not text:
        return None
    clean = strip_accents(str(text)).lower()
    match = re.search(r"(\d+)\s*([a-z]+)", clean)
    if not match:
        return None
    amount, unit = int(match.group(1)), match.group(2)
    for names, seconds in _AGO_UNITS:
        if any(unit.startswith(name) for name in names):
            return amount * seconds
    return None


def fmt_number(value) -> str:
    if value is None:
        return "—"
    value = float(value)
    for limit, suffix in ((1e6, " M"), (1e3, " mil")):
        if abs(value) >= limit:
            number = value / limit
            text = f"{number:.1f}".rstrip("0").rstrip(".") if number < 10 else f"{number:.0f}"
            return text.replace(".", ",") + suffix
    return f"{value:.0f}"


def clean_html_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return " ".join(text.split())
