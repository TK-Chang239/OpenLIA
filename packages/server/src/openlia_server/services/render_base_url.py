from __future__ import annotations

import os
import socket
from collections.abc import Callable
from typing import Final
from urllib.parse import urlparse

_DEFAULT_VITE_URL: Final[str] = "http://127.0.0.1:5173"


class RenderBaseUrlResolver:
    """Resolve the base URL Playwright should load to render a report print page.

    Resolution order (first match wins, result is cached):
      1. OPENLIA_REPORT_RENDER_BASE_URL env var
      2. server's own URL, if `is_spa_served_locally()` returns True
         (which means the FastAPI process is mounting frontend/dist itself
         per OPENLIA_FRONTEND_DIST, so /reports/:id/render resolves)
      3. Vite dev server at http://127.0.0.1:5173, if `probe` returns True
      4. None — caller surfaces a 503 with a remediation hint
    """

    def __init__(
        self,
        *,
        server_url: str,
        is_spa_served_locally: Callable[[], bool],
        probe: Callable[[str], bool],
        vite_url: str = _DEFAULT_VITE_URL,
    ) -> None:
        self._server_url = server_url.rstrip("/")
        self._is_spa_served_locally = is_spa_served_locally
        self._probe = probe
        self._vite_url = vite_url.rstrip("/")
        self._cached: str | None = None

    def resolve(self) -> str | None:
        if self._cached:
            return self._cached
        env = os.environ.get("OPENLIA_REPORT_RENDER_BASE_URL")
        if env:
            self._cached = env.rstrip("/")
            return self._cached
        if self._is_spa_served_locally():
            self._cached = self._server_url
            return self._cached
        if self._probe(self._vite_url):
            self._cached = self._vite_url
            return self._cached
        return None

    def invalidate(self) -> None:
        self._cached = None


def default_probe(url: str, *, timeout_sec: float = 0.2) -> bool:
    """TCP-connect probe to test whether a dev server is up at `url`.

    Returns True only on a successful socket connect; any OSError (including
    refused, unreachable, timed out) maps to False.
    """
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True
    except OSError:
        return False
