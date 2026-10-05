from __future__ import annotations

import datetime as dt
import html
import json
import math
import random
import time
from email.utils import format_datetime
from urllib.parse import quote

from .analysis import VOLUME_BUCKETS
from .sources import efemerides, google_trends, news, tiktok, wikipedia, x_trends, youtube
from .sources.base import SourceResult

H = 3600

GOOGLE_24H = [
    ("whatsapp caído", 200000, 1000, 1.0, None, [18], ["whatsapp no funciona", "caída whatsapp", "whatsapp hoy"], "explosive",
     [("WhatsApp sufre una caída que afecta a usuarios de varios países", "Diario digital (demo)")]),
    ("premio nobel de medicina", 100000, 1000, 2.5, None, [15], ["nobel de medicina 2026", "premio nobel", "nobel fisiología"], "explosive",
     [("Qué se premia en el Nobel de Medicina y cómo se elige al ganador", "Agencia (demo)")]),
    ("alcaraz", 100000, 500, 4.0, None, [17], ["alcaraz hoy", "alcaraz partido", "a qué hora juega alcaraz"], "rising",
     [("Alcaraz vuelve a la pista: horario y dónde ver el partido", "Prensa deportiva (demo)")]),
    ("real madrid - villarreal", 500000, 1000, 20.0, 7.0, [17], ["real madrid", "villarreal", "alineaciones real madrid", "laliga"], "cooling",
     [("Real Madrid - Villarreal: crónica, goles y análisis del partido", "Prensa deportiva (demo)")]),
    ("aviso amarillo lluvia", 50000, 500, 5.0, None, [20], ["aemet", "lluvia mañana", "aviso amarillo comunitat valenciana"], "rising",
     [("La AEMET activa avisos amarillos por lluvias en el este peninsular", "Diario nacional (demo)")]),
    ("gta 6", 50000, 500, 3.0, None, [6], ["gta 6 fecha", "gta 6 tráiler", "rockstar games"], "rising",
     [("GTA 6: todo lo que se sabe a semanas de su lanzamiento", "Web de videojuegos (demo)")]),
    ("huelga renfe", 50000, 200, 9.0, None, [19], ["huelga renfe octubre", "servicios mínimos renfe"], "peak",
     [("Huelga de Renfe: servicios mínimos y trenes afectados este lunes", "Diario nacional (demo)")]),
    ("la revuelta", 20000, 300, 1.5, None, [4], ["broncano", "la revuelta invitado hoy"], "explosive",
     [("La Revuelta: los invitados de esta semana", "Revista de televisión (demo)")]),
    ("día mundial de los docentes", 20000, 400, 7.0, None, [9], ["día del docente", "5 de octubre"], "peak",
     [("Día Mundial de los Docentes: por qué se celebra el 5 de octubre", "Diario educativo (demo)")]),
    ("bonoloto", 50000, 200, 3.0, None, [11], ["bonoloto resultados", "comprobar bonoloto"], "peak", []),
    ("batalla de lepanto", 5000, 600, 2.0, None, [11], ["lepanto 1571", "batalla de lepanto resumen", "juan de austria"], "rising",
     [("Lepanto, 455 años después: la batalla que cambió el Mediterráneo", "Revista de historia (demo)")]),
    ("presupuestos generales", 10000, 300, 6.0, None, [14], ["congreso presupuestos", "presupuestos 2027"], "rising",
     [("El Congreso debate esta semana los presupuestos generales", "Diario nacional (demo)")]),
    ("ucrania", 20000, 150, 10.0, None, [14], ["ucrania rusia", "zelenski", "otan ucrania"], "peak",
     [("Ucrania: claves de la semana en el frente diplomático", "Agencia (demo)")]),
    ("euribor", 20000, 100, 11.0, None, [3], ["euribor hoy", "euribor septiembre", "hipoteca euribor"], "peak",
     [("El euríbor cierra septiembre: así quedan las hipotecas", "Diario económico (demo)")]),
    ("dana", 20000, 300, 8.0, None, [20], ["dana octubre", "aemet dana", "dana valencia"], "peak", []),
    ("gran hermano", 20000, 200, 14.0, None, [4], ["gh hoy", "gran hermano expulsión"], "cooling",
     [("Gran Hermano: así fue la última gala", "Revista de televisión (demo)")]),
    ("concierto aitana", 10000, 200, 12.0, 2.0, [4], ["aitana gira", "entradas aitana"], "cooling", []),
    ("oposiciones educación", 10000, 200, 18.0, None, [9], ["oposiciones 2027", "temario oposiciones"], "cooling", []),
    ("vacuna gripe", 10000, 150, 9.0, None, [7], ["campaña vacunación gripe", "vacuna gripe 2026"], "peak",
     [("Campaña de vacunación de la gripe: fechas por comunidades", "Diario de salud (demo)")]),
    ("pedro sánchez", 20000, 200, 6.0, None, [14], ["sánchez hoy", "comparecencia sánchez"], "peak", []),
]

