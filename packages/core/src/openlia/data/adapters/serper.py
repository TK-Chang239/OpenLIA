"""Serper adapter — search provider (google.serper.dev).

Mirrors the Serper MCP server (github.com/marcopesani/mcp-server-serper) on top
of the Serper REST API. Serper exposes Google's verticals as JSON endpoints.

Capabilities (POST + JSON body, all routed off `base_url`):
    web_search     /search        organic + knowledge graph + people-also-ask
    news_search    /news
    image_search   /images
    video_search   /videos
    places_search  /places        google maps locations
    maps_search    /maps
    shopping_search /shopping
    scholar_search /scholar
    autocomplete   /autocomplete

Plus a separate scrape host (https://scrape.serper.dev) used for `web_scrape`.
The scrape host can be overridden via `extra_config["scrape_url"]`.

Authentication: header `X-API-KEY: <key>`.
Default base URL: `https://google.serper.dev`.

Also implements the `WebSearchAdapter` Protocol (`search(query)`).
"""

from typing import Any, ClassVar

import httpx

from openlia.data._http import async_request_with_retry
from openlia.data.adapters.eodhd import _parse_retry_after
from openlia.data.base import ProviderAdapter
from openlia.data.errors import (
    AuthenticationError,
    DataNotAvailable,
    DataSourceError,
    RateLimitError,
)
from openlia.data.types import ProviderCategory, ProviderEntry, ToolResult
from openlia.llm.runtime.web_search import WebSearchResult

_REQUEST_TIMEOUT_SECONDS = 30.0
_DEFAULT_SCRAPE_URL = "https://scrape.serper.dev"

_SEARCH_PATHS: dict[str, str] = {
    "web_search": "/search",
    "news_search": "/news",
    "image_search": "/images",
    "video_search": "/videos",
    "places_search": "/places",
    "maps_search": "/maps",
    "shopping_search": "/shopping",
    "scholar_search": "/scholar",
    "autocomplete": "/autocomplete",
}

_PASSTHROUGH_KEYS = (
    "gl",
    "hl",
    "location",
    "num",
    "page",
    "tbs",
    "type",
    "autocorrect",
)


class SerperAdapter(ProviderAdapter):
    """Serper adapter (also implements WebSearchAdapter Protocol)."""

    kind: ClassVar[str] = "serper"
    category: ClassVar[ProviderCategory] = ProviderCategory.SEARCH
    capabilities: ClassVar[frozenset[str]] = frozenset(
        {
            *_SEARCH_PATHS.keys(),
            "web_scrape",
        }
    )

    def __init__(self, entry: ProviderEntry) -> None:
        super().__init__(entry)
        if entry.base_url is None:
            raise ValueError("serper requires base_url")
        self._base_url = entry.base_url.rstrip("/")
        self._scrape_url = str(entry.extra_config.get("scrape_url", _DEFAULT_SCRAPE_URL)).rstrip(
            "/"
        )

    async def fetch(
        self,
        capability: str,
        params: dict[str, Any],
    ) -> ToolResult:
        if capability not in self.capabilities:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason=f"capability {capability!r} not declared by serper",
            )
        if capability == "web_scrape":
            url, body = self._build_scrape(params)
        else:
            path, body = self._build_search(capability, params)
            url = f"{self._base_url}{path}"
        payload = await self._post_json(url, body, capability)
        return ToolResult(
            provider_kind=self.kind,
            capability=capability,
            payload=payload,
        )

    async def search(self, query: str) -> list[WebSearchResult]:
        result = await self.fetch("web_search", {"query": query, "num": 10})
        organic = (
            (result.payload or {}).get("organic", []) if isinstance(result.payload, dict) else []
        )
        out: list[WebSearchResult] = []
        for item in organic:
            if not isinstance(item, dict):
                continue
            url = str(item.get("link") or "").strip()
            if not url:
                continue
            out.append(
                WebSearchResult(
                    title=str(item.get("title") or ""),
                    url=url,
                    snippet=str(item.get("snippet") or ""),
                )
            )
        return out

    async def health_check(self) -> bool:
        try:
            await self._post_json(
                f"{self._base_url}/search",
                {"q": "openlia health", "num": 1},
                capability="web_search",
            )
        except (
            DataNotAvailable,
            RateLimitError,
            DataSourceError,
            AuthenticationError,
            httpx.HTTPError,
        ):
            return False
        return True

    def _build_search(
        self,
        capability: str,
        params: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        q = params.get("query") or params.get("q")
        if not q:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason="`query` parameter is required",
            )
        body: dict[str, Any] = {"q": str(q)}
        for key in _PASSTHROUGH_KEYS:
            if key in params and params[key] is not None:
                body[key] = params[key]
        # Convenience aliases the LLM tends to send.
        if "num" not in body and "count" in params and params["count"] is not None:
            body["num"] = params["count"]
        if "gl" not in body and "country" in params and params["country"] is not None:
            body["gl"] = params["country"]
        if "hl" not in body and "language" in params and params["language"] is not None:
            body["hl"] = params["language"]
        return _SEARCH_PATHS[capability], body

    def _build_scrape(
        self,
        params: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        target = params.get("url")
        if not target:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability="web_scrape",
                reason="`url` parameter is required",
            )
        body: dict[str, Any] = {"url": str(target)}
        if "include_markdown" in params and params["include_markdown"] is not None:
            body["includeMarkdown"] = bool(params["include_markdown"])
        return self._scrape_url, body

    async def _post_json(
        self,
        url: str,
        body: dict[str, Any],
        capability: str,
    ) -> dict[str, Any] | list[Any]:
        headers = {
            "X-API-KEY": self.entry.api_key or "",
            "Content-Type": "application/json",
        }

        async def _send() -> httpx.Response:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                return await client.post(url, json=body, headers=headers)

        def _classify_rate_limit(resp: httpx.Response) -> int | None:
            if resp.status_code != 429:
                return None
            ra = _parse_retry_after(resp.headers.get("Retry-After"))
            return ra if ra is not None else -1

        try:
            resp = await async_request_with_retry(
                _send,
                provider_kind=self.kind,
                rate_limit_classifier=_classify_rate_limit,
            )
        except httpx.TimeoutException as exc:
            raise DataSourceError(
                provider_kind=self.kind,
                detail=f"timeout: {exc}",
                is_transient=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise DataSourceError(
                provider_kind=self.kind,
                detail=str(exc),
                is_transient=True,
            ) from exc

        if resp.status_code == 200:
            try:
                return resp.json()
            except ValueError as exc:
                raise DataSourceError(
                    provider_kind=self.kind,
                    status_code=200,
                    detail=f"malformed json: {exc}",
                ) from exc
        if resp.status_code == 400:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason=resp.text[:500] or "bad request",
            )
        if resp.status_code == 404:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason=resp.text.strip() or "not found",
            )
        if resp.status_code in (401, 403):
            raise AuthenticationError(
                provider_kind=self.kind,
                status_code=resp.status_code,
                detail=resp.text[:500],
            )
        if 500 <= resp.status_code < 600:
            raise DataSourceError(
                provider_kind=self.kind,
                status_code=resp.status_code,
                detail=resp.text[:500],
                is_transient=True,
            )
        raise DataSourceError(
            provider_kind=self.kind,
            status_code=resp.status_code,
            detail=resp.text[:500],
        )
