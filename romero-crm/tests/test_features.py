import datetime as dt
import json
import re
import tempfile
import time
import types
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from romero_crm import ai, connections, festivities, planner, recap, stories
from romero_crm.config import Settings
from romero_crm.demo import DemoData
from romero_crm.engine import Engine
from romero_crm.server import AppServer
from romero_crm.storage import Storage


def demo_engine(root: Path) -> Engine:
    (root / "cache").mkdir(exist_ok=True)
    storage = Storage(root)
    demo = DemoData()
    demo.seed_planner(storage)
    engine = Engine(Settings(root / "settings.json"), storage, demo.load)
    engine.refresh(force=True)
    return engine


TOPIC_EXTRA = {"phase": "subiendo", "sources": ["x"], "phase_reason": "", "why": None, "related": []}


def topic(key, title, niche, headlines, related=(), heat=50, trend=False):
    return {"key": key, "title": title, "niche": niche, "niches": [niche], "heat": heat, "potential": 40,
            "utility": False, "news": {"items": [{"title": h, "from_trend": trend} for h in headlines]},
            "related": list(related)}


def keys_of(groups):
    return sorted(sorted(t["key"] for t in g) for g in groups)


class StoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.engine = demo_engine(Path(cls.tmp.name))
        cls.state = cls.engine.get_state()
        cls.by_title = {s["title"]: s for s in cls.state["stories"]}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_elections_are_one_story(self):
        story = self.by_title["Elecciones generales"]
        members = {m["title"] for m in story["members"]}
        self.assertTrue({"Pedro Sánchez", "Feijóo", "Coalición de izquierdas"} <= members, members)
        self.assertNotIn("Pedro Sánchez", self.by_title)
        self.assertEqual(story["scope"], "espana")
        self.assertGreater(story["volume"], 100000)

    def test_portada_has_five_with_alert_first(self):
        front = self.state["portada"]
        self.assertEqual(len(front["keys"]), 5)
        self.assertEqual(front["alerts"], ["whatsappcaido"])
        self.assertEqual(front["keys"][0], "whatsappcaido")
        self.assertIn("eleccionesgenerales", front["keys"])

    def test_world_and_routine(self):
        self.assertEqual(self.by_title["Aranceles trump"]["scope"], "mundo")
        self.assertTrue(self.by_title["Real Madrid - Villarreal"]["routine"])
        self.assertTrue(self.by_title["La Revuelta"]["routine"])
        self.assertNotIn(self.by_title["La Revuelta"]["key"], self.state["portada"]["keys"])

    def test_synopsis_and_angle_come_from_data(self):
        story = self.by_title["Elecciones generales"]
        self.assertEqual(len(story["synopsis"]), 2)
        self.assertNotEqual(story["synopsis"][0]["source"], story["synopsis"][1]["source"])
        tips = " ".join(story["angle"]["tips"])
        self.assertIn("cuándo son las elecciones generales", tips)
        lepanto = self.by_title["Batalla de Lepanto"]
        self.assertEqual(lepanto["angle"]["urgency"], "ahora")
        whatsapp = self.by_title["WhatsApp caído"]
        self.assertEqual(whatsapp["angle"]["urgency"], "angulo")
        self.assertTrue(any("WhatsApp CAÍDO hoy" in t for t in whatsapp["angle"]["tips"]))

    def test_unrelated_topics_stay_apart(self):
        groups = stories.cluster([
            topic("a", "Huelga de médicos", "salud", ["Los médicos van a la huelga el lunes"], trend=True),
            topic("b", "Alcaraz", "deportes", ["Alcaraz gana en Pekín"]),
            topic("c", "Ministerio de Sanidad", "salud", ["Los médicos van a la huelga el lunes"], trend=True),
        ])
        self.assertEqual(keys_of(groups), [["a", "c"], ["b"]])

    def test_event_families_from_real_data(self):
        # Caso real (6 de octubre de 2026): Sánchez convoca elecciones y a la vez son tendencia Abascal, Page,
        # «PP y Vox» o el Frente Amplio sin decir «elecciones» en el título; y una huelga general aparte.
        groups = stories.cluster([
            topic("elec", "Elecciones generales España", "politica", [
                "Pedro Sánchez anuncia la convocatoria de elecciones generales para el 29 de noviembre",
                "Sánchez adelanta las elecciones al 29 de noviembre"], heat=60, trend=True),
            topic("abascal", "Abascal", "politica", [
                "Ayuso y Abascal azuzan la idea de un posible pucherazo ante el adelanto electoral"], heat=56),
            topic("page", "Page", "politica", [
                "Page ironiza sobre la posibilidad de que Sánchez saque un buen resultado el 29-N",
                "Page celebra la convocatoria de elecciones y avisa: no renunciaré a mis ideas"], heat=54, trend=True),
            topic("frente", "Frente Amplio", "politica", [
                "Mónica García favorita como candidata del Frente Amplio",
                "El 29N dinamita los calendarios de Frente Amplio"], heat=57, trend=True),
            topic("huelga", "Huelga general", "economia", [
                "UGT y CCOO convocan una huelga general por la crisis de la vivienda",
                "El Sindicato de Inquilinas prepara una huelga general tras el anuncio de elecciones anticipadas el 29N"],
                heat=40, trend=True),
            topic("brasil", "Elecciones generales de Brasil de 2026", "politica", [
                "Bolsonaro vence a Lula en primera vuelta de las elecciones en Brasil",
                "Elecciones en Brasil: Bolsonaro y Lula en segunda vuelta"], heat=58, trend=True),
            topic("cortes", "Cortés", "politica", [
                "Íñigo Cortés, entrenador del Ribadesella: soy cántabro",
                "¿Es constitucional aprobar los decretos de vivienda tras la disolución de las Cortes?"], heat=58),
        ])
        self.assertEqual(keys_of(groups), [["abascal", "elec", "frente", "page"], ["brasil"], ["cortes"], ["huelga"]])
        self.assertTrue(stories.unconfirmed(topic("cortes", "Cortés", "politica", [
            "Íñigo Cortés, entrenador del Ribadesella", "Manuel Cortés anuncia una oficina de la Policía Local"])))

    def test_lead_is_what_the_others_talk_about(self):
        film = topic("film", "La bola negra (película)", "entretenimiento", [], heat=47)
        actor = topic("actor", "Miguel Bernardeau", "entretenimiento", [
            "Miguel Bernardeau, protagonista de 'La bola negra', invitado en 'Al cielo con ella'",
            "De su romance con Aitana al aplauso de la crítica por La bola negra"], heat=61)
        groups = stories.cluster([film, actor])
        self.assertEqual(keys_of(groups), [["actor", "film"]])
        story = stories.build_stories([dict(film, **TOPIC_EXTRA), dict(actor, **TOPIC_EXTRA)])[0]
        self.assertEqual(story["title"], "La bola negra")
        self.assertEqual(story["heat"], 61)

    def test_person_names_count_surname_as_weak_evidence(self):
        self.assertEqual(stories.title_phrases("Pedro Sánchez"), [("pedro sanchez", True)])
        self.assertEqual(stories.title_phrases("José Luis Ozores"), [("jose luis ozores", True), ("ozores", False)])
        self.assertEqual(stories.title_phrases("La bola negra taquilla"), [("la bola negra taquilla", True), ("la bola negra", True)])
        self.assertEqual(stories.title_phrases("Elecciones"), [])

    def test_alert_needs_everything_at_once(self):
        base = {"routine": False, "phase": "explosivo", "elapsed_hours": 2, "scope": "espana", "heat": 90,
                "volume": 500000, "x_rank": 1, "outlets": 3, "sources": ["google", "x", "news"]}
        self.assertTrue(stories.is_alert(base))
        self.assertFalse(stories.is_alert(dict(base, routine=True)))
        self.assertFalse(stories.is_alert(dict(base, volume=50000)))
        self.assertFalse(stories.is_alert(dict(base, scope="mundo", volume=300000)))
        self.assertFalse(stories.is_alert(dict(base, elapsed_hours=30)))


