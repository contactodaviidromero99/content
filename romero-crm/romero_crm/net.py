from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import APP_VERSION

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
APP_UA = f"RomeroCRM/{APP_VERSION} (herramienta personal de tendencias; python-requests)"
TIMEOUT = 20


class SourceError(Exception):
    pass


def make_session(user_agent: str = BROWSER_UA, retry_rate_limit: bool = True) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=2,
        connect=2,
        read=1,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504) if retry_rate_limit else (500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "POST"]),
        respect_retry_after_header=False,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": user_agent,
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    })
    return session


def check(response: requests.Response, what: str) -> requests.Response:
    if response.status_code == 429:
        raise SourceError(f"{what} ha limitado las peticiones (429). Se reintentará más tarde.")
    if response.status_code >= 400:
        raise SourceError(f"{what} respondió con error {response.status_code}.")
    return response
