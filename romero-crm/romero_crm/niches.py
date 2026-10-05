from __future__ import annotations

import re

from .text import norm

NICHES = [
    ("actualidad", "Actualidad y sucesos"),
    ("politica", "Política"),
    ("internacional", "Internacional"),
    ("economia", "Economía"),
    ("deportes", "Deportes"),
    ("entretenimiento", "TV, cine y series"),
    ("musica", "Música"),
    ("historia", "Historia y cultura"),
    ("tecnologia", "Tecnología"),
    ("ciencia", "Ciencia"),
    ("videojuegos", "Videojuegos"),
    ("salud", "Salud"),
    ("clima", "Clima y medio ambiente"),
    ("motor", "Motor"),
    ("estilo", "Moda y belleza"),
    ("gastronomia", "Gastronomía"),
    ("viajes", "Viajes y transporte"),
    ("educacion", "Educación y empleo"),
    ("animales", "Animales"),
    ("ocio", "Ocio y compras"),
    ("otros", "Otros"),
]
NICHE_NAMES = dict(NICHES)
NICHE_ORDER = {nid: index for index, (nid, _) in enumerate(NICHES)}

GOOGLE_TOPICS = {
    1: "motor", 2: "estilo", 3: "economia", 4: "entretenimiento", 5: "gastronomia",
    6: "videojuegos", 7: "salud", 8: "ocio", 9: "educacion", 10: "politica", 11: "otros",
    13: "animales", 14: "politica", 15: "ciencia", 16: "ocio", 17: "deportes",
    18: "tecnologia", 19: "viajes", 20: "clima",
}

NEWS_SECTIONS = {
    "espana": "actualidad", "internacional": "internacional", "economia": "economia",
    "tecnologia": "tecnologia", "entretenimiento": "entretenimiento", "deportes": "deportes",
    "ciencia": "ciencia", "salud": "salud",
}