X_TRENDS = [
    ("WhatsApp", 95000, 1), ("#NobelMedicina", 18400, 2), ("#LaRevuelta", 12000, 1), ("Alcaraz", 22000, 4),
    ("GTA 6", 27000, 3), ("#HuelgaRenfe", 9800, 9), ("Lepanto", 3100, 1), ("AEMET", 7600, 5),
    ("#DiaMundialDeLosDocentes", 14500, 8), ("Mbappé", 41000, 22), ("Pedro Sánchez", 15700, 10), ("Broncano", 8000, 1),
    ("Zelenski", 9000, 9), ("#RealMadridVillarreal", 66000, 21), ("Vinicius", 30500, 21), ("Feijóo", 8800, 6),
    ("#GH", 11000, 14), ("Presupuestos", 6100, 5), ("Euribor", None, 4), ("Juan de Austria", 2100, 1),
    ("#LunesDeOtoño", 4300, 7), ("Halloween", 12500, 18), ("DANA", 5200, 8), ("Aitana", 7300, 13),
    ("Champions", 18800, 16), ("Rockstar", 6600, 3), ("Bernabéu", 9100, 20), ("Netflix", 5100, 12),
]

TIKTOK_TAGS = [
    ("halloween", 48000, 310_000_000, "Life Services", 0, False), ("otoño", 21000, 120_000_000, "Apparel & Accessories", 2, False),
    ("gta6", 15000, 95_000_000, "Games", 6, False), ("realmadrid", 14000, 99_000_000, "Sports & Outdoor", -1, False),
    ("laliga", 12000, 88_000_000, "Sports & Outdoor", 1, False), ("historia", 9000, 64_000_000, "Education", 3, False),
    ("gym", 9900, 70_000_000, "Sports & Outdoor", 0, False), ("recetasfaciles", 8800, 52_000_000, "Food & Beverage", -2, False),
    ("curiosidades", 7500, 48_000_000, "Education", 4, False), ("outfitotoño", 6600, 40_000_000, "Apparel & Accessories", 0, True),
    ("larevuelta", 6000, 41_000_000, "News & Entertainment", 5, False), ("aitana", 5000, 33_000_000, "News & Entertainment", -3, False),
    ("lepanto", 1800, 9_500_000, "Education", 0, True), ("dana", 3000, 21_000_000, "News & Entertainment", -4, False),
    ("nobel", 2100, 9_000_000, "Education", 0, True), ("granhermano", 4400, 29_000_000, "News & Entertainment", -1, False),
]

TIKTOK_SONGS = [
    ("Épico (versión orquestal)", "Compositor Demo"), ("Ritmo de otoño", "Artista Demo"), ("Noche en Madrid", "Banda Demo"),
    ("Lluvia de octubre", "Cantante Demo"), ("Tensión (cinemática)", "Estudio Demo"), ("Vuelta al barrio", "Rapero Demo"),
]

