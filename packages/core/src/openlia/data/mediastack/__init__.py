"""Thin Mediastack client. Wraps the public REST API at api.mediastack.com.

Mediastack publishes a REST API but no official Python SDK and no MCP server.
This module provides a minimal `MediastackClient` class so the connector
subsystem can drive it through the python_lib transport like any other SDK.
"""

from __future__ import annotations

from typing import Any

import httpx

_BASE_URL = "https://api.mediastack.com/v1"


class MediastackClient:
    """Tiny wrapper over the Mediastack REST API."""

    def __init__(self, *, api_key: str) -> None:
        self._api_key = api_key

    def search(
        self,
        *,
        keywords: str,
        since: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Search news articles by keyword. Returns the `data` array verbatim."""
        params: dict[str, Any] = {
            "access_key": self._api_key,
            "keywords": keywords,
            "limit": limit,
        }
        if since is not None:
            params["date"] = since
        response = httpx.get(f"{_BASE_URL}/news", params=params, timeout=30.0)
        response.raise_for_status()
        body = response.json()
        return list(body.get("data", []))


__all__ = ["MediastackClient"]
