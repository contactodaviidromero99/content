import datetime as dt
import json
import time
import unittest

from romero_crm import analysis, explain
from romero_crm.demo import DemoData
from romero_crm.niches import classify, is_utility
from romero_crm.sources import efemerides, google_trends, news, wikipedia, x_trends, youtube
from romero_crm.text import casing_map, key, parse_ago_seconds, parse_compact_number, parse_duration, recase


class TextTests(unittest.TestCase):
    def test_compact_numbers(self):
        cases = {
            "200K+": 200000, "2,000+": 2000, "1.2M views": 1200000, "123,456 views": 123456,
            "12,5 mil": 12500, "1,2 M": 1200000, "Under 10K": 10000, "5 months ago": 5, "No views": None,
        }
        for raw, expected in cases.items():
            self.assertEqual(parse_compact_number(raw), expected, raw)

    def test_durations_and_ago(self):
        self.assertEqual(parse_duration("1:02:03"), 3723)
        self.assertEqual(parse_duration("0:59"), 59)
        self.assertEqual(parse_ago_seconds("3 hours ago"), 3 * 3600)
        self.assertEqual(parse_ago_seconds("hace 2 días"), 2 * 86400)
        self.assertEqual(parse_ago_seconds("Streamed 1 week ago"), 7 * 86400)

    def test_keys_join_hashtags_and_phrases(self):
        self.assertEqual(key("#RealMadridVillarreal"), key("real madrid - villarreal"))
        self.assertEqual(key("Mbappé"), "mbappe")

    def test_recase_uses_headline_casing(self):
        mapping = casing_map(["La AEMET activa avisos", "Qué se premia en el Nobel de Medicina"])
        self.assertEqual(recase("aviso aemet", mapping), "Aviso AEMET")
        self.assertEqual(recase("premio nobel de medicina", mapping), "Premio Nobel de Medicina")
        self.assertEqual(recase("whatsapp caído", mapping), "WhatsApp caído")
        self.assertEqual(recase("atlético - betis", {}), "Atlético - Betis")

    def test_recase_recovers_accents_from_headlines(self):
        mapping = casing_map(["Pedro Sánchez convoca elecciones", "El PP de Feijóo sube", "Muere Ángel Arroyo", "Sánchez disuelve las Cortes"])
        self.assertEqual(recase("pedro sanchez", mapping), "Pedro Sánchez")
        self.assertEqual(recase("feijoo", mapping), "Feijóo")
        self.assertEqual(recase("angel arroyo", mapping), "Ángel Arroyo")
        self.assertEqual(recase("psoe vox", mapping), "PSOE VOX")


class NicheTests(unittest.TestCase):
    def test_keywords(self):
        self.assertEqual(classify("batalla de lepanto", base="otros")[0], "historia")
        self.assertEqual(classify("rosalía", base="entretenimiento", related=["rosalía concierto"])[0], "musica")
        self.assertEqual(classify("zelenski", base="politica", related=["ucrania rusia"])[0], "internacional")
        self.assertEqual(classify("Kylian Mbappé", description="futbolista francés")[0], "deportes")

    def test_utility(self):
        self.assertTrue(is_utility("bonoloto"))
        self.assertTrue(is_utility("resultados euromillones"))
        self.assertFalse(is_utility("batalla de lepanto"))

    def test_navigational_searches_are_utility(self):
        for title in ("Elpais", "El Mundo", "Abc", "Cadena Ser", "#FelizLunes"):
            self.assertTrue(is_utility(title), title)
        for title in ("Elecciones", "Últimas noticias de Gaza", "Real Madrid"):
            self.assertFalse(is_utility(title), title)