WIKI_ARTICLES = [
    ("es", "Premio_Nobel_de_Fisiología_o_Medicina", 48000, 6800, "galardón internacional anual"),
    ("es", "Kylian_Mbappé", 31000, 29000, "futbolista francés"),
    ("es", "Villarreal_Club_de_Fútbol", 22000, 9000, "club de fútbol de Villarreal, España"),
    ("es", "Batalla_de_Lepanto", 19000, 4200, "batalla naval de 1571"),
    ("es", "Gran_Hermano_(España)", 17000, 18500, "programa de televisión español"),
    ("es", "Grand_Theft_Auto_VI", 16500, 9800, "videojuego de acción"),
    ("es", "Carlos_Alcaraz", 15000, 7000, "tenista español"),
    ("es", "Día_Mundial_de_los_Docentes", 12000, 400, "día internacional"),
    ("es", "Felipe_II_de_España", 9000, 5200, "rey de España entre 1556 y 1598"),
    ("es", "Cristóbal_Colón", 8800, 6100, "navegante y explorador"),
    ("es", "Imperio_otomano", 7800, 3500, "Estado que existió entre 1299 y 1922"),
    ("es", "David_Broncano", 7000, 6600, "humorista y presentador español"),
    ("es", "Juan_de_Austria", 6900, 1500, "militar y diplomático español del siglo XVI"),
    ("es", "WhatsApp", 6000, 900, "aplicación de mensajería"),
    ("es", "Halloween", 5800, 4100, "festividad celebrada el 31 de octubre"),
    ("es", "Guerra_Civil_Española", 5500, 5600, "conflicto bélico entre 1936 y 1939"),
    ("en", "Battle_of_Lepanto", 4000, 1300, "1571 naval battle"),
    ("es", "Euríbor", 3900, 3700, "tipo de interés de referencia del mercado interbancario"),
    ("es", "Inteligencia_artificial", 3700, 3900, "disciplina de la informática"),
    ("es", "Aitana_(cantante)", 3500, 3900, "cantante española"),
]

NEWS = {
    "portada": [
        ("El Nobel de Medicina se anuncia hoy: qué se premia y cómo se elige", "Agencia (demo)", 2),
        ("WhatsApp sufre una caída que afecta a usuarios de varios países", "Diario digital (demo)", 1),
        ("Huelga de Renfe: servicios mínimos y trenes afectados este lunes", "Diario nacional (demo)", 6),
    ],
    "espana": [
        ("El Congreso debate esta semana los presupuestos generales", "Diario nacional (demo)", 4),
        ("La AEMET activa avisos amarillos por lluvias en el este peninsular", "Diario nacional (demo)", 3),
        ("Día Mundial de los Docentes: por qué se celebra el 5 de octubre", "Diario educativo (demo)", 7),
    ],
    "internacional": [("Ucrania: claves de la semana en el frente diplomático", "Agencia (demo)", 5)],
    "economia": [("El euríbor cierra septiembre: así quedan las hipotecas", "Diario económico (demo)", 9)],
    "tecnologia": [("Cómo comprobar si WhatsApp está caído y qué hacer mientras tanto", "Web tecnológica (demo)", 1)],
    "entretenimiento": [
        ("La Revuelta: los invitados de esta semana", "Revista de televisión (demo)", 3),
        ("Gran Hermano: así fue la última gala", "Revista de televisión (demo)", 12),
    ],
    "deportes": [
        ("Alcaraz vuelve a la pista: horario y dónde ver el partido", "Prensa deportiva (demo)", 4),
        ("Real Madrid - Villarreal: crónica, goles y análisis del partido", "Prensa deportiva (demo)", 9),
    ],
    "ciencia": [
        ("Qué se premia en el Nobel de Medicina y cómo se elige al ganador", "Revista científica (demo)", 3),
        ("Lepanto, 455 años después: la batalla que cambió el Mediterráneo", "Revista de historia (demo)", 2),
    ],
    "salud": [("Campaña de vacunación de la gripe: fechas por comunidades", "Diario de salud (demo)", 8)],
}

