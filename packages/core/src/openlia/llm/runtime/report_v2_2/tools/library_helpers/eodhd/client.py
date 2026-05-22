"""EODHD HTTP client for report_v2_2 helpers.

Bypasses the eodhd SDK entirely to avoid its sys.exit() calls on API errors
(observed in eodhd.APIs.BaseAPI._rest_get_method and apiclient._rest_get).
Uses requests directly with exponential backoff on 429s.
"""

from __future__ import annotations

import os
import time
from typing import Any

import requests

_BASE_URL = "https://eodhd.com/api"
_RETRY_DELAYS = (1, 2, 4)  # seconds; 3 attempts total


def get_api_key() -> str:
    key = os.environ.get("EODHD_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "EODHD_API_KEY env var not set. "
            "Set it in your .env or environment before calling EODHD helpers."
        )
    return key


def _get(endpoint: str, uri: str = "", querystring: str = "") -> Any:
    """GET ``/api/<endpoint>/<uri>?api_token=<key>&fmt=json<querystring>``.

    Retries up to 3 times with exponential backoff on HTTP 429.
    Raises RuntimeError on non-200 responses (never calls sys.exit).
    Returns the parsed JSON body (list or dict).
    """
    key = get_api_key()
    url = f"{_BASE_URL}/{endpoint}/{uri}".rstrip("/")
    params_str = f"api_token={key}&fmt=json{querystring}"

    for _attempt, delay in enumerate((*_RETRY_DELAYS, None)):
        try:
            resp = requests.get(f"{url}?{params_str}", timeout=30)
        except requests.RequestException as exc:
            raise RuntimeError(f"EODHD network error: {exc}") from exc

        if resp.status_code == 429:
            if delay is not None:
                time.sleep(delay)
                continue
            # Final attempt — fall through to post-loop raise
            break

        if resp.status_code != 200:
            body = ""
            try:
                body = resp.json().get("message", "")
            except Exception:
                pass
            raise RuntimeError(f"EODHD API error {resp.status_code} for {url}: {body}")

        try:
            return resp.json()
        except ValueError as exc:
            raise RuntimeError(f"EODHD invalid JSON from {url}: {exc}") from exc

    raise RuntimeError(
        f"EODHD rate-limit (429) persisted after {len(_RETRY_DELAYS)} retries: {url}"
    )