KEYWORDS = {
    "deportes": [
        "futbol", "laliga", "la liga", "liga ea sports", "champions", "champions league", "europa league",
        "conference league", "copa del rey", "supercopa", "mundial de futbol", "copa del mundo", "mundial de clubes", "eurocopa", "real madrid", "fc barcelona",
        "barca", "atletico de madrid", "atletico", "atleti", "sevilla fc", "real betis", "betis", "valencia cf",
        "villarreal", "athletic club", "athletic", "real sociedad", "osasuna", "celta", "getafe", "girona",
        "mallorca", "rayo vallecano", "alaves", "espanyol", "las palmas", "leganes", "real valladolid", "levante",
        "elche", "real oviedo", "racing", "deportivo", "real zaragoza", "sporting", "granada cf", "cadiz cf",
        "almeria", "gol", "goles", "alineacion", "alineaciones", "fichaje", "fichajes", "seleccion espanola",
        "la roja", "mbappe", "vinicius", "bellingham", "lamine yamal", "pedri", "gavi", "raphinha", "lewandowski",
        "ancelotti", "xabi alonso", "hansi flick", "simeone", "nadal", "alcaraz", "sinner", "djokovic", "tenis",
        "roland garros", "wimbledon", "us open", "open de australia", "formula 1", "gran premio", "fernando alonso",
        "carlos sainz", "verstappen", "motogp", "marc marquez", "jorge martin", "baloncesto", "nba", "euroliga",
        "acb", "ciclismo", "vuelta a espana", "tour de francia", "giro de italia", "golf", "boxeo", "ufc",
        "topuria", "balonmano", "juegos olimpicos", "olimpiadas", "atletismo", "natacion", "padel", "derbi",
        "clasico", "arbitro", "var", "penalti", "hat trick", "uefa", "fifa", "entrenador", "jornada",
    ],
    "politica": [
        "psoe", "pp", "partido popular", "vox", "sumar", "podemos", "junts", "erc", "pnv", "bildu",
        "pedro sanchez", "sanchez", "feijoo", "abascal", "yolanda diaz", "ayuso", "puigdemont", "salvador illa",
        "moncloa", "congreso", "senado", "gobierno", "ministro", "ministra", "elecciones", "votacion",
        "encuesta", "cis", "decreto", "amnistia", "presupuestos", "tribunal supremo", "tribunal constitucional",
        "fiscal general", "cgpj", "investidura", "mocion de censura", "parlament", "generalitat", "junta de andalucia",
        "xunta", "comunidad de madrid", "ayuntamiento", "alcalde", "alcaldesa", "diputado", "diputada",
        "corrupcion", "imputado", "imputada", "sumario", "dimision", "dimite", "ley de", "reforma",
        "votar", "voto", "votos", "urnas", "pucherazo", "escrutinio", "sondeo", "sondeos", "campana electoral",
        "mitin", "adelanto electoral", "elecciones anticipadas", "elecciones generales", "candidato", "candidata",
        "papeleta", "voto por correo", "jornada electoral", "cortes generales", "disolucion de las cortes",
    ],
    "internacional": [
        "trump", "donald trump", "biden", "kamala harris", "putin", "zelenski", "ucrania", "rusia", "israel",
        "gaza", "hamas", "hezbolla", "netanyahu", "iran", "china", "xi jinping", "otan", "onu", "union europea",
        "bruselas", "von der leyen", "macron", "meloni", "merz", "starmer", "milei", "maduro", "venezuela",
        "eeuu", "estados unidos", "casa blanca", "kremlin", "corea del norte", "kim jong", "taiwan", "siria",
        "libano", "palestina", "cisjordania", "marruecos", "argelia", "mexico", "argentina", "colombia", "brasil",
        "lula", "papa leon", "vaticano", "aranceles", "g7", "g20", "cumbre", "embajada", "guerra comercial",
    ],
    "economia": [
        "ibex", "ibex 35", "bolsa", "euribor", "hipoteca", "hipotecas", "ipc", "inflacion", "pensiones",
        "pension", "smi", "salario minimo", "hacienda", "renta", "declaracion de la renta", "bce",
        "tipos de interes", "paro", "huelga general", "bitcoin", "criptomonedas", "precio de la luz",
        "gasolina", "diesel", "vivienda", "alquiler", "alquileres", "inditex", "amancio ortega", "santander",
        "bbva", "caixabank", "telefonica", "iberdrola", "repsol", "mercadona", "el corte ingles", "ere",
        "despidos", "empresa", "empresas", "economia", "pib", "deuda", "impuesto", "impuestos", "irpf", "iva",
        "subsidio", "nomina", "paga extra", "black friday",
    ],
    "entretenimiento": [
        "serie", "series", "pelicula", "peliculas", "estreno", "netflix", "hbo", "hbo max", "disney",
        "prime video", "movistar plus", "atresplayer", "temporada", "capitulo", "actor", "actriz",
        "gran hermano", "supervivientes", "operacion triunfo", "isla de las tentaciones", "pasapalabra",
        "el hormiguero", "la revuelta", "broncano", "pablo motos", "masterchef", "la voz", "tu cara me suena",
        "first dates", "telecinco", "antena 3", "la 1", "rtve", "cuatro", "la sexta", "premios goya", "goya",
        "oscar", "oscars", "emmy", "festival de cine", "festival de san sebastian", "cannes", "venecia",
        "reality", "presentador", "presentadora", "influencer", "youtuber", "boda", "famosos", "telenovela",
        "anime", "marvel", "star wars", "harry potter", "trailer", "taquilla", "cine",
    ],
    "musica": [
        "concierto", "conciertos", "gira", "album", "disco", "cancion", "single", "festival", "eurovision",
        "benidorm fest", "los40", "grammy", "grammys", "latin grammy", "rosalia", "bad bunny", "aitana",
        "quevedo", "bizarrap", "karol g", "shakira", "taylor swift", "coldplay", "estopa", "alejandro sanz",
        "melendi", "dani martin", "lola indigo", "c tangana", "rels b", "myke towers", "feid", "morat",
        "primavera sound", "mad cool", "bbk live", "sonar", "arenal sound", "vina rock", "rapero", "cantante",
        "rap", "reggaeton", "flamenco", "spotify", "videoclip", "entradas",
    ],
    "historia": [
        "historia", "historico", "historica", "guerra civil", "franco", "franquismo", "segunda republica",
        "republica", "dictadura", "transicion", "imperio", "imperio romano", "romano", "romanos", "egipto",
        "faraon", "piramide", "piramides", "edad media", "medieval", "reconquista", "al andalus",
        "reyes catolicos", "isabel la catolica", "cristobal colon", "colon", "conquista", "hernan cortes",
        "pizarro", "napoleon", "hitler", "nazi", "nazis", "segunda guerra mundial", "primera guerra mundial",
        "holocausto", "revolucion francesa", "aniversario", "efemeride", "arqueologia", "arqueologico",
        "arqueologicos", "yacimiento", "museo", "patrimonio", "unesco", "monasterio", "catedral", "castillo",
        "templarios", "vikingos", "inquisicion", "armada invencible", "felipe ii", "carlos v", "siglo",
        "dinastia", "momia", "tesoro", "naufragio", "pecio", "biblioteca", "literatura", "premio planeta",
        "premio cervantes", "nobel de literatura", "escritor", "escritora", "novela", "poeta", "pintor",
        "picasso", "dali", "goya pintor", "velazquez", "cervantes", "quijote", "lorca", "arte",
        "batalla", "batallas", "emperador", "emperatriz", "conquistadores", "civilizacion", "antigua roma",
        "antiguo egipto", "mayas", "aztecas", "incas", "corona de castilla", "hispania", "visigodos", "celtas",
        "iberos", "almirante", "carabela", "galeon", "tercios", "guerra de independencia", "guerra fria",
        "cruzadas", "edad moderna", "hispanidad", "lepanto", "trafalgar", "juan de austria", "imperio otomano",
    ],
    "tecnologia": [
        "iphone", "apple", "samsung", "android", "google", "microsoft", "meta", "whatsapp", "instagram",
        "tiktok", "openai", "chatgpt", "inteligencia artificial", "ia", "gemini", "claude", "nvidia", "tesla",
        "elon musk", "musk", "ciberataque", "hackeo", "xiaomi", "ios", "macbook", "ipad", "apple watch",
        "smartphone", "movil", "moviles", "aplicacion", "app", "actualizacion", "caida de", "se cae",
        "no funciona", "starlink", "robot", "chip", "chips", "internet", "wifi", "5g", "streaming", "x twitter",
    ],
    "ciencia": [
        "nasa", "esa", "cometa", "eclipse", "eclipse solar", "eclipse lunar", "luna", "superluna", "marte",
        "asteroide", "meteorito", "telescopio", "james webb", "descubrimiento", "cientificos", "cientifico",
        "estudio", "investigacion", "fosil", "fosiles", "dinosaurio", "dinosaurios", "volcan", "erupcion",
        "aurora boreal", "auroras boreales", "lluvia de estrellas", "perseidas", "leonidas", "gemínidas",
        "geminidas", "espacio", "astronauta", "cohete", "spacex", "nobel de fisica", "nobel de quimica",
        "nobel de medicina", "premio nobel", "nobel", "fisiologia o medicina", "genetica", "adn", "cerebro", "evolucion", "especie",
    ],
    "videojuegos": [
        "gta", "gta 6", "gta vi", "fortnite", "minecraft", "roblox", "playstation", "ps5", "ps6", "nintendo",
        "switch 2", "nintendo switch", "xbox", "steam", "league of legends", "valorant", "call of duty",
        "ea fc", "ea sports fc", "pokemon", "zelda", "mario", "elden ring", "twitch", "ibai", "kings league",
        "queens league", "streamer", "videojuego", "videojuegos", "gamer", "esports", "nintendo direct",
        "state of play", "game awards", "the game awards", "battlefield", "assassins creed", "hollow knight",
    ],
    "salud": [
        "covid", "gripe", "virus", "vacuna", "vacunas", "hospital", "hospitales", "sanidad", "medico",
        "medicos", "enfermedad", "cancer", "alzheimer", "salud mental", "brote", "epidemia", "pandemia",
        "sintomas", "infeccion", "bacteria", "ictus", "infarto", "diabetes", "obesidad", "dieta", "ozempic",
        "medicamento", "farmacia", "lista de espera", "urgencias", "enfermeras", "suicidio",
    ],
    "clima": [
        "aemet", "dana", "lluvia", "lluvias", "tormenta", "tormentas", "temporal", "nieve", "nevada",
        "ola de calor", "calor", "frio", "ola de frio", "alerta roja", "alerta naranja", "aviso amarillo",
        "aviso naranja", "aviso rojo", "inundaciones", "inundacion", "incendio forestal", "incendios",
        "sequia", "terremoto", "seismo", "huracan", "borrasca", "granizo", "viento", "cambio climatico",
        "el tiempo", "prevision", "temperaturas",
    ],
    "motor": [
        "coche", "coches", "dgt", "carnet de conducir", "multa", "multas", "seat", "cupra", "renault",
        "toyota", "volkswagen", "bmw", "mercedes", "ford", "hyundai", "kia", "byd", "coche electrico",
        "electricos", "itv", "radar", "radares", "trafico", "autopista", "peaje", "baliza v16", "moto", "motos",
    ],
    "estilo": [
        "moda", "zara", "mango", "desfile", "pasarela", "belleza", "maquillaje", "met gala", "vestido",
        "look", "tendencia de moda", "pelo", "peinado", "skincare", "perfume", "rebajas zara", "shein",
    ],
    "gastronomia": [
        "receta", "recetas", "restaurante", "restaurantes", "chef", "michelin", "estrella michelin",
        "tortilla", "paella", "comida", "bebida", "vino", "cerveza", "aceite de oliva", "jamon", "cocina",
        "gastronomia", "dulce", "turron", "roscon", "pan", "cafe",
    ],
    "viajes": [
        "vuelo", "vuelos", "aeropuerto", "aeropuertos", "renfe", "ave", "tren", "trenes", "cercanias",
        "ryanair", "iberia", "vueling", "aena", "turismo", "turistas", "viaje", "viajes", "hotel", "hoteles",
        "playa", "playas", "metro", "autobus", "huelga de taxis", "pasaporte", "puente", "vacaciones",
    ],
    "educacion": [
        "oposiciones", "selectividad", "pau", "ebau", "evau", "universidad", "universidades", "colegio",
        "colegios", "becas", "beca", "educacion", "profesores", "docentes", "examen", "examenes",
        "empleo publico", "sepe", "curso escolar", "vuelta al cole", "notas", "fp", "formacion profesional",
        "empleo", "trabajo", "ofertas de empleo",
    ],
    "animales": [
        "perro", "perros", "gato", "gatos", "animal", "animales", "zoo", "lince", "oso", "osos", "lobo",
        "lobos", "ballena", "ballenas", "orca", "orcas", "tiburon", "mascota", "mascotas", "veterinario",
    ],
    "ocio": [
        "loteria", "loteria de navidad", "el gordo", "sorteo", "black friday", "rebajas", "ofertas",
        "prime day", "ikea", "primark", "lidl", "aldi", "halloween", "navidad", "carnaval", "fallas",
        "san fermin", "feria de abril", "semana santa", "parque de atracciones", "concurso",
    ],
    "actualidad": [
        "detenido", "detenida", "detenidos", "asesinato", "asesinada", "asesinado", "crimen", "muerto",
        "muertos", "muere", "fallece", "fallecido", "fallecida", "accidente", "incendio", "explosion",
        "desaparecido", "desaparecida", "guardia civil", "policia nacional", "policia", "mossos", "juicio",
        "condena", "condenado", "sentencia", "apagon", "huelga", "manifestacion", "protesta", "okupa",
        "okupas", "atentado", "tiroteo", "rescate", "evacuacion", "ultima hora", "casa real", "rey felipe",
        "princesa leonor", "reina letizia", "suceso", "sucesos", "violencia", "agresion", "robo", "estafa",
        "cambio de hora",
    ],
}