EFEMERIDES = [
    (10, 5, 1910, "selected", "Se proclama la Primera República Portuguesa tras la revolución que derroca a la monarquía.", "Revolución del 5 de octubre de 1910", "revolución en Portugal"),
    (10, 6, 1976, "events", "Detención de la «Banda de los Cuatro» en Pekín, un mes después de la muerte de Mao Zedong.", "Banda de los Cuatro", "facción política china"),
    (10, 7, 1571, "selected", "Batalla de Lepanto: la Liga Santa, con Juan de Austria al frente, derrota a la flota otomana.", "Batalla de Lepanto", "batalla naval de 1571"),
    (10, 7, 2001, "events", "Comienza la intervención militar de Estados Unidos y sus aliados en Afganistán.", "Guerra de Afganistán (2001-2021)", "conflicto bélico"),
    (10, 9, 1967, "events", "Ernesto «Che» Guevara es ejecutado en La Higuera (Bolivia).", "Che Guevara", "revolucionario argentino-cubano"),
    (10, 9, 2006, "events", "Corea del Norte realiza su primera prueba nuclear.", "Prueba nuclear norcoreana de 2006", "ensayo nuclear"),
    (10, 11, 1776, "events", "Batalla de la isla de Valcour, en la Guerra de Independencia de Estados Unidos.", "Batalla de la isla de Valcour", "batalla naval de 1776"),
    (10, 11, 1986, "events", "Comienza la cumbre de Reikiavik entre Reagan y Gorbachov.", "Cumbre de Reikiavik", "reunión diplomática"),
    (10, 12, 1492, "selected", "Cristóbal Colón llega a la isla de Guanahani, en las Bahamas.", "Cristóbal Colón", "navegante y explorador"),
    (10, 14, 1066, "events", "Batalla de Hastings: Guillermo de Normandía vence a Haroldo II.", "Batalla de Hastings", "batalla de 1066"),
    (10, 14, 1926, "events", "Se publica «Winnie-the-Pooh», de A. A. Milne.", "Winnie-the-Pooh", "libro infantil"),
    (10, 16, 1793, "events", "María Antonieta es guillotinada en París.", "María Antonieta", "reina de Francia"),
    (10, 17, 1986, "selected", "El COI elige a Barcelona como sede de los Juegos Olímpicos de 1992.", "Juegos Olímpicos de Barcelona 1992", "evento multideportivo"),
    (10, 21, 1805, "selected", "Batalla de Trafalgar: la flota británica de Nelson vence a la franco-española.", "Batalla de Trafalgar", "batalla naval de 1805"),
    (10, 21, 1966, "events", "Desastre de Aberfan (Gales): un alud de escombros mineros sepulta una escuela.", "Desastre de Aberfan", "catástrofe en Gales"),
    (10, 23, 1956, "selected", "Comienza la Revolución húngara contra el régimen prosoviético.", "Revolución húngara de 1956", "revuelta"),
    (10, 24, 1945, "events", "Entra en vigor la Carta de las Naciones Unidas: nace la ONU.", "Organización de las Naciones Unidas", "organización internacional"),
    (10, 25, 1415, "events", "Batalla de Agincourt, en la guerra de los Cien Años.", "Batalla de Agincourt", "batalla de 1415"),
    (10, 28, 1726, "events", "Se publican «Los viajes de Gulliver», de Jonathan Swift.", "Los viajes de Gulliver", "novela satírica"),
    (10, 28, 1886, "events", "Se inaugura la Estatua de la Libertad en Nueva York.", "Estatua de la Libertad", "monumento"),
    (10, 29, 1929, "selected", "«Martes negro»: se hunde la Bolsa de Nueva York.", "Crac del 29", "crisis financiera"),
    (10, 29, 1956, "events", "Israel invade el Sinaí: comienza la crisis de Suez.", "Crisis de Suez", "conflicto de 1956"),
    (10, 31, 1517, "selected", "Lutero hace públicas sus 95 tesis en Wittenberg.", "Las 95 tesis", "documento de 1517"),
    (10, 31, 1926, "deaths", "Muere Harry Houdini, ilusionista y escapista.", "Harry Houdini", "ilusionista"),
    (11, 1, 1755, "selected", "Un terremoto y un tsunami arrasan Lisboa.", "Terremoto de Lisboa de 1755", "terremoto"),
    (11, 2, 1976, "events", "Jimmy Carter gana las elecciones presidenciales de Estados Unidos.", "Jimmy Carter", "político estadounidense"),
]