class GoogleTests(unittest.TestCase):
    def test_batch_roundtrip(self):
        demo = DemoData()
        payload = google_trends.parse_batch_response(demo.google_payload(
            [("prueba tendencia", 50000, 300, 2.0, None, [17], ["prueba"], "rising", [("Titular", "Medio")])]), "i0OFE")
        items = google_trends.parse_trending(payload)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["volume"], 50000)
        self.assertEqual(item["categories"], ["deportes"])
        self.assertTrue(item["active"])
        self.assertEqual(item["news"][0]["source"], "Medio")

    def test_chunked_response_and_short_rows(self):
        inner = json.dumps([None, [["solo keyword"]]])
        text = ")]}'\n\n123\n" + json.dumps([["wrb.fr", "i0OFE", inner, None, None, None, "generic"]]) + "\n25\n[[\"di\",10]]"
        items = google_trends.parse_trending(google_trends.parse_batch_response(text, "i0OFE"))
        self.assertEqual(items[0]["title"], "Solo Keyword")
        self.assertEqual(items[0]["volume"], 0)

    def test_rss(self):
        xml = """<rss xmlns:ht="https://trends.google.com/trending/rss"><channel><item><title>dana valencia</title>
        <ht:approx_traffic>20K+</ht:approx_traffic><pubDate>Mon, 05 Oct 2026 08:00:00 +0200</pubDate>
        <ht:picture>https://img/1.jpg</ht:picture><ht:picture_source>X</ht:picture_source>
        <ht:news_item><ht:news_item_title>Aviso &amp; alerta</ht:news_item_title><ht:news_item_url>https://n/1</ht:news_item_url>
        <ht:news_item_source>Diario</ht:news_item_source></ht:news_item></item></channel></rss>"""
        items = google_trends.parse_rss(xml)
        self.assertEqual(items[0]["volume"], 20000)
        self.assertEqual(items[0]["picture"], "https://img/1.jpg")
        self.assertEqual(items[0]["news"][0]["title"], "Aviso & alerta")


class XTests(unittest.TestCase):
    def test_trends24(self):
        demo = DemoData()
        items = x_trends.build_items(x_trends.parse_trends24(demo.trends24_html()), now=demo.now)
        self.assertGreater(len(items), 20)
        first = items[0]
        self.assertEqual(first["rank"], 1)
        self.assertTrue(first["url"].startswith("https://x.com/search"))
        mbappe = next(i for i in items if i["title"] == "Mbappé")
        self.assertGreater(mbappe["hours_in_trends"], 10)

    def test_getdaytrends(self):
        html = """<table><tr><th><a href="/spain/trend/%23Foo/">#Foo</a></th><td>25.3K tweets</td></tr>
        <tr><th><a href="/spain/trend/Bar/">Bar</a></th><td>Under 10K tweets</td></tr></table>"""
        cards = x_trends.parse_getdaytrends(html)
        items = x_trends.build_items(cards)
        self.assertEqual([i["title"] for i in items], ["#Foo", "Bar"])
        self.assertEqual(items[0]["volume"], 25300)

    def test_getdaytrends_history_from_sparklines(self):
        def row(pos, name, points):
            grid = "".join(f'<polyline class="grid-h" points="0,{y} 140,{y}"></polyline>' for y in range(0, 60, 10))
            return (f'<tr><th class="pos">{pos}</th><td class="main"><a href="/spain/trend/{name}/">{name}</a></td>'
                    f'<td class="graph"><svg viewbox="0 -2 140 54"><g class="grid-h">{grid}</g>'
                    f'<polyline points=""></polyline><polyline points="{points}"></polyline></svg></td></tr>')

        html = '<table class="trends">' + "".join([
            row(1, "Nuevo", "120,50 140,0 "),
            row(2, "Veterano", "0,9 20,7 40,5 60,4 80,3 100,2 120,1 140,1 "),
            row(3, "Bajando", "100,0 120,0 140,2 "),
        ]) + "</table>"
        items = {i["title"]: i for i in x_trends.build_items(x_trends.parse_getdaytrends(html, now=1_000_000), now=1_000_000)}
        self.assertTrue(items["Nuevo"]["is_new"])
        self.assertEqual(items["Nuevo"]["hours_in_trends"], 1)
        self.assertEqual(items["Veterano"]["hours_in_trends"], 8)
        self.assertEqual(items["Veterano"]["best_rank"], 2)
        self.assertEqual(items["Veterano"]["first_seen"], 1_000_000 - 7 * 3600)
        self.assertEqual(items["Bajando"]["rank_change"], -2)
        self.assertEqual(len(items["Veterano"]["series"]), 8)


