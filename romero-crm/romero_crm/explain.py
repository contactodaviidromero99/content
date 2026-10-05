"""Explicación breve de cada tema: qué es, por qué es tendencia y sus cifras en palabras."""
from __future__ import annotations

import re
import time

from .niches import classify
from .text import STOPWORDS, fmt_number, norm, strip_accents, tokens

_LIVE_WORDS = r"en directo|en vivo|minuto a minuto|última hora|ultima hora"
_LIVE_SEGMENT = re.compile(r"\b(?:%s)\b" % _LIVE_WORDS, re.I)
_LIVE_INLINE = re.compile(r",?\s*\b(?:en directo|en vivo|minuto a minuto)\b\s*[:|\-–—]?\s*", re.I)
_LEAD_TAG = re.compile(r"^(?:última hora|ultima hora|directo|v[íi]deo|fotos?|exclusiva|opini[óo]n)\s*[:|\-–—]\s*", re.I)
_DISAMBIGUATION = re.compile(r"desambiguaci|disambiguation|página de wikimedia|wikimedia list", re.I)
_GENERIC_TYPES = {
    "pagina", "lista", "articulo", "anexo", "ano", "dia", "concepto", "termino", "proceso", "conjunto",
    "tipo", "forma", "parte", "nombre", "apellido", "palabra", "accion", "evento", "edicion",
}


def clean_headline(title: str) -> str:
    text = " ".join((title or "").split())
    parts = [p.strip(" -–—") for p in re.split(r"\s+\|\s+", text) if p.strip(" -–—")]
    if len(parts) > 1:
        informative = [p for p in parts if not _LIVE_SEGMENT.search(p)]
        text = max(informative or parts, key=len)
    match = _LIVE_INLINE.search(text)
    if match:
        head, tail = text[:match.start()].strip(), text[match.end():].strip()
        if len(head) >= 30 or not tail:
            text = head
        else:
            text = f"{head}: {tail}" if head else tail
    text = _LEAD_TAG.sub("", text).strip(" -–—|:,")
    return text[:1].upper() + text[1:] if text else text


def headline_score(headline: dict, topic_tokens: set, now: float) -> float:
    title = clean_headline(headline.get("title") or "")
    words = set(tokens(title))
    score = 0.0
    if topic_tokens:
        score += 3.0 * len(topic_tokens & words) / len(topic_tokens)
    if headline.get("from_trend"):
        score += 2.0
    score += min(headline.get("coverage") or 1, 10) / 4
    published = headline.get("published")
    if published:
        age = (now - published) / 3600
        score += 1.5 if age <= 3 else 1.0 if age <= 12 else 0.3 if age <= 36 else -1.0
    if len(title) < 25 or len(title) > 170:
        score -= 1.0
    return score


def rank_headlines(topic: dict, now: float = None) -> list:
    now = now or time.time()
    topic_tokens = set(tokens(topic.get("title") or ""))
    items = topic.get("news", {}).get("items") or []
    return sorted(items, key=lambda h: -headline_score(h, topic_tokens, now))


def is_disambiguation(description: str) -> bool:
    return bool(_DISAMBIGUATION.search(description or ""))


_WORD = r"[A-Za-zÁÉÍÓÚÑÜáéíóúñü0-9]+"


def context_word(description: str):
    if not description or is_disambiguation(description):
        return None
    words = [w for w in re.findall(_WORD, description) if strip_accents(w).lower() not in ("un", "una", "el", "la", "los", "las")]
    if not words:
        return None
    base = strip_accents(words[0]).lower()
    return words[0].lower() if len(base) >= 4 and base not in STOPWORDS and base not in _GENERIC_TYPES else None


def mentions(title: str, headline: str) -> bool:
    words = [w for w in re.findall(_WORD, title or "") if len(w) > 1 and strip_accents(w).lower() not in STOPWORDS]
    if not words:
        return True
    if any(strip_accents(w) != w for w in words):
        found = set(re.findall(_WORD, (headline or "").lower()))
        return any(w.lower() in found for w in words)
    return bool(set(tokens(title)) & set(tokens(headline or "")))


def proper_mention(title: str, headline: str) -> bool:
    """Un tema de una sola palabra solo se explica con titulares que la usen como nombre propio:
    «Abascal responde…» sí; «la batería externa…» no habla del tema «Batería»."""
    significant = tokens(title or "")
    if len(significant) != 1:
        return True
    target = significant[0]
    accented = strip_accents(title or "") != (title or "")
    for word in re.findall(_WORD, headline or ""):
        if not word[:1].isupper():
            continue
        if norm(word) == target and (not accented or word.lower() in (title or "").lower()):
            return True
    return False