YOUTUBE_DEMO = {
    "whatsappcaido": (28, [("WhatsApp CAÍDO hoy: qué está pasando", "Canal Demo Tech", 410000, "3 hours ago", "4:12"),
                           ("Caída mundial de WhatsApp explicada", "Canal Demo Noticias", 260000, "2 hours ago", "0:58")]),
    "premionobeldemedicina": (8, [("¿Qué es el Premio Nobel de Medicina? Explicado", "Canal Demo Ciencia", 45000, "1 day ago", "6:40"),
                                  ("Nobel de Medicina: historia en 60 segundos", "Canal Demo Shorts", 22000, "4 days ago", "0:59")]),
    "batalladelepanto": (3, [("La batalla de Lepanto en 10 minutos", "Canal Demo Historia", 12000, "5 days ago", "10:22"),
                             ("Lepanto: el día que cambió el Mediterráneo", "Canal Demo Divulgación", 6100, "6 days ago", "0:55")]),
    "alcaraz": (20, [("Alcaraz: mejores puntos de la semana", "Canal Demo Tenis", 380000, "2 days ago", "8:03"),
                     ("Alcaraz, el golpe que nadie esperaba", "Canal Demo Deportes", 190000, "3 days ago", "0:45")]),
    "gta6": (20, [("GTA 6: todo lo que sabemos", "Canal Demo Gaming", 920000, "4 days ago", "15:31"),
                  ("GTA 6 en 60 segundos", "Canal Demo Shorts", 510000, "2 days ago", "0:59")]),
}


def _curve(shape: str, started_h: float, points: int = 91, step_min: int = 16) -> list:
    start_index = max(0, points - int(started_h * 60 / step_min))
    values = []
    for i in range(points):
        if i < start_index:
            values.append(0.0)
            continue
        t = (i - start_index) / max(points - start_index - 1, 1)
        if shape == "explosive":
            v = 100 * (t ** 1.6)
        elif shape == "rising":
            v = 25 + 75 * t
        elif shape == "peak":
            v = 100 * (1 - math.exp(-6 * t)) * (0.92 + 0.08 * math.sin(t * 9))
        else:
            v = 100 * math.sin(math.pi * min(1.0, t * 1.15)) if t < 0.43 else 100 * math.exp(-2.6 * (t - 0.43)) * 0.97
        values.append(round(max(0.0, min(100.0, v)), 1))
    return values


def _batch_text(rpc_id: str, payload) -> str:
    entry = ["wrb.fr", rpc_id, json.dumps(payload), None, None, None, "generic"]
    return ")]}'\n\n" + json.dumps([entry, ["di", 87], ["af.httprm", 86, "-3141592653", 21]])