UTILITY_PATTERNS = [
    "bonoloto", "euromillones", "primitiva", "la primitiva", "loteria nacional", "comprobar loteria",
    "cupon once", "once", "quiniela", "el gordo de la primitiva", "eurojackpot", "lototurf", "quinigol",
    "super once", "triplex", "eurodreams", "el tiempo", "tiempo manana", "calendario laboral",
    "resultados loteria", "horario", "donde ver", "a que hora", "cita previa", "traductor",
    "feliz lunes", "feliz martes", "feliz miercoles", "feliz jueves", "feliz viernes", "feliz sabado",
    "feliz domingo", "feliz finde", "feliz fin de semana", "buenos dias", "buenas noches", "buen lunes",
]

UTILITY_EXACT = {
    "el pais", "elpais", "el mundo", "elmundo", "abc", "cope", "cadena ser", "la vanguardia", "rtve",
    "rtve play", "el confidencial", "okdiario", "ok diario", "eldiario", "eldiario es", "20 minutos",
    "el espanol", "la razon", "publico", "el periodico", "marca", "as", "mundo deportivo", "sport",
    "europa press", "noticias", "ultimas noticias", "ultima hora", "noticias de hoy", "tiempo", "meteo",
    "telediario", "antena 3", "antena 3 noticias", "telecinco", "la sexta", "lasexta", "cuatro", "tve",
    "la 1", "atresplayer", "mitele", "google", "youtube", "facebook", "instagram", "whatsapp web",
    "gmail", "hotmail", "outlook", "google translate", "traductor google", "el periodico de catalunya",
    "ara", "vilaweb", "naiz", "deia", "el correo", "la voz de galicia", "faro de vigo", "levante emv",
    "las provincias", "diario de sevilla", "heraldo", "el norte de castilla", "diario sur", "ideal",
}