def qualifies(topic: dict, headline: dict) -> bool:
    """¿Puede este titular explicar por qué el tema es tendencia?"""
    if headline.get("from_trend"):
        return True
    title, text = topic.get("title") or "", clean_headline(headline.get("title") or "")
    return mentions(title, text) and proper_mention(title, text)


def subject_fits(topic_title: str, subject: str, why_title: str) -> bool:
    """El artículo de Wikipedia de otro nombre («Elecciones generales de Brasil de 2026» para el tema
    «Elecciones») solo sirve de contexto si el titular del «qué pasa» habla de él."""
    own = set(tokens(topic_title or ""))
    base = re.sub(r"\s*\([^)]*\)\s*$", "", subject or "")
    words = re.findall(_WORD, base)
    proper = [norm(w) for i, w in enumerate(words) if i > 0 and w[:1].isupper() and not w.isdigit() and norm(w) not in own]
    extra = [t for t in tokens(base) if t not in own and not t.isdigit()]
    if not extra:
        return True
    found = set(tokens(why_title or ""))
    if proper:
        return all(p in found for p in proper)
    return any(t in found for t in extra)


def looks_proper(topic: dict) -> bool:
    significant = tokens(topic.get("title") or "")
    if len(significant) >= 2:
        return True
    if not significant:
        return False
    target = significant[0]
    for headline in (topic.get("news") or {}).get("items") or []:
        for index, word in enumerate(re.findall(_WORD, headline.get("title") or "")):
            if index > 0 and word[:1].isupper() and norm(word) == target:
                return True
    return False


def same_entity(topic_title: str, page_title: str) -> bool:
    page = re.sub(r"\s*\([^)]*\)\s*$", "", page_title or "")
    a, b = norm(topic_title), norm(page)
    if not a or not b:
        return False
    if a == b:
        return True
    title = (topic_title or "").strip()
    if title.isupper() and 2 <= len(title) <= 6:
        initials = "".join(w[0] for w in b.split() if w not in STOPWORDS)
        return initials == norm(title).replace(" ", "")
    ta, tb = set(tokens(a)), set(tokens(b))
    return bool(ta) and ta <= tb and len(tb) <= len(ta) + 2


def description_fits(topic: dict, description: str) -> bool:
    if not description or is_disambiguation(description):
        return False
    described = classify("", description=description)[0]
    if described == "otros" or topic.get("niche") in (None, "otros"):
        return True
    return described in (topic.get("niches") or [topic.get("niche")])


def summary_line(topic: dict) -> str:
    parts = []
    google, x, wiki = topic.get("google"), topic.get("x"), topic.get("wikipedia")
    if google and google.get("volume"):
        parts.append(f"{fmt_number(google['volume'])}+ búsquedas en Google")
    if x:
        text = f"nº {x['rank']} en X"
        if (x.get("hours_in_trends") or 0) >= 2:
            text += f" desde hace {x['hours_in_trends']} h"
        parts.append(text)
    if wiki:
        parts.append(f"{fmt_number(wiki['views'])} lecturas en Wikipedia")
    outlets = topic.get("news", {}).get("outlets") or 0
    if outlets >= 2:
        parts.append(f"lo cuentan {outlets} medios")
    return " · ".join(parts[:3])


def pick_why(topic: dict, headlines: list):
    """El primer titular (ya ordenado por relevancia) que de verdad explica el tema."""
    best = next((h for h in headlines if qualifies(topic, h)), None)
    if not best:
        return None
    return {"title": clean_headline(best["title"]), "source": best.get("source"),
            "published": best.get("published"), "url": best.get("url")}


def explain(topic: dict, now: float = None) -> None:
    ranked = rank_headlines(topic, now)
    if ranked:
        topic["news"]["items"] = ranked
    topic["why"] = pick_why(topic, ranked)
    topic["what"], topic["what_subject"] = None, None
    title, wiki = topic.get("title") or "", topic.get("wikipedia")
    if topic.get("description") and wiki and not is_disambiguation(topic["description"]):
        subject = None if same_entity(title, wiki.get("title") or "") else wiki.get("title")
        if not subject or subject_fits(title, subject, (topic["why"] or {}).get("title")):
            topic["what"], topic["what_subject"] = _sentence_case(topic["description"]), subject
    if not topic["what"] and topic.get("extra_description"):
        topic["what"] = _sentence_case(topic["extra_description"])
    topic["summary"] = summary_line(topic)


def _sentence_case(text: str) -> str:
    text = (text or "").strip()
    return text[:1].upper() + text[1:]