class WikipediaTests(unittest.TestCase):
    def test_filters_and_changes(self):
        payload = {"items": [{"articles": [
            {"project": "es.wikipedia", "article": "Especial:Buscar", "views_ceil": 9000, "rank": 1},
            {"project": "es.wikipedia", "article": "Batalla_de_Lepanto", "views_ceil": 2000, "rank": 2},
            {"project": "commons.wikimedia", "article": "Foo", "views_ceil": 1000, "rank": 3},
        ]}]}
        rows = wikipedia.parse_top_per_country(payload)
        self.assertEqual([r["article"] for r in rows], ["Batalla_de_Lepanto"])
        noisy = {"items": [{"articles": [
            {"project": "fr.wikipedia", "article": "Cookie_(informatique)", "views_ceil": 198700, "rank": 1},
            {"project": "en.wikipedia", "article": "HTTP_cookie", "views_ceil": 5000, "rank": 2},
            {"project": "ca.wikipedia", "article": "Barcelona", "views_ceil": 3000, "rank": 3},
        ]}]}
        self.assertEqual([r["article"] for r in wikipedia.parse_top_per_country(noisy)], ["Barcelona"])
        prev = [{"project": "es.wikipedia", "article": "Batalla_de_Lepanto", "views": 1000, "rank": 9}]
        items = wikipedia.build_items([(dt.date(2026, 10, 4), rows), (dt.date(2026, 10, 3), prev)], {})
        self.assertEqual(items[0]["title"], "Batalla de Lepanto")
        self.assertAlmostEqual(items[0]["change_pct"], 100.0)


class NewsTests(unittest.TestCase):
    def test_rss_strips_source(self):
        demo = DemoData()
        items = news.parse_rss(demo.news_rss("espana"), "espana")
        self.assertTrue(items)
        self.assertFalse(items[0]["title"].endswith("(demo)"))
        self.assertGreaterEqual(items[0]["coverage"], 1)


class YouTubeTests(unittest.TestCase):
    def test_both_renderers(self):
        demo = DemoData()
        videos = youtube.parse_search(demo.youtube_payload([
            ("Vídeo A", "Canal A", 120000, "2 days ago", "10:00"),
            ("Vídeo B", "Canal B", 45000, "3 hours ago", "0:58"),
        ]))
        self.assertEqual([v["title"] for v in videos], ["Vídeo A", "Vídeo B"])
        self.assertEqual(videos[0]["views"], 120000)
        self.assertEqual(videos[1]["views"], 45000)
        self.assertEqual(videos[1]["duration"], 58)
        summary = youtube.summarize("q", videos)
        self.assertEqual(summary["level"], "hueco")

    def test_shorts_lockup(self):
        data = {"x": [{"shortsLockupViewModel": {"onTap": {"innertubeCommand": {"reelWatchEndpoint": {"videoId": "abc"}}},
                                                  "overlayMetadata": {"primaryText": {"content": "Short"}, "secondaryText": {"content": "1.5M views"}}}}]}
        video = youtube.parse_search(data)[0]
        self.assertTrue(video["is_short"])
        self.assertEqual(video["views"], 1500000)

    def test_only_videos_about_the_topic_count(self):
        self.assertTrue(youtube.is_relevant("Ángel Arroyo, el ciclista que pudo ganar el Tour", "Ángel Arroyo"))
        self.assertFalse(youtube.is_relevant("Mi rutina de mañana | Ángel", "Ángel Arroyo"))
        self.assertFalse(youtube.is_relevant("Arroyo marca el gol de la victoria", "Ángel Arroyo"))
        self.assertTrue(youtube.is_relevant("Lepanto: el día que cambió el Mediterráneo", "Batalla de Lepanto"))
        self.assertFalse(youtube.is_relevant("Batalla de gallos: la gran final", "Batalla de Lepanto"))
        self.assertTrue(youtube.is_relevant("Caída mundial de WhatsApp explicada", "WhatsApp caído"))
        self.assertFalse(youtube.is_relevant("Electricidad gratis en casa", "Elecciones"))
        found = [{"title": "Ángel Arroyo vlog", "views": 23}, {"title": "Mi gato", "views": 14},
                 {"title": "Ángel Arroyo: adiós a un ciclista", "views": 50000}]
        summary = youtube.summarize("Ángel Arroyo", found, "Ángel Arroyo ciclista")
        self.assertEqual(summary["count"], 2)
        self.assertIn("ciclista", summary["search_url"])

    def test_search_params(self):
        self.assertEqual(youtube.search_params(sort=3, upload=3, kind=1), "CAMSBAgDEAE=")