DESCRIPTION_KEYWORDS = {
    "deportes": ["futbolista", "football", "soccer", "club de futbol", "football club", "tenista", "tennis",
                 "piloto", "racing driver", "baloncestista", "basketball", "ciclista", "deportista", "atleta",
                 "athlete", "entrenador", "boxeador", "luchador", "jugador", "player", "equipo de", "team",
                 "competicion", "tournament", "torneo", "temporada"],
    "politica": ["politico", "politica espanola", "politician", "partido politico", "political party",
                 "presidente del gobierno", "ministro", "minister", "diputado", "senador", "alcalde"],
    "internacional": ["presidente de los estados unidos", "president of the united states", "primer ministro",
                      "prime minister", "pais", "country", "conflicto", "organizacion internacional"],
    "entretenimiento": ["actor", "actriz", "actress", "presentador", "presentadora", "serie de television",
                        "television series", "pelicula", "film", "reality", "programa de television",
                        "television program", "youtuber", "influencer", "modelo", "personaje", "character",
                        "telenovela", "miniserie", "anime", "manga", "comic"],
    "musica": ["cantante", "singer", "rapero", "rapper", "musico", "musician", "banda", "band",
               "grupo musical", "album", "cancion", "song", "compositor", "composer", "dj", "festival de musica"],
    "historia": ["batalla", "battle", "guerra", "war", "imperio", "empire", "dinastia", "dynasty", "reino",
                 "kingdom", "monarca", "emperador", "emperor", "faraon", "pharaoh", "conquistador", "explorador",
                 "revolucion", "revolution", "siglo", "century", "antigua", "ancient", "medieval", "historico",
                 "historical", "arqueologico", "archaeological", "genocidio", "holocausto", "dictador",
                 "dictator", "almirante", "navegante", "rey de", "reina de", "king of", "queen of", "santo",
                 "escritor", "writer", "novelista", "poeta", "poet", "pintor", "painter", "filosofo",
                 "philosopher", "novela", "novel", "obra de teatro", "monumento", "catedral", "castillo"],
    "ciencia": ["cientifico", "scientist", "fisico", "physicist", "quimico", "chemist", "matematico",
                "astronomo", "cometa", "comet", "planeta", "planet", "asteroide", "especie", "species",
                "fenomeno", "teoria"],
    "tecnologia": ["empresa tecnologica", "software", "sistema operativo", "smartphone", "red social",
                   "social network", "inteligencia artificial", "artificial intelligence", "aplicacion movil",
                   "empresario", "businessman", "chatbot"],
    "videojuegos": ["videojuego", "video game", "streamer", "esports"],
    "actualidad": ["asesinato", "crimen", "desastre", "catastrofe", "accidente", "terremoto", "atentado",
                   "ataque", "incendio", "naufragio", "papa de la iglesia", "pope"],
    "economia": ["empresa", "company", "multinacional", "banco", "bank", "economista", "economist",
                 "moneda", "currency"],
    "clima": ["huracan", "hurricane", "tormenta", "storm", "borrasca", "dana"],
    "salud": ["enfermedad", "disease", "virus", "sindrome", "syndrome", "medicamento", "drug"],
}

