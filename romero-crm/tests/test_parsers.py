import json
import time
import unittest

from romero_crm import analysis
from romero_crm.demo import DemoData
from romero_crm.niches import classify, is_utility
from romero_crm.sources import efemerides, google_trends, news, tiktok, wikipedia, x_trends, youtube
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


class TikTokTests(unittest.TestCase):
    def test_next_data_hashtags_and_songs(self):
        demo = DemoData()
        raw = next(tiktok.find_record_lists(tiktok.extract_next_data(demo.tiktok_html()), tiktok._is_hashtag))
        tags = tiktok.parse_hashtags(raw)
        self.assertEqual(tags[0]["title"], "#halloween")
        self.assertEqual(tags[0]["niche_hint"], "ocio")
        self.assertTrue(any(t["is_new"] for t in tags))
        songs_raw = next(tiktok.find_record_lists(tiktok.extract_next_data(demo.tiktok_music_html()), tiktok._is_song))
        self.assertEqual(len(tiktok.parse_songs(songs_raw)), 6)

    def test_snake_case_api_records(self):
        records = [{"hashtag_name": "historia", "publish_cnt": 100, "video_views": 2000, "rank": 1, "rank_diff": 3,
                    "rank_diff_type": 2, "industry_info": {"value": "Education"}}]
        item = tiktok.parse_hashtags(records)[0]
        self.assertEqual(item["rank_change"], -3)
        self.assertEqual(item["niche_hint"], "educacion")


class WikipediaTests(unittest.TestCase):
    def test_filters_and_changes(self):
        payload = {"items": [{"articles": [
            {"project": "es.wikipedia", "article": "Especial:Buscar", "views_ceil": 9000, "rank": 1},
            {"project": "es.wikipedia", "article": "Batalla_de_Lepanto", "views_ceil": 2000, "rank": 2},
            {"project": "commons.wikimedia", "article": "Foo", "views_ceil": 1000, "rank": 3},
        ]}]}
        rows = wikipedia.parse_top_per_country(payload)
        self.assertEqual([r["article"] for r in rows], ["Batalla_de_Lepanto"])
        import datetime as dt
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

    def test_search_params(self):
        self.assertEqual(youtube.search_params(sort=3, upload=3, kind=1), "CAMSBAgDEAE=")


class EfemeridesTests(unittest.TestCase):
    def test_round_levels(self):
        self.assertEqual(efemerides.round_level(100), 4)
        self.assertEqual(efemerides.round_level(250), 3)
        self.assertEqual(efemerides.round_level(25), 2)
        self.assertEqual(efemerides.round_level(40), 1)
        self.assertEqual(efemerides.round_level(455), 0)


class AnalysisTests(unittest.TestCase):
    def test_demo_pipeline_merges_platforms(self):
        demo = DemoData()
        results = {s: demo.load(s) for s in ("google", "x", "tiktok", "wikipedia", "news")}
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

    def test_no_false_merge_on_generic_city(self):
        demo = DemoData()
        results = {"google": demo.load("google"), "x": x_trends_result(["Madrid"])}
        topics = analysis.build_topics(results, {}, time.time())
        madrid = next(t for t in topics if t["title"] == "Madrid")
        self.assertEqual(madrid["sources"], ["x"])


def x_trends_result(names):
    from romero_crm.sources.base import SourceResult
    cards = [(None, [(n, None) for n in names])]
    return SourceResult(source="x", ok=True, items=x_trends.build_items(cards))


if __name__ == "__main__":
    unittest.main()