class EfemeridesTests(unittest.TestCase):
    def test_time_budget_leaves_the_rest_for_later(self):
        import tempfile
        from pathlib import Path

        calls = []

        def fake_fetch_day(session, month, day, cache_dir):
            calls.append((month, day))
            return {"events": [{"year": 1926, "text": "Algo pasó en España.", "pages": []}]}

        original = efemerides.fetch_day
        efemerides.fetch_day = fake_fetch_day
        try:
            with tempfile.TemporaryDirectory() as tmp:
                result = efemerides.fetch(Path(tmp), days=10, today=dt.date(2026, 10, 5), budget_s=0)
        finally:
            efemerides.fetch_day = original
        self.assertTrue(result.ok)
        self.assertTrue(result.meta["partial"])
        self.assertEqual(calls, [(10, 5)])
        self.assertEqual(result.items[0]["items"][0]["years_ago"], 100)

    def test_round_levels(self):
        self.assertEqual(efemerides.round_level(100), 4)
        self.assertEqual(efemerides.round_level(250), 3)
        self.assertEqual(efemerides.round_level(25), 2)
        self.assertEqual(efemerides.round_level(40), 1)
        self.assertEqual(efemerides.round_level(455), 0)


class AnalysisTests(unittest.TestCase):
    def test_demo_pipeline_merges_platforms(self):
        demo = DemoData()
        results = {s: demo.load(s) for s in ("google", "x", "wikipedia", "news")}
        analysis.recase_google(results)
        topics = analysis.build_topics(results, {}, demo.now)
        lepanto = next(t for t in topics if t["key"] == "batalladelepanto")
        self.assertEqual(lepanto["niche"], "historia")
        self.assertGreaterEqual(len(lepanto["sources"]), 4)
        whatsapp = next(t for t in topics if t["key"] == "whatsappcaido")
        self.assertEqual(whatsapp["title"], "WhatsApp caído")
        self.assertIn(whatsapp["phase"], ("explosivo", "subiendo"))
        for topic in topics:
            self.assertTrue(0 <= topic["heat"] <= 100)
            self.assertTrue(0 <= topic["potential"] <= 100)

    def test_distinct_google_trends_never_merge_through_related_queries(self):
        demo = DemoData()
        payload = google_trends.parse_batch_response(demo.google_payload([
            ("elecciones", 200000, 1000, 5.0, None, [14], ["elecciones brasil", "pedro sanchez"], "rising", []),
            ("elecciones brasil", 50000, 1000, 8.0, None, [14], ["lula"], "rising", []),
        ]), "i0OFE")
        from romero_crm.sources.base import SourceResult
        results = {"google": SourceResult(source="google", ok=True, items=google_trends.parse_trending(payload))}
        topics = analysis.build_topics(results, {}, time.time())
        self.assertEqual(sorted(t["key"] for t in topics), ["elecciones", "eleccionesbrasil"])

    def test_own_volume_history_drives_phase_momentum_and_curve(self):
        demo = DemoData()
        now = demo.now
        payload = google_trends.parse_batch_response(demo.google_payload([
            ("despegue", 20000, 1000, 5.0, None, [17], [], "rising", []),
            ("estancado", 50000, 1000, 10.0, None, [4], [], "peak", []),
        ]), "i0OFE")
        items = google_trends.parse_trending(payload)
        started = {i["id"]: i["started_at"] for i in items}
        snapshots = [{"id": "despegue", "started": started["despegue"], "ts": int(now - h * 3600), "volume": v}
                     for h, v in ((4.5, 2000), (3, 5000), (1.5, 10000), (0.5, 20000))]
        snapshots += [{"id": "estancado", "started": started["estancado"], "ts": int(now - h * 3600), "volume": 50000}
                      for h in (6, 4, 2, 0.2)]
        analysis.attach_volume_history(items, snapshots, now)
        by_id = {i["id"]: i for i in items}
        self.assertEqual(by_id["despegue"]["volume_trend"]["recent_steps"], 2)
        self.assertEqual(by_id["despegue"]["volume_series"][-1], 20000)
        self.assertEqual(len(by_id["despegue"]["volume_series"]), 5)
        self.assertGreaterEqual(by_id["estancado"]["volume_trend"]["stalled_hours"], 6)

        from romero_crm.sources.base import SourceResult
        topics = {t["key"]: t for t in analysis.build_topics({"google": SourceResult(source="google", ok=True, items=items)}, {}, now)}
        self.assertEqual(topics["despegue"]["phase"], "explosivo")
        self.assertIn("de 5 mil+ a 20 mil+", topics["despegue"]["phase_reason"])
        self.assertEqual(topics["despegue"]["series_kind"], "google_volume")
        self.assertEqual(topics["estancado"]["phase"], "pico")
        self.assertIn("estable en 50 mil+", topics["estancado"]["phase_reason"])
        self.assertLessEqual(topics["estancado"]["heat_parts"]["impulso"], 0.4)

    def test_loose_x_trends_link_to_their_story(self):
        from romero_crm.sources.base import SourceResult
        demo = DemoData()
        payload = google_trends.parse_batch_response(demo.google_payload([
            ("elecciones", 200000, 1000, 5.0, None, [14], ["elecciones generales", "29 de noviembre"], "rising", []),
        ]), "i0OFE")
        headlines = [
            "El PSOE celebra que las elecciones del 29 de noviembre llegan con ventaja",
            "Sánchez disuelve las Cortes y convoca elecciones",
            "El PSOE prepara la campaña de las elecciones",
        ]
        results = {
            "google": SourceResult(source="google", ok=True, items=google_trends.parse_trending(payload)),
            "x": x_trends_result(["29-N", "PSOE", "Cortés", "Esperan"]),
            "news": SourceResult(source="news", ok=True, items=[
                {"title": h, "url": f"https://example.com/{i}", "source": "Demo", "section": "espana"} for i, h in enumerate(headlines)
            ]),
        }
        topics = {t["title"]: t for t in analysis.build_topics(results, {}, time.time())}
        self.assertEqual(topics["29-N"]["story"]["key"], "elecciones")
        self.assertEqual(topics["29-N"]["niche"], "politica")
        self.assertEqual(topics["PSOE"]["story"]["key"], "elecciones")
        self.assertNotIn("story", topics["Cortés"])
        self.assertNotIn("story", topics["Esperan"])
        self.assertEqual({a["title"] for a in topics["Elecciones"]["angles"]}, {"29-N", "PSOE"})
        self.assertTrue(all("_headlines" not in t for t in topics.values()))
        self.assertLess(topics["Esperan"]["heat"], topics["29-N"]["heat"])

    def test_story_link_prefers_the_most_specific_story(self):
        from romero_crm.sources.base import SourceResult
        demo = DemoData()
        payload = google_trends.parse_batch_response(demo.google_payload([
            ("elecciones", 200000, 1000, 5.0, None, [14],
             ["elecciones generales", "lula da silva"] + [f"elecciones consulta {i}" for i in range(28)], "rising", []),
            ("elecciones brasil", 50000, 1000, 8.0, None, [14], ["lula", "flavio bolsonaro"], "rising", []),
        ]), "i0OFE")
        headlines = [
            "Elecciones en Brasil: Flávio Bolsonaro y Lula da Silva van a una segunda vuelta",
            "Sánchez convoca elecciones generales",
            "Las encuestas ante las elecciones del 29 de noviembre",
            "Feijóo arranca la precampaña de las elecciones",
        ]
        results = {
            "google": SourceResult(source="google", ok=True, items=google_trends.parse_trending(payload)),
            "x": x_trends_result(["Silva"]),
            "news": SourceResult(source="news", ok=True, items=[
                {"title": h, "url": f"https://example.com/{i}", "source": "Demo", "section": "portada"} for i, h in enumerate(headlines)
            ]),
        }
        topics = {t["title"]: t for t in analysis.build_topics(results, {}, time.time())}
        self.assertEqual(topics["Silva"]["story"]["key"], "eleccionesbrasil")

    def test_no_false_merge_on_generic_city(self):
        demo = DemoData()
        results = {"google": demo.load("google"), "x": x_trends_result(["Madrid"])}
        topics = analysis.build_topics(results, {}, time.time())
        madrid = next(t for t in topics if t["title"] == "Madrid")
        self.assertEqual(madrid["sources"], ["x"])

    def test_duplicate_headlines_keep_their_coverage(self):
        merged = analysis.dedupe_news([
            {"title": "Lepanto, 455 años después", "source": "Diario A", "from_trend": True},
            {"title": "Lepanto, 455 años después", "source": "Diario A", "url": "https://a.example/l", "coverage": 5},
        ])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["coverage"], 5)
        self.assertTrue(merged[0]["from_trend"])
        self.assertEqual(merged[0]["url"], "https://a.example/l")
        demo = DemoData()
        results = {name: demo.load(name) for name in ("google", "x", "wikipedia", "news")}
        topics = analysis.build_topics(results, {}, time.time())
        lepanto = next(t for t in topics if t["key"] == "batalladelepanto")
        self.assertGreaterEqual(lepanto["news"]["outlets"], 2)