_HISTORIC_YEAR_RE = re.compile(r"\b(?:1[0-8]\d\d|19[0-6]\d)\b|\ba\.\s?c\.?", re.I)


def _compile(phrases):
    unique = sorted({norm(p) for p in phrases if norm(p)}, key=len, reverse=True)
    pattern = "|".join(re.escape(p) for p in unique)
    return re.compile(r"(?<![a-z0-9])(?:" + pattern + r")(?![a-z0-9])")


_RULES = [(niche, _compile(phrases)) for niche, phrases in KEYWORDS.items()]
_DESC_RULES = [(niche, _compile(phrases)) for niche, phrases in DESCRIPTION_KEYWORDS.items()]
_UTILITY_RX = _compile(UTILITY_PATTERNS)


def keyword_scores(text: str, rules=None) -> dict:
    normalized = norm(text)
    scores = {}
    if not normalized:
        return scores
    for niche, rx in rules or _RULES:
        hits = rx.findall(normalized)
        if hits:
            scores[niche] = sum(2 if " " in hit else 1 for hit in hits)
    return scores


def is_utility(text: str) -> bool:
    normalized = norm(text)
    return normalized in UTILITY_EXACT or bool(_UTILITY_RX.search(normalized))


def _add(total: dict, scores: dict, weight: float) -> None:
    for niche, value in scores.items():
        total[niche] = total.get(niche, 0.0) + value * weight