class FestivityTests(unittest.TestCase):
    def test_easter(self):
        known = {2024: (3, 31), 2025: (4, 20), 2026: (4, 5), 2027: (3, 28), 2028: (4, 16), 2030: (4, 21)}
        for year, (month, day) in known.items():
            self.assertEqual(festivities.easter(year), dt.date(year, month, day), year)

    def test_october_and_movable_dates(self):
        fests = festivities.for_range(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
        names = lambda iso: [f["name"] for f in fests.get(iso, [])]
        self.assertIn("Fiesta Nacional de España", names("2026-10-12"))
        self.assertTrue(next(f for f in fests["2026-10-12"] if f["name"] == "Fiesta Nacional de España")["idea"])
        self.assertIn("Cambio al horario de invierno", names("2026-10-25"))
        self.assertIn("Cambio al horario de verano", names("2026-03-29"))
        self.assertIn("Black Friday", names("2026-11-27"))
        self.assertIn("Carnaval", names("2026-02-17"))
        self.assertIn("Día de la Madre", names("2026-05-03"))
        self.assertIn("Viernes Santo", names("2026-04-03"))
        self.assertFalse(next(f for f in fests["2026-10-05"] if "Docentes" in f["name"])["spain"])


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.storage = Storage(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_validation(self):
        with self.assertRaises(planner.InvalidItem):
            planner.clean_item({"day": "2026-13-40", "title": "x"})
        with self.assertRaises(planner.InvalidItem):
            planner.clean_item({"day": "2026-10-06", "title": "   "})
        with self.assertRaises(planner.InvalidItem):
            planner.clean_item({"day": "2026-10-06", "title": "x", "kind": "fiesta"})
        item = planner.clean_item({"day": "2026-10-06", "title": "  Ruiz-Mateos  ", "platforms": ["tiktok", "myspace"],
                                   "links": [{"url": "javascript:alert(1)"}, {"url": "https://www.tiktok.com/@a/video/1"}], "time": "25:00"})
        self.assertEqual(item["title"], "Ruiz-Mateos")
        self.assertEqual(item["platforms"], ["tiktok"])
        self.assertEqual([l["url"] for l in item["links"]], ["https://www.tiktok.com/@a/video/1"])
        self.assertEqual(item["links"][0]["platform"], "tiktok")
        self.assertIsNone(item["time"])

    def test_roundtrip_and_done(self):
        saved = self.storage.save_plan_item(planner.clean_item({"day": "2026-10-07", "title": "Cuenca", "kind": "grabar"}))
        self.assertFalse(saved["done"])
        done = self.storage.save_plan_item({"id": saved["id"], "done": True})
        self.assertTrue(done["done"])
        self.assertTrue(done["done_at"])
        self.assertEqual(done["title"], "Cuenca")
        undone = self.storage.save_plan_item({"id": saved["id"], "done": False})
        self.assertIsNone(undone["done_at"])
        self.assertEqual(len(self.storage.plan_items("2026-10-01", "2026-10-31")), 1)
        self.assertTrue(self.storage.delete_plan_item(saved["id"]))
        self.assertEqual(self.storage.plan_items("2026-10-01", "2026-10-31"), [])

    def test_month_grid(self):
        first, last, start, end = planner.month_grid("2026-10")
        self.assertEqual((first, last), (dt.date(2026, 10, 1), dt.date(2026, 10, 31)))
        self.assertEqual(start.weekday(), 0)
        self.assertEqual(end.weekday(), 6)
        self.storage.save_plan_item(planner.clean_item({"day": "2026-10-12", "title": "Fiesta Nacional", "kind": "publicar"}))
        data = planner.calendar_month(self.storage, None, "2026-10", today=dt.date(2026, 10, 6))
        self.assertEqual(len(data["days"]) % 7, 0)
        day = next(d for d in data["days"] if d["date"] == "2026-10-12")
        self.assertEqual([i["title"] for i in day["items"]], ["Fiesta Nacional"])
        self.assertTrue(any(f["name"] == "Fiesta Nacional de España" for f in day["festivities"]))
        self.assertTrue(next(d for d in data["days"] if d["date"] == "2026-10-06")["today"])

    def test_auto_match_marks_published(self):
        today = dt.date.today()
        item = self.storage.save_plan_item(planner.clean_item({"day": today.isoformat(), "title": "Ruiz-Mateos", "kind": "publicar"}))
        self.storage.upsert_published([{"platform": "youtube", "vid": "abc", "url": "https://www.youtube.com/watch?v=abc",
                                        "title": "Ruiz-Mateos: el hombre de la abeja", "published_at": int(time.time()) - 60,
                                        "views": 1200, "source": "youtube"}])
        self.assertEqual(planner.auto_match(self.storage), 1)
        updated = self.storage.plan_item(item["id"])
        self.assertTrue(updated["done"])
        self.assertEqual(updated["links"][0]["views"], 1200)
        self.assertIn("youtube", updated["platforms"])

    def test_agenda_and_horizon(self):
        today = dt.date.today()
        self.storage.save_plan_item(planner.clean_item({"day": today.isoformat(), "title": "Hoy", "kind": "grabar"}))
        self.storage.save_plan_item(planner.clean_item({"day": (today + dt.timedelta(days=1)).isoformat(), "title": "Mañana"}))
        self.storage.save_plan_item(planner.clean_item({"day": (today - dt.timedelta(days=2)).isoformat(), "title": "Atrasada"}))
        agenda = planner.agenda(self.storage, today)
        self.assertEqual([i["title"] for i in agenda["today"]], ["Hoy"])
        self.assertEqual([i["title"] for i in agenda["tomorrow"]], ["Mañana"])
        self.assertEqual([i["title"] for i in agenda["overdue"]], ["Atrasada"])
        horizon = planner.horizon(None, dt.date(2026, 10, 1))
        self.assertTrue(any(h["title"] == "Fiesta Nacional de España" and h["idea"] for h in horizon))

    def test_platform_detection(self):
        self.assertEqual(planner.platform_of("https://vm.tiktok.com/ZM123/"), "tiktok")
        self.assertEqual(planner.platform_of("https://www.instagram.com/reel/Dd3jGjtOUgl/"), "instagram")
        self.assertEqual(planner.platform_of("https://youtu.be/jNQXAC9IVRw"), "youtube")
        self.assertIsNone(planner.platform_of("https://example.com/video"))


class RecapTests(unittest.TestCase):
    def test_weekly_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine = demo_engine(Path(tmp))
            data = engine.recap(0)
            self.assertEqual(len(data["days"]), 7)
            self.assertEqual(dt.date.fromisoformat(data["week"]["start"]).weekday(), 0)
            self.assertIsNotNone(data["star"])
            self.assertFalse(stories.is_routine(data["star"]["title"], data["star"]["niche"]))
            self.assertLessEqual(sum(n["share"] for n in data["niches"]), 100.5)
            self.assertEqual(len(data["hours"]), 24)
            last = engine.recap(1)
            self.assertEqual(last["week"]["label"], "La semana pasada")
            self.assertTrue(any(d["top"] for d in last["days"]))

    def test_week_bounds(self):
        start, end = recap.week_bounds(1, dt.date(2026, 10, 6))
        self.assertEqual((start, end), (dt.date(2026, 9, 28), dt.date(2026, 10, 4)))


YOUTUBE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
 <title>Canal de prueba</title>
 <entry>
  <id>yt:video:abc123XYZ00</id>
  <yt:videoId>abc123XYZ00</yt:videoId>
  <yt:channelId>UCabcdefghijklmnopqrstuv</yt:channelId>
  <title>Ruiz-Mateos: el hombre de la abeja</title>
  <link rel="alternate" href="https://www.youtube.com/shorts/abc123XYZ00"/>
  <published>2026-10-06T17:30:00+00:00</published>
  <media:group>
   <media:title>Ruiz-Mateos: el hombre de la abeja</media:title>
   <media:thumbnail url="https://i2.ytimg.com/vi/abc123XYZ00/hqdefault.jpg" width="480" height="360"/>
   <media:community>
    <media:starRating count="812" average="5.00" min="1" max="5"/>
    <media:statistics views="12940"/>
   </media:community>
  </media:group>
 </entry>
</feed>"""


class ConnectionTests(unittest.TestCase):
    def test_youtube_feed(self):
        items = connections.parse_youtube_feed(YOUTUBE_FEED)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["vid"], "abc123XYZ00")
        self.assertEqual(item["views"], 12940)
        self.assertEqual(item["likes"], 812)
        self.assertEqual(item["url"], "https://www.youtube.com/shorts/abc123XYZ00")
        self.assertEqual(item["published_at"], int(dt.datetime(2026, 10, 6, 17, 30, tzinfo=dt.timezone.utc).timestamp()))
        self.assertEqual(connections.parse_youtube_feed("<html>no</html>"), [])

    def test_youtube_falls_back_to_channel_tabs(self):
        def page(renderers):
            data = {"contents": {"twoColumnBrowseResultsRenderer": {"tabs": [{"tabRenderer": {"content": {
                "richGridRenderer": {"contents": [{"richItemRenderer": {"content": r}} for r in renderers]}}}}]}}}
            return f"<script>var ytInitialData = {json.dumps(data)};</script>"

        videos = page([{"videoRenderer": {"videoId": "vidLargo001", "title": {"runs": [{"text": "Ruiz-Mateos, el ascenso"}]},
                                          "viewCountText": {"simpleText": "12.345 visualizaciones"},
                                          "publishedTimeText": {"simpleText": "hace 2 días"}}}])
        shorts = page([{"shortsLockupViewModel": {
            "onTap": {"innertubeCommand": {"reelWatchEndpoint": {"videoId": "vidCorto001"}}},
            "overlayMetadata": {"primaryText": {"content": "Vietnam en 60 segundos"}, "secondaryText": {"content": "1,2 M visualizaciones"}}}}])

        class Response:
            def __init__(self, status, text=""):
                self.status_code, self.text, self.ok = status, text, status < 400

        class Session:
            def get(self, url, params=None, timeout=None):
                if "feeds/videos.xml" in url:
                    return Response(404)
                if url.endswith("/videos"):
                    return Response(200, videos)
                if url.endswith("/shorts"):
                    return Response(200, shorts)
                if "vidCorto001" in url:
                    return Response(200, '<meta itemprop="datePublished" content="2026-10-05T18:00:00+02:00">')
                return Response(500)

        known = {"vidLargo001": 1790000000}
        items = {i["vid"]: i for i in connections.fetch_youtube("UCabcdefghijklmnopqrstuv", Session(), known)}
        self.assertEqual(items["vidLargo001"]["published_at"], 1790000000)
        self.assertEqual(items["vidLargo001"]["views"], 12345)
        short = items["vidCorto001"]
        self.assertEqual(short["url"], "https://www.youtube.com/shorts/vidCorto001")
        self.assertEqual(short["views"], 1200000)
        self.assertEqual(short["source"], "youtube")
        self.assertEqual(short["published_at"], int(dt.datetime(2026, 10, 5, 16, 0, tzinfo=dt.timezone.utc).timestamp()))

        with tempfile.TemporaryDirectory() as tmp:
            storage = Storage(Path(tmp))
            storage.upsert_published([dict(short, published_at=1), dict(items["vidLargo001"], source=connections.APPROX)])
            self.assertEqual(storage.published_dates("youtube"), {"vidCorto001": 1})

    def test_channel_input(self):
        self.assertEqual(connections.resolve_channel("UCabcdefghijklmnopqrstuv"), "UCabcdefghijklmnopqrstuv")
        self.assertEqual(connections.resolve_channel("https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv"), "UCabcdefghijklmnopqrstuv")
        self.assertEqual(connections.channel_page_url("@daviidromero"), "https://www.youtube.com/@daviidromero")
        self.assertEqual(connections.channel_page_url("daviidromero"), "https://www.youtube.com/@daviidromero")
        self.assertIsNone(connections.channel_page_url("https://example.com/canal"))

    def test_instagram_media(self):
        rows = [
            {"id": "1", "caption": "Los 500 de Cortés (1521)\n#historia", "media_type": "VIDEO", "media_product_type": "REELS",
             "permalink": "https://www.instagram.com/reel/DduBtjtMrxz/", "thumbnail_url": "https://cdn/x.jpg",
             "timestamp": "2026-09-25T15:47:19+0000", "like_count": 11124, "comments_count": 281},
            {"id": "2", "media_type": "STORY"},
        ]
        items = connections.parse_instagram_media(rows)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Los 500 de Cortés (1521)")
        self.assertEqual(items[0]["likes"], 11124)
        self.assertEqual(items[0]["published_at"], int(dt.datetime(2026, 9, 25, 15, 47, 19, tzinfo=dt.timezone.utc).timestamp()))
        self.assertEqual(connections._insight_value({"data": [{"name": "views", "total_value": {"value": 155942}}]}), 155942)
        self.assertEqual(connections._insight_value({"data": [{"name": "views", "values": [{"value": 77}]}]}), 77)


class _FakeBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeAnthropicModule:
    """Imita lo justo del SDK de Anthropic para probar ai.py sin red ni clave."""

    class AuthenticationError(Exception):
        pass

    class PermissionDeniedError(Exception):
        pass

    class RateLimitError(Exception):
        pass

    class BadRequestError(Exception):
        pass

    class APIStatusError(Exception):
        status_code = 500

    class APIConnectionError(Exception):
        pass

    def __init__(self, stop_reason="end_turn", payload=None):
        module = self
        self.calls = []

        class Messages:
            def create(self, **kwargs):
                module.calls.append(kwargs)
                text = json.dumps(payload if payload is not None else {"historias": [
                    {"clave": s["clave"], "titular": f"T {s['clave']}", "que_ha_pasado": "Pasó algo.",
                     "enfoque": "Enfoque concreto.", "gancho": "Gancho."}
                    for s in json.loads(kwargs["messages"][0]["content"].split("\n", 1)[1])["historias"]]})
                return types.SimpleNamespace(stop_reason=stop_reason, content=[_FakeBlock(text)])

        class Client:
            def __init__(self, **kwargs):
                module.client_kwargs = kwargs
                self.beta = types.SimpleNamespace(messages=Messages())

        self.Anthropic = Client


class AITests(unittest.TestCase):
    def setUp(self):
        self.original = ai.anthropic

    def tearDown(self):
        ai.anthropic = self.original

    def story(self, key="eleccionesgenerales", why="Sánchez y Feijóo chocan"):
        return {"key": key, "title": "Elecciones generales", "members": [{"title": "Feijóo"}], "why": {"title": why},
                "news": [{"title": why}], "niche": "politica", "scope": "espana", "phase_label": "Explosivo",
                "remaining_hours": 10, "summary": "", "related": [], "youtube": None, "context": None}

    def test_request_uses_current_model_fallbacks_and_schema(self):
        fake = _FakeAnthropicModule()
        ai.anthropic = fake
        cache = {}
        asked = ai.enrich("sk-ant-test", [self.story()], cache, "David")
        self.assertEqual(asked, 1)
        call = fake.calls[0]
        self.assertEqual(call["model"], "claude-opus-5-5")
        self.assertEqual(call["fallbacks"], "default")
        self.assertIn("server-side-fallback-2026-07-01", call["betas"])
        self.assertEqual(call["output_config"]["format"]["type"], "json_schema")
        self.assertNotIn("thinking", call)
        self.assertIn("David", call["system"])
        self.assertEqual(fake.client_kwargs["api_key"], "sk-ant-test")
        self.assertEqual(cache["eleccionesgenerales"]["data"]["enfoque"], "Enfoque concreto.")
        # La misma historia no se vuelve a pedir; si cambia su titular, sí.
        self.assertEqual(ai.enrich("sk-ant-test", [self.story()], cache), 0)
        self.assertEqual(ai.enrich("sk-ant-test", [self.story(why="Nuevo titular")], cache), 1)

    def test_refusal_is_reported(self):
        ai.anthropic = _FakeAnthropicModule(stop_reason="refusal")
        with self.assertRaises(ai.AIError):
            ai.request("sk-ant-test", [self.story()])

    def test_engine_publishes_ideas_without_mutating_old_state(self):
        ai.anthropic = _FakeAnthropicModule()
        with tempfile.TemporaryDirectory() as tmp:
            engine = demo_engine(Path(tmp))
            engine.settings.update({"ai_key": "sk-ant-test-key-123456"})
            before = engine.get_state()["stories"]
            key = engine.state["portada"]["keys"][0]
            result = engine.ai_for_story(key)
            self.assertEqual(result["ai"]["enfoque"], "Enfoque concreto.")
            self.assertNotIn("ai", next(s for s in before if s["key"] == key))
            after = next(s for s in engine.get_state()["stories"] if s["key"] == key)
            self.assertEqual(after["ai"]["gancho"], "Gancho.")
            self.assertTrue(engine.get_state()["ai"]["enabled"])

    def test_missing_sdk(self):
        ai.anthropic = None
        self.assertFalse(ai.available())
        with self.assertRaises(ai.AIError):
            ai.request("sk-ant-test", [self.story()])


class SettingsTests(unittest.TestCase):
    def test_secrets_are_never_exposed(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(Path(tmp) / "settings.json")
            settings.update({"instagram_token": "IGQVJ-secret-token-1234", "ai_key": "sk-ant-abcdefgh9999", "youtube_channel": "@canal"})
            public = settings.public()
            text = json.dumps(public)
            self.assertNotIn("secret", text)
            self.assertNotIn("sk-ant", text)
            self.assertTrue(public["instagram_token_set"])
            self.assertEqual(public["ai_key_hint"], "…9999")
            settings.update({"youtube_channel_id": "UCabcdefghijklmnopqrstuv"}, trusted=True)
            settings.update({"youtube_channel": "@otro"})
            self.assertEqual(settings.get()["youtube_channel_id"], "")
            reloaded = Settings(Path(tmp) / "settings.json")
            self.assertEqual(reloaded.get()["instagram_token"], "IGQVJ-secret-token-1234")


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.engine = demo_engine(root)
        cls.server = AppServer(cls.engine, cls.engine.settings, cls.engine.storage)
        cls.server.start()
        cls.base = cls.server.url.rstrip("/")
        html = urllib.request.urlopen(cls.base + "/").read().decode()
        cls.token = re.search(r'name="romero-token" content="([^"]+)"', html).group(1)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        cls.tmp.cleanup()

    def call(self, path, data=None):
        headers = {"X-Romero-Token": self.token, "Content-Type": "application/json"}
        req = urllib.request.Request(self.base + path, data=json.dumps(data).encode() if data is not None else None,
                                     headers=headers, method="POST" if data is not None else "GET")
        try:
            with urllib.request.urlopen(req) as response:
                return response.status, json.loads(response.read().decode())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read().decode() or "{}")

    def test_state_has_stories_and_agenda(self):
        status, state = self.call("/api/state")
        self.assertEqual(status, 200)
        self.assertTrue(state["stories"])
        self.assertEqual(len(state["portada"]["keys"]), 5)
        self.assertIn("today", state["agenda"])
        self.assertIn("horizon", state)
        self.assertEqual(state["app"]["name"], "Romero Xandre CRM")

    def test_plan_lifecycle(self):
        status, item = self.call("/api/plan", {"day": "2026-10-20", "title": "Trafalgar", "kind": "guion", "platforms": ["instagram"]})
        self.assertEqual(status, 200)
        status, month = self.call("/api/calendar?month=2026-10")
        day = next(d for d in month["days"] if d["date"] == "2026-10-20")
        self.assertIn("Trafalgar", [i["title"] for i in day["items"]])
        status, updated = self.call("/api/plan", {"id": item["id"], "done": True})
        self.assertTrue(updated["done"])
        status, error = self.call("/api/plan", {"day": "nope", "title": "x"})
        self.assertEqual(status, 400)
        self.assertIn("Fecha", error["error"])
        status, gone = self.call("/api/plan/delete", {"id": item["id"]})
        self.assertTrue(gone["ok"])

    def test_recap_agenda_and_preview(self):
        status, data = self.call("/api/recap?week=1")
        self.assertEqual(status, 200)
        self.assertEqual(len(data["days"]), 7)
        status, agenda = self.call("/api/agenda")
        self.assertIn("agenda", agenda)
        status, error = self.call("/api/link-preview", {"url": "file:///etc/passwd"})
        self.assertEqual(status, 400)
        status, preview = self.call("/api/link-preview", {"url": "https://www.tiktok.com/@a/video/1"})
        self.assertEqual(preview["platform"], "tiktok")

    def test_settings_hide_secrets(self):
        status, settings = self.call("/api/settings", {"instagram_token": "IGQVJ-very-secret-token"})
        self.assertTrue(settings["instagram_token_set"])
        self.assertNotIn("instagram_token", settings)
        status, settings = self.call("/api/settings", {"instagram_token": ""})
        self.assertFalse(settings["instagram_token_set"])

    def test_fonts_are_served(self):
        with urllib.request.urlopen(self.base + "/static/fonts/inter-var.woff2") as response:
            self.assertEqual(response.headers["Content-Type"], "font/woff2")


if __name__ == "__main__":
    unittest.main()
