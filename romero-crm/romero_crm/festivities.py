"""Festividades de España y algunos días internacionales para el calendario.

Solo fechas seguras: las fijas y las que salen de una regla (Pascua, último domingo de octubre, primer
domingo de mayo…). Cuando la fecha tiene una historia que contar, lleva una idea de vídeo; las ideas
se limitan a hechos comprobables, sin adornos."""
from __future__ import annotations

import datetime as dt

KIND_LABELS = {
    "nacional": "Festivo nacional",
    "autonomico": "Día autonómico",
    "tradicion": "Tradición",
    "internacional": "Día internacional",
    "aviso": "Fecha clave",
}

_HOUR_IDEA = "Por qué España vive con la hora de Berlín: el cambio de huso de 1940."

FIXED = [
    (1, 1, "Año Nuevo", "nacional", None),
    (1, 6, "Día de Reyes", "nacional", "Por qué en España los regalos los traen los Reyes Magos: el origen de la tradición y de la cabalgata."),
    (1, 27, "Día en memoria del Holocausto", "internacional", "Los republicanos españoles deportados a Mauthausen: la parte española del Holocausto."),
    (2, 4, "Día Mundial contra el Cáncer", "internacional", None),
    (2, 11, "Día de la Mujer y la Niña en la Ciencia", "internacional", None),
    (2, 14, "San Valentín", "tradicion", "¿Quién fue san Valentín? La historia que hay detrás de la fecha."),
    (2, 28, "Día de Andalucía", "autonomico", "28-F de 1980: el referéndum que llevó a Andalucía a la autonomía plena."),
    (3, 1, "Día de las Illes Balears", "autonomico", None),
    (3, 8, "Día Internacional de la Mujer", "internacional", "Mujeres que cambiaron la historia de España y casi nadie recuerda."),
    (3, 14, "Día de Pi", "internacional", None),
    (3, 19, "San José · Día del Padre", "tradicion", None),
    (3, 19, "Cremà de las Fallas", "tradicion", "Por qué Valencia quema sus fallas cada 19 de marzo: el origen de la cremà."),
    (3, 21, "Día Mundial de la Poesía", "internacional", None),
    (3, 22, "Día Mundial del Agua", "internacional", None),
    (4, 7, "Día Mundial de la Salud", "internacional", None),
    (4, 22, "Día de la Tierra", "internacional", None),
    (4, 23, "Día del Libro · Sant Jordi", "tradicion", "Cervantes y Shakespeare: por qué el Día del Libro es el 23 de abril (y por qué en realidad no murieron el mismo día)."),
    (4, 23, "Día de Aragón", "autonomico", None),
    (4, 23, "Día de Castilla y León", "autonomico", "Villalar, 1521: la derrota de los comuneros que acabó siendo un símbolo."),
    (5, 1, "Fiesta del Trabajo", "nacional", "Por qué el 1 de mayo: la revuelta de Haymarket (Chicago, 1886)."),
    (5, 2, "Día de la Comunidad de Madrid", "autonomico", "El Dos de Mayo de 1808: el levantamiento que pintó Goya."),
    (5, 3, "Día de la Libertad de Prensa", "internacional", None),
    (5, 9, "Día de Europa", "internacional", "9 de mayo de 1950: la declaración Schuman y el origen de la Unión Europea."),
    (5, 15, "San Isidro (Madrid)", "tradicion", None),
    (5, 18, "Día Internacional de los Museos", "internacional", None),
    (5, 30, "Día de Canarias", "autonomico", None),
    (5, 31, "Día de Castilla-La Mancha", "autonomico", None),
    (6, 5, "Día Mundial del Medio Ambiente", "internacional", None),
    (6, 9, "Día de la Región de Murcia y de La Rioja", "autonomico", None),
    (6, 23, "Noche de San Juan", "tradicion", "La noche de San Juan: hogueras, solsticio y tradiciones que vienen de muy atrás."),
    (6, 28, "Día del Orgullo LGTBI", "internacional", "Stonewall (1969) y la historia del Orgullo en España."),
    (7, 6, "Chupinazo de San Fermín", "tradicion", "San Fermín: cómo Hemingway convirtió una fiesta local en un fenómeno mundial."),
    (7, 25, "Santiago Apóstol · Día de Galicia", "autonomico", "Cómo nació el Camino de Santiago."),
    (7, 28, "Día de las Instituciones de Cantabria", "autonomico", None),
    (8, 15, "Asunción de la Virgen", "nacional", None),
    (9, 2, "Día de Ceuta", "autonomico", None),
    (9, 8, "Día de Asturias y de Extremadura", "autonomico", None),
    (9, 11, "Diada de Cataluña", "autonomico", "Por qué la Diada recuerda el 11 de septiembre de 1714."),
    (9, 17, "Día de Melilla", "autonomico", None),
    (9, 21, "Día Internacional de la Paz", "internacional", None),
    (9, 27, "Día Mundial del Turismo", "internacional", None),
    (10, 5, "Día Mundial de los Docentes", "internacional", None),
    (10, 9, "Día de la Comunitat Valenciana", "autonomico", "9 de octubre de 1238: la entrada de Jaime I en Valencia."),
    (10, 10, "Día Mundial de la Salud Mental", "internacional", None),
    (10, 12, "Fiesta Nacional de España", "nacional", "Por qué el 12 de octubre: de la llegada de Colón en 1492 a fiesta nacional."),
    (10, 16, "Día Mundial de la Alimentación", "internacional", None),
    (10, 24, "Día de las Naciones Unidas", "internacional", "Por qué España no entró en la ONU hasta 1955."),
    (10, 31, "Halloween", "tradicion", "Las tradiciones españolas de difuntos que Halloween ha eclipsado: la castañada, el Samaín…"),
    (11, 1, "Todos los Santos", "nacional", "Todos los Santos y Halloween: dos fiestas con la misma raíz."),
    (11, 2, "Día de Difuntos", "tradicion", None),
    (11, 20, "Día Universal del Niño", "internacional", None),
    (11, 25, "Día contra la Violencia hacia las Mujeres", "internacional", None),
    (12, 1, "Día Mundial del Sida", "internacional", None),
    (12, 3, "Día de Navarra", "autonomico", None),
    (12, 6, "Día de la Constitución", "nacional", "6 de diciembre de 1978: cómo votó España su Constitución."),
    (12, 8, "Inmaculada Concepción", "nacional", None),
    (12, 10, "Día de los Derechos Humanos", "internacional", "1948: cómo se escribió la Declaración Universal de los Derechos Humanos."),
    (12, 22, "Sorteo de la Lotería de Navidad", "tradicion", "El sorteo que se celebra desde 1812: cómo nació la Lotería de Navidad en Cádiz."),
    (12, 24, "Nochebuena", "tradicion", None),
    (12, 25, "Navidad", "nacional", None),
    (12, 28, "Día de los Santos Inocentes", "tradicion", "Por qué en España las bromas son el 28 de diciembre y no el 1 de abril."),
    (12, 31, "Nochevieja", "tradicion", "Las doce uvas: de dónde sale la costumbre."),
]