class DemoData:
    def __init__(self):
        self.now = time.time()
        self.rng = random.Random(7)

    def load(self, source: str):
        handler = getattr(self, f"_{source}", None)
        if handler is None:
            return SourceResult(source=source, ok=False, error="Fuente no disponible en modo demo")
        return handler()

    def google_payload(self, rows_spec, ended_is_hours_ago=True) -> str:
        rows = []
        for keyword, volume, growth, started_h, ended_h, topics, related, _shape, news_items in rows_spec:
            started = int(self.now - started_h * H)
            ended = [int(self.now - ended_h * H), 0] if ended_h is not None else None
            news_rows = [[t, f"https://example.com/demo/{quote(t[:30])}", s, [started + 1800], None] for t, s in news_items]
            rows.append([keyword, news_rows, "ES", [started, 0], ended, None, volume, None, growth, related, topics,
                         [f"token-{abs(hash(keyword)) % 10000}"], keyword])
        return _batch_text("i0OFE", [None, rows])

    def _google(self):
        items = google_trends.parse_trending(google_trends.parse_batch_response(self.google_payload(GOOGLE_24H), "i0OFE"))
        return SourceResult(source="google", ok=True, items=items, meta={"mode": "demo", "seed_snapshots": self.google_snapshots(items)})

    def google_snapshots(self, items: list) -> list:
        shapes = {k: (shape, started) for k, _v, _g, started, _e, _t, _r, shape, _n in GOOGLE_24H}
        rows = []
        for item in items:
            if not item["active"] or item["query"] not in shapes:
                continue
            curve = _curve(*shapes[item["query"]])
            total, running = sum(curve) or 1.0, 0.0
            for index, value in enumerate(curve):
                running += value
                ts = int(self.now - (len(curve) - 1 - index) * 960)
                volume = max((b for b in VOLUME_BUCKETS if b <= item["volume"] * running / total), default=0)
                if index % 2 == 0 and ts >= item["started_at"] and volume:
                    rows.append((item["id"], item["started_at"], ts, volume))
        return rows

    def _google_week(self):
        pools = {
            17: ["atlético - betis", "barcelona - sevilla", "champions league", "fernando alonso", "selección española",
                 "nba", "motogp", "vuelta ciclista", "athletic - osasuna", "alcaraz"],
            4: ["la revuelta", "el hormiguero", "gran hermano", "masterchef", "netflix estrenos", "pasapalabra bote",
                "la isla de las tentaciones", "concierto aitana", "los40 music awards"],
            14: ["pedro sánchez", "feijóo", "congreso", "presupuestos generales", "ayuso", "ucrania", "trump", "gaza", "otan"],
            3: ["euribor", "pensiones", "salario mínimo", "ibex 35", "bitcoin", "precio de la luz"],
            20: ["aemet", "dana", "lluvia", "tormentas", "temperaturas"],
            18: ["iphone", "whatsapp", "chatgpt", "inteligencia artificial"],
            6: ["gta 6", "fortnite", "ea fc 27", "nintendo switch 2"],
            11: ["huelga", "accidente tráfico", "incendio", "detenido", "hispanidad", "guerra civil", "batalla de lepanto",
                 "bonoloto", "euromillones"],
            7: ["vacuna gripe", "covid"],
            9: ["oposiciones", "becas", "día mundial de los docentes"],
        }
        lifetimes = {17: 9, 4: 13, 14: 20, 3: 15, 20: 28, 18: 10, 6: 16, 11: 14, 7: 22, 9: 18}
        weights = {17: 7, 4: 6, 14: 6, 3: 3, 20: 3, 18: 3, 6: 2, 11: 6, 7: 1, 9: 2}
        hours = [0, 0, 0, 0, 0, 1, 2, 4, 7, 9, 8, 7, 7, 8, 7, 6, 6, 7, 9, 11, 12, 13, 9, 4]
        rows_spec = []
        topic_ids = list(weights)
        for day in range(1, 8):
            for _ in range(self.rng.randint(14, 22)):
                topic = self.rng.choices(topic_ids, weights=[weights[t] for t in topic_ids])[0]
                keyword = self.rng.choice(pools[topic])
                base_day = dt.datetime.fromtimestamp(self.now) - dt.timedelta(days=day)
                hour = self.rng.choices(range(24), weights=hours)[0]
                start = base_day.replace(hour=hour, minute=self.rng.randint(0, 59), second=0).timestamp()
                duration = max(1.0, self.rng.gauss(lifetimes[topic], lifetimes[topic] * 0.35))
                started_h = (self.now - start) / H
                ended_h = max(0.1, started_h - duration)
                volume = self.rng.choice([2000, 5000, 10000, 20000, 50000, 100000, 200000])
                rows_spec.append((keyword, volume, self.rng.choice([100, 200, 300, 500, 1000]), started_h, ended_h, [topic], [], "peak", []))
        rows_spec.extend(GOOGLE_24H)
        items = google_trends.parse_trending(google_trends.parse_batch_response(self.google_payload(rows_spec), "i0OFE"))
        return SourceResult(source="google_week", ok=True, items=items, meta={"mode": "demo"})

    def trends24_html(self) -> str:
        cards = []
        for hour in range(24):
            stamp = int(self.now - hour * H)
            entries = []
            for index, (name, count, hours_in) in enumerate(X_TRENDS):
                if hour < hours_in:
                    drift = int(hour * (1.5 if hours_in > 12 else -0.6))
                    entries.append((max(1, index + 1 + drift), name, count))
            entries.sort()
            lis = "".join(
                f'<li><span class="trend-name"><a class="trend-link" href="https://twitter.com/search?q={quote(n)}">{html.escape(n)}</a>'
                + (f'<span class="tweet-count" data-count="{c}">{c // 1000}K</span>' if c else "")
                + "</span></li>"
                for _r, n, c in entries
            )
            cards.append(f'<div class="list-container"><h3 class="title" data-timestamp="{stamp}">hace {hour} h</h3>'
                         f'<ol class="trend-card__list">{lis}</ol></div>')
        return "<html><body><div id='timeline'>" + "".join(cards) + "</div></body></html>"

    def _x(self):
        items = x_trends.build_items(x_trends.parse_trends24(self.trends24_html()), now=self.now)
        return SourceResult(source="x", ok=True, items=items, meta={"provider": "demo"})

    def tiktok_html(self) -> str:
        records = []
        for rank, (name, posts, views, industry, diff, new) in enumerate(TIKTOK_TAGS, 1):
            curve = [{"time": int(self.now - (6 - d) * 86400), "value": round(0.3 + 0.7 * ((d + 1) / 7) ** (1.5 if diff >= 0 else 0.4), 3)} for d in range(7)]
            records.append({
                "hashtagId": str(1000 + rank), "hashtagName": name, "publishCnt": posts, "videoViews": views, "rank": rank,
                "rankDiff": abs(diff), "rankDiffType": 3 if new else (1 if diff > 0 else 2 if diff < 0 else 4),
                "industryInfo": {"id": rank, "value": industry}, "trend": curve,
            })
        data = {"props": {"pageProps": {"data": {"pagination": {"page": 1, "total": len(records)}, "list": records}}}}
        return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></html>'

    def tiktok_music_html(self) -> str:
        records = [
            {"clipId": str(9000 + i), "title": title, "author": author, "rank": i, "rankDiff": i % 3, "rankDiffType": 1 if i % 2 else 4,
             "link": "https://www.tiktok.com/music/demo", "trend": [{"time": 0, "value": 0.2 + 0.1 * d} for d in range(7)]}
            for i, (title, author) in enumerate(TIKTOK_SONGS, 1)
        ]
        data = {"props": {"pageProps": {"data": {"soundList": records}}}}
        return f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></html>'

    def _tiktok(self):
        return SourceResult(source="tiktok", ok=False, error=tiktok.LOGIN_MESSAGE,
                            meta={"requires_login": True, "browse_url": tiktok.BROWSE_URL})

    def _wikipedia(self):
        today = dt.date.fromtimestamp(self.now)
        days = []
        for offset in range(1, 9):
            day = today - dt.timedelta(days=offset)
            articles = []
            for lang, article, views, previous, _desc in WIKI_ARTICLES:
                if offset == 1:
                    value = views
                elif offset == 2:
                    value = previous
                else:
                    value = int(previous * (0.75 + 0.25 * self.rng.random()) * (1 - 0.04 * offset))
                if value >= 1000 or offset == 1:
                    articles.append({"project": f"{lang}.wikipedia", "article": article, "views_ceil": value, "rank": 0})
            articles.append({"project": "es.wikipedia", "article": "Especial:Buscar", "views_ceil": 90000, "rank": 0})
            articles.sort(key=lambda a: -a["views_ceil"])
            payload = {"items": [{"country": "ES", "access": "all-access", "articles": articles}]}
            days.append((day, wikipedia.parse_top_per_country(payload)))
        descriptions = {(f"{lang}.wikipedia", article): {"description": desc, "thumbnail": None}
                        for lang, article, _v, _p, desc in WIKI_ARTICLES}
        items = wikipedia.build_items(days, descriptions)
        return SourceResult(source="wikipedia", ok=True, items=items, meta={"day": days[0][0].isoformat(), "days": len(days)})

    def news_rss(self, section: str) -> str:
        entries = []
        for title, source, hours_ago in NEWS.get(section, []):
            published = format_datetime(dt.datetime.fromtimestamp(self.now - hours_ago * H, dt.timezone.utc))
            related = "".join(f"&lt;li&gt;item {i}&lt;/li&gt;" for i in range(1 + len(title) % 5))
            entries.append(
                f"<item><title>{html.escape(title)} - {html.escape(source)}</title>"
                f"<link>https://news.google.com/rss/articles/demo-{quote(title[:20])}</link>"
                f"<pubDate>{published}</pubDate><description>&lt;ol&gt;{related}&lt;/ol&gt;</description>"
                f"<source url=\"https://example.com\">{html.escape(source)}</source></item>"
            )
        return f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>{"".join(entries)}</channel></rss>'

    def _news(self):
        sections, items, seen = {}, [], set()
        for section_id, _topic, _label in news.SECTIONS:
            rows = news.parse_rss(self.news_rss(section_id), section_id)
            sections[section_id] = [r["id"] for r in rows]
            for row in rows:
                if row["id"] not in seen:
                    seen.add(row["id"])
                    items.append(row)
        return SourceResult(source="news", ok=True, items=items, meta={"sections": sections, "errors": []})

    def _efemerides(self):
        today = dt.date.fromtimestamp(self.now)
        all_days = []
        for offset in range(30):
            target = today + dt.timedelta(days=offset)
            payload = {"selected": [], "events": [], "births": [], "deaths": []}
            for month, day, year, kind, text, title, desc in EFEMERIDES:
                if (month, day) == (target.month, target.day):
                    payload[kind].append({"text": text, "year": year, "pages": [{
                        "titles": {"normalized": title}, "description": desc,
                        "content_urls": {"desktop": {"page": f"https://es.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"}},
                    }]})
            all_days.append({"date": target.isoformat(), "items": efemerides.build_items(payload, target)[:12]})
        return SourceResult(source="efemerides", ok=True, items=all_days, meta={"highlights": efemerides.pick_highlights(all_days)})

    def youtube_payload(self, videos) -> dict:
        contents = []
        for index, (title, channel, views, ago, length) in enumerate(videos):
            if index % 2 == 0:
                contents.append({"videoRenderer": {
                    "videoId": f"demo{index:07d}", "title": {"runs": [{"text": title}]},
                    "ownerText": {"runs": [{"text": channel}]}, "viewCountText": {"simpleText": f"{views:,} views"},
                    "publishedTimeText": {"simpleText": ago}, "lengthText": {"simpleText": length},
                }})
            else:
                contents.append({"lockupViewModel": {
                    "contentId": f"demo{index:07d}", "contentType": "LOCKUP_CONTENT_TYPE_VIDEO",
                    "metadata": {"lockupMetadataViewModel": {
                        "title": {"content": title},
                        "metadata": {"contentMetadataViewModel": {"metadataRows": [
                            {"metadataParts": [{"text": {"content": channel}}]},
                            {"metadataParts": [{"text": {"content": f"{views/1000:.0f}K views"}}, {"text": {"content": ago}}]},
                        ]}},
                    }},
                    "contentImage": {"thumbnailViewModel": {"overlays": [
                        {"thumbnailBottomOverlayViewModel": {"badges": [{"thumbnailBadgeViewModel": {"text": length}}]}}]}},
                }})
        return {"contents": {"twoColumnSearchResultsRenderer": {"primaryContents": {"sectionListRenderer": {"contents": [
            {"itemSectionRenderer": {"contents": contents}}]}}}}}

    def _competitions(self) -> dict:
        out = {}
        for topic_key, (extra, videos) in YOUTUBE_DEMO.items():
            padded = list(videos)
            for i in range(extra - len(videos)):
                padded.append((f"Vídeo relacionado {i + 1}", "Canal Demo", int(videos[-1][2] * (0.8 ** (i + 1))), f"{i % 6 + 1} days ago", "3:10"))
            found = youtube.parse_search(self.youtube_payload(padded))
            summary = youtube.summarize(topic_key, found)
            summary.update({"topic_key": topic_key, "topic_title": topic_key})
            out[topic_key] = summary
        return out

    def _youtube(self):
        return SourceResult(source="youtube", ok=True, items=list(self._competitions().values()), meta={})

    def _detail(self):
        return {"youtube": self._competitions()}
