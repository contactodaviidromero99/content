from __future__ import annotations

import json
import mimetypes
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

WEB_DIR = (Path(__file__).parent / "web").resolve()
CSP = (
    "default-src 'self'; img-src 'self' https: data:; style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
)
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")


class AppServer:
    def __init__(self, engine, settings, storage, host: str = "127.0.0.1", port: int = 0):
        self.engine = engine
        self.settings = settings
        self.storage = storage
        self.token = secrets.token_urlsafe(24)
        try:
            self.httpd = ThreadingHTTPServer((host, port), self._handler())
        except OSError:
            self.httpd = ThreadingHTTPServer((host, 0), self._handler())
        self.httpd.daemon_threads = True

    @property
    def url(self) -> str:
        host, port = self.httpd.server_address[:2]
        return f"http://{host}:{port}/"

    def start(self) -> None:
        threading.Thread(target=self.httpd.serve_forever, name="romero-http", daemon=True).start()

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def _handler(self):
        app = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "RomeroCRM"

            def log_message(self, *args):
                pass

            def _host_ok(self) -> bool:
                host = (self.headers.get("Host") or "").split(":")[0].strip("[]").lower()
                return host in ("127.0.0.1", "localhost", "::1")

            def _send(self, status: int, body: bytes, content_type: str, extra: dict = None) -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                for name, value in (extra or {}).items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(body)

            def _json(self, data, status: int = 200) -> None:
                body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                self._send(status, body, "application/json; charset=utf-8")

            def _body(self) -> dict:
                length = int(self.headers.get("Content-Length") or 0)
                if length <= 0 or length > 1_000_000:
                    return {}
                try:
                    data = json.loads(self.rfile.read(length).decode("utf-8"))
                except ValueError:
                    return {}
                return data if isinstance(data, dict) else {}

            def do_GET(self):
                if not self._host_ok():
                    return self._send(403, b"forbidden", "text/plain")
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)
                path = parsed.path
                if path in ("/", "/index.html"):
                    html = (WEB_DIR / "index.html").read_text(encoding="utf-8").replace("{{TOKEN}}", app.token)
                    return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8", {"Content-Security-Policy": CSP})
                if path.startswith("/static/"):
                    return self._static(path[len("/static/"):])
                if path == "/api/state":
                    return self._json(app.engine.get_state())
                if path == "/api/status":
                    return self._json(app.engine.status())
                if path == "/api/history":
                    try:
                        days = int((query.get("days") or ["7"])[0])
                    except ValueError:
                        days = 7
                    return self._json(app.engine.history(days))
                if path == "/api/topic":
                    topic_key = (query.get("key") or [""])[0]
                    return self._json(app.engine.topic_detail(topic_key))
                if path == "/api/settings":
                    return self._json(dict(app.settings.get(), data_dir=str(app.storage.root)))
                return self._send(404, b"not found", "text/plain")

            def do_POST(self):
                if not self._host_ok() or self.headers.get("X-Romero-Token") != app.token:
                    return self._send(403, b"forbidden", "text/plain")
                path = urlparse(self.path).path
                body = self._body()
                if path == "/api/refresh":
                    return self._json({"started": app.engine.request_refresh()})
                if path == "/api/settings":
                    before = app.settings.get()
                    after = app.settings.update(body)
                    if before["sources"] != after["sources"] or before["youtube_topics"] != after["youtube_topics"]:
                        app.engine.request_refresh()
                    elif before["refresh_minutes"] != after["refresh_minutes"]:
                        app.engine.reschedule()
                    return self._json(dict(after, data_dir=str(app.storage.root)))
                if path == "/api/open":
                    url = str(body.get("url") or "")
                    if not url.startswith(("https://", "http://")):
                        return self._json({"ok": False}, 400)
                    webbrowser.open(url)
                    return self._json({"ok": True})
                if path == "/api/clear-history":
                    app.storage.clear_history()
                    app.engine.results.clear()
                    app.engine.request_refresh()
                    return self._json({"ok": True})
                return self._send(404, b"not found", "text/plain")

            def _static(self, relative: str):
                target = (WEB_DIR / relative).resolve()
                if WEB_DIR not in target.parents or not target.is_file():
                    return self._send(404, b"not found", "text/plain")
                content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
                if content_type.startswith("text/") or content_type in ("application/javascript", "image/svg+xml"):
                    content_type += "; charset=utf-8"
                return self._send(200, target.read_bytes(), content_type)

        return Handler