def easter(year: int) -> dt.date:
    """Domingo de Pascua (algoritmo gregoriano anónimo de Meeus/Jones/Butcher)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return dt.date(year, month, day + 1)


def _weekday_in_month(year: int, month: int, weekday: int, nth: int) -> dt.date:
    """El nth `weekday` (0 = lunes) del mes; nth = -1 es el último."""
    if nth > 0:
        first = dt.date(year, month, 1)
        return first + dt.timedelta(days=(weekday - first.weekday()) % 7 + 7 * (nth - 1))
    last = (dt.date(year, month % 12 + 1, 1) if month < 12 else dt.date(year + 1, 1, 1)) - dt.timedelta(days=1)
    return last - dt.timedelta(days=(last.weekday() - weekday) % 7)


def movable(year: int) -> list:
    sunday = easter(year)
    thanksgiving = _weekday_in_month(year, 11, 3, 4)
    return [
        (sunday - dt.timedelta(days=47), "Carnaval", "tradicion", "El carnaval que Franco prohibió: cómo sobrevivió en Cádiz y en Tenerife."),
        (sunday - dt.timedelta(days=7), "Domingo de Ramos", "tradicion", None),
        (sunday - dt.timedelta(days=3), "Jueves Santo", "autonomico", None),
        (sunday - dt.timedelta(days=2), "Viernes Santo", "nacional", None),
        (sunday, "Domingo de Resurrección", "tradicion", None),
        (sunday + dt.timedelta(days=1), "Lunes de Pascua (en algunas comunidades)", "autonomico", None),
        (sunday + dt.timedelta(days=60), "Corpus Christi", "tradicion", None),
        (_weekday_in_month(year, 5, 6, 1), "Día de la Madre", "tradicion", None),
        (_weekday_in_month(year, 3, 6, -1), "Cambio al horario de verano", "aviso", _HOUR_IDEA),
        (_weekday_in_month(year, 10, 6, -1), "Cambio al horario de invierno", "aviso", _HOUR_IDEA),
        (thanksgiving + dt.timedelta(days=1), "Black Friday", "tradicion", "De dónde viene el nombre «Black Friday»."),
    ]


def for_range(start: dt.date, end: dt.date) -> dict:
    """{fecha ISO: [festividades]} entre start y end, ambos incluidos."""
    out = {}
    for year in range(start.year, end.year + 1):
        entries = [(dt.date(year, m, d), name, kind, idea) for m, d, name, kind, idea in FIXED]
        entries += movable(year)
        for date, name, kind, idea in entries:
            if start <= date <= end:
                out.setdefault(date.isoformat(), []).append({
                    "name": name, "kind": kind, "kind_label": KIND_LABELS[kind], "idea": idea,
                    "spain": kind != "internacional",
                })
    order = {"nacional": 0, "aviso": 1, "autonomico": 2, "tradicion": 3, "internacional": 4}
    for items in out.values():
        items.sort(key=lambda f: (order[f["kind"]], f["idea"] is None))
    return out