def classify(title: str, related=(), headlines=(), base=None, description: str = "", prior=None) -> list:
    scores = {}
    _add(scores, keyword_scores(title), 2.0)
    for text in list(related)[:10]:
        _add(scores, keyword_scores(text), 1.0)
    for text in list(headlines)[:8]:
        _add(scores, keyword_scores(text), 0.5)
    if description:
        _add(scores, keyword_scores(description, _DESC_RULES), 2.0)
        if _HISTORIC_YEAR_RE.search(description) and "historia" not in scores:
            scores["historia"] = scores.get("historia", 0.0) + 1.5

    if prior is None:
        prior = {"otros": 0.0, "ocio": 1.0}.get(base, 2.5) if base else 0.0
    if base:
        scores[base] = scores.get(base, 0.0) + prior

    if base == "entretenimiento" and scores.get("musica", 0) >= 2:
        scores["musica"] = scores.get("musica", 0) + prior
    if base == "politica" and scores.get("internacional", 0) >= 2 and scores.get("internacional", 0) >= scores.get("politica", 0) - prior:
        scores["internacional"] = scores.get("internacional", 0) + prior

    if not scores:
        return [base or "otros"]
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], NICHE_ORDER.get(kv[0], 99)))
    primary = ranked[0][0]
    if primary == "otros" and len(ranked) > 1 and ranked[1][1] > 0:
        primary = ranked[1][0]
    result = [primary]
    for niche, value in ranked[1:]:
        if niche != "otros" and value >= 2 and len(result) < 3:
            result.append(niche)
    return result


def niche_from_tiktok_industry(label) -> str:
    text = norm(label if isinstance(label, str) else "")
    table = [
        ("educ", "educacion"), ("deport", "deportes"), ("sport", "deportes"), ("jueg", "videojuegos"),
        ("game", "videojuegos"), ("comida", "gastronomia"), ("food", "gastronomia"), ("bebida", "gastronomia"),
        ("belleza", "estilo"), ("beauty", "estilo"), ("ropa", "estilo"), ("apparel", "estilo"),
        ("tecnolog", "tecnologia"), ("tech", "tecnologia"), ("app", "tecnologia"), ("viaj", "viajes"),
        ("travel", "viajes"), ("vehic", "motor"), ("mascota", "animales"), ("pet", "animales"),
        ("financ", "economia"), ("business", "economia"), ("negocio", "economia"), ("salud", "salud"),
        ("health", "salud"), ("noticia", "actualidad"), ("news", "entretenimiento"),
        ("entreten", "entretenimiento"), ("entertain", "entretenimiento"),
    ]
    for needle, niche in table:
        if needle in text:
            return niche
    return "ocio" if text else "otros"
