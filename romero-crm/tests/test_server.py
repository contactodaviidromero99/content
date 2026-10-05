import json
import re
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from romero_crm.config import Settings
from romero_crm.demo import DemoData
from romero_crm.engine import Engine
from romero_crm.server import AppServer
from romero_crm.storage import Storage


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        (root / "cache").mkdir()
        settings = Settings(root / "settings.json")
        storage = Storage(root)
        cls.engine = Engine(settings, storage, DemoData().load)
        cls.engine.refresh(force=True)
        cls.server = AppServer(cls.engine, settings, storage)
        cls.server.start()
        cls.base = cls.server.url.rstrip("/")
        html = urllib.request.urlopen(cls.base + "/").read().decode()
        cls.token = re.search(r'name="romero-token" content="([^"]+)"', html).group(1)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        cls.tmp.cleanup()

    def request(self, path, data=None, headers=None):
        req = urllib.request.Request(self.base + path, data=json.dumps(data).encode() if data is not None else None,
                                     headers=headers or {}, method="POST" if data is not None else "GET")
        try:
            with urllib.request.urlopen(req) as response:
                return response.status, response.read().decode()
        except urllib.error.HTTPError as err:
            return err.code, err.read().decode()

    def test_state_has_topics(self):
        status, body = self.request("/api/state")
        self.assertEqual(status, 200)
        state = json.loads(body)
        self.assertTrue(state["topics"])
        self.assertTrue(state["app"]["demo"])

    def test_post_requires_token(self):
        status, _ = self.request("/api/settings", {"theme": "dark"})
        self.assertEqual(status, 403)
        status, body = self.request("/api/settings", {"theme": "dark"}, {"X-Romero-Token": self.token})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["theme"], "dark")

    def test_rejects_foreign_host(self):
        status, _ = self.request("/api/state", headers={"Host": "evil.example"})
        self.assertEqual(status, 403)

    def test_open_only_web_urls(self):
        status, body = self.request("/api/open", {"url": "file:///etc/passwd"}, {"X-Romero-Token": self.token})
        self.assertEqual(status, 400)

    def test_static_cannot_escape(self):
        status, _ = self.request("/static/../server.py")
        self.assertEqual(status, 404)
        status, _ = self.request("/static/js/app.js")
        self.assertEqual(status, 200)

    def test_topic_detail_and_history(self):
        state = json.loads(self.request("/api/state")[1])
        key = state["topics"][0]["key"]
        status, body = self.request(f"/api/topic?key={key}")
        self.assertEqual(status, 200)
        self.assertIn("news", json.loads(body))
        status, body = self.request("/api/history?days=7")
        self.assertEqual(len(json.loads(body)["days"]), 7)


if __name__ == "__main__":
    unittest.main()