class ExplainTests(unittest.TestCase):
    def test_clean_headline_removes_live_blog_noise(self):
        self.assertEqual(
            explain.clean_headline("Pedro Sánchez convoca elecciones anticipadas el 29 de noviembre, en directo: última hora del adelanto electoral"),
            "Pedro Sánchez convoca elecciones anticipadas el 29 de noviembre")
        self.assertEqual(
            explain.clean_headline("Adelanto electoral de Sánchez, en directo | Sánchez disuelve las Cortes y convoca elecciones generales para el 29 de noviembre"),
            "Sánchez disuelve las Cortes y convoca elecciones generales para el 29 de noviembre")
        self.assertEqual(explain.clean_headline("ÚLTIMA HORA: Muere Ángel Arroyo, ciclista"), "Muere Ángel Arroyo, ciclista")

    def test_same_entity(self):
        self.assertTrue(explain.same_entity("Feijóo", "Alberto Núñez Feijóo"))
        self.assertTrue(explain.same_entity("Moncloa", "Palacio de la Moncloa"))
        self.assertTrue(explain.same_entity("PSOE", "Partido Socialista Obrero Español"))
        self.assertTrue(explain.same_entity("Frente Amplio", "Frente Amplio (Uruguay)"))
        self.assertFalse(explain.same_entity("Elecciones", "Elección"))
        self.assertFalse(explain.same_entity("Votar", "Voto"))
        self.assertFalse(explain.same_entity("WhatsApp caído", "WhatsApp"))

    def test_description_must_fit_the_topic(self):
        battery = {"niche": "tecnologia", "niches": ["tecnologia"]}
        self.assertFalse(explain.description_fits(battery, "instrumento musical de percusión"))
        self.assertFalse(explain.description_fits(battery, "página de desambiguación de Wikimedia"))
        rider = {"niche": "deportes", "niches": ["deportes"]}
        self.assertTrue(explain.description_fits(rider, "ciclista español"))
        town = {"niche": "politica", "niches": ["politica"]}
        self.assertTrue(explain.description_fits(town, "municipio de la provincia de Alicante"))

    def test_single_words_need_proper_noun_evidence(self):
        battery = {"title": "Batería", "news": {"items": [{"title": "Cómo cuidar la batería del móvil"}]}}
        leader = {"title": "Feijóo", "news": {"items": [{"title": "El PP de Feijóo sube en las encuestas"}]}}
        self.assertFalse(explain.looks_proper(battery))
        self.assertTrue(explain.looks_proper(leader))
        self.assertTrue(explain.looks_proper({"title": "Frente Amplio", "news": {"items": []}}))

    def test_context_word_for_youtube(self):
        self.assertEqual(explain.context_word("ciclista español"), "ciclista")
        self.assertEqual(explain.context_word("película de 2026 dirigida por Los Javis"), "película")
        self.assertIsNone(explain.context_word("página de desambiguación"))

    def test_why_uses_the_most_relevant_headline(self):
        now = time.time()
        topic = {
            "title": "Feijóo", "niche": "politica", "niches": ["politica"], "google": {"volume": 20000}, "x": None, "wikipedia": None,
            "news": {"count": 2, "outlets": 2, "items": [
                {"title": "El Ibex 35 abre en positivo", "source": "Expansión", "published": now - 600, "coverage": 8},
                {"title": "Feijóo presenta al PP como la alternativa ante el adelanto electoral", "source": "El País",
                 "published": now - 3600, "coverage": 3},
            ]},
        }
        explain.explain(topic, now)
        self.assertEqual(topic["why"]["source"], "El País")
        self.assertIn("Feijóo", topic["why"]["title"])
        self.assertEqual(topic["summary"], "20 mil+ búsquedas en Google · lo cuentan 2 medios")

    def test_unrelated_headlines_give_no_why(self):
        topic = {"title": "Cortés", "niche": "otros", "news": {"count": 1, "outlets": 1, "items": [
            {"title": "Sánchez disuelve las Cortes", "source": "ABC", "published": time.time(), "coverage": 2}]}}
        explain.explain(topic)
        self.assertIsNone(topic["why"])

    def test_wikipedia_lookup_follows_redirects(self):
        class FakeResponse:
            status_code = 200

            def json(self):
                return {"query": {
                    "redirects": [{"from": "Feijóo", "to": "Alberto Núñez Feijóo"}],
                    "pages": [
                        {"title": "Alberto Núñez Feijóo", "description": "político español"},
                        {"title": "Frente Amplio", "description": "página de desambiguación", "pageprops": {"disambiguation": ""}},
                        {"title": "Inexistente", "missing": True},
                    ]}}

        class FakeSession:
            def get(self, url, **kwargs):
                return FakeResponse()

        found = wikipedia.lookup_titles(FakeSession(), ["Feijóo", "Frente Amplio", "Inexistente"])
        self.assertEqual(found["Feijóo"]["page"], "Alberto Núñez Feijóo")
        self.assertEqual(found["Feijóo"]["description"], "político español")
        self.assertTrue(found["Frente Amplio"]["disambiguation"])
        self.assertTrue(found["Inexistente"]["missing"])


def x_trends_result(names):
    from romero_crm.sources.base import SourceResult
    cards = [(None, [(n, None) for n in names])]
    return SourceResult(source="x", ok=True, items=x_trends.build_items(cards))


if __name__ == "__main__":
    unittest.main()
