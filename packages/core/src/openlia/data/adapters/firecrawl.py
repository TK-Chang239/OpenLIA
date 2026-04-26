"""Firecrawl adapter — search + scraping provider.

Modelled on the official Firecrawl API (api.firecrawl.dev) and the Firecrawl
MCP server (github.com/mendableai/firecrawl-mcp-server).

Capabilities:
    web_search   POST /v1/search    (LLM-grade web search with optional scrape)
    web_scrape   POST /v1/scrape    (single URL → markdown/html)
    web_crawl    POST /v1/crawl     (multi-page crawl from a seed URL)
    web_map      POST /v1/map       (discover all URLs reachable from a seed)
    web_extract  POST /v1/extract   (LLM extraction from one or more URLs)

Authentication: header `Authorization: Bearer fc-<key>`.
Default base URL: `https://api.firecrawl.dev`.

Also implements the `WebSearchAdapter` Protocol (`search(query)`) so it can
back the runtime's `web_search` tool when the active LLM lacks native web
search.
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

_REQUEST_TIMEOUT_SECONDS = 60.0
_HEALTH_CHECK_PATH = "/v1/search"


class FirecrawlAdapter(ProviderAdapter):
    """Firecrawl adapter (also implements WebSearchAdapter Protocol)."""

    kind: ClassVar[str] = "firecrawl"
    category: ClassVar[ProviderCategory] = ProviderCategory.SEARCH
    capabilities: ClassVar[frozenset[str]] = frozenset(
        {
            "web_search",
            "web_scrape",
            "web_crawl",
            "web_map",
            "web_extract",
        }
    )

    def __init__(self, entry: ProviderEntry) -> None:
        super().__init__(entry)
        if entry.base_url is None:
            raise ValueError("firecrawl requires base_url")
        self._base_url = entry.base_url.rstrip("/")

    async def fetch(
        self,
        capability: str,
        params: dict[str, Any],
    ) -> ToolResult:
        if capability not in self.capabilities:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason=f"capability {capability!r} not declared by firecrawl",
            )
        path, body = self._build_request(capability, params)
        payload = await self._post_json(path, body, capability)
        return ToolResult(
            provider_kind=self.kind,
            capability=capability,
            payload=payload,
        )

    async def search(self, query: str) -> list[WebSearchResult]:
        """WebSearchAdapter Protocol implementation backed by /v1/search."""
        result = await self.fetch("web_search", {"query": query, "limit": 10})
        payload = result.payload if isinstance(result.payload, dict) else {}
        items = payload.get("data") or payload.get("results") or []
        out: list[WebSearchResult] = []
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                url = str(item.get("url") or "").strip()
                if not url:
                    continue
                out.append(
                    WebSearchResult(
                        title=str(item.get("title") or ""),
                        url=url,
                        snippet=str(item.get("description") or item.get("snippet") or ""),
                    )
                )
        return out

    async def health_check(self) -> bool:
        try:
            await self._post_json(
                _HEALTH_CHECK_PATH,
                {"query": "openlia health", "limit": 1},
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

    def _build_request(
        self,
        capability: str,
        params: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        if capability == "web_search":
            q = params.get("query") or params.get("q")
            if not q:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`query` parameter is required",
                )
            body: dict[str, Any] = {"query": str(q)}
            for k in ("limit", "lang", "country", "tbs", "filter", "scrapeOptions"):
                if k in params and params[k] is not None:
                    body[k] = params[k]
            return "/v1/search", body

        if capability == "web_scrape":
            url = params.get("url")
            if not url:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`url` parameter is required",
                )
            body = {"url": str(url)}
            for k in (
                "formats",
                "onlyMainContent",
                "includeTags",
                "excludeTags",
                "waitFor",
                "timeout",
                "actions",
                "extract",
            ):
                if k in params and params[k] is not None:
                    body[k] = params[k]
            return "/v1/scrape", body

        if capability == "web_crawl":
            url = params.get("url")
            if not url:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`url` parameter is required",
                )
            body = {"url": str(url)}
            for k in (
                "limit",
                "maxDepth",
                "allowBackwardLinks",
                "allowExternalLinks",
                "includePaths",
                "excludePaths",
                "scrapeOptions",
                "webhook",
            ):
                if k in params and params[k] is not None:
                    body[k] = params[k]
            return "/v1/crawl", body

        if capability == "web_map":
            url = params.get("url")
            if not url:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`url` parameter is required",
                )
            body = {"url": str(url)}
            for k in ("search", "limit", "ignoreSitemap", "includeSubdomains"):
                if k in params and params[k] is not None:
                    body[k] = params[k]
            return "/v1/map", body

        if capability == "web_extract":
            urls = params.get("urls") or ([params["url"]] if params.get("url") else None)
            if not urls:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`urls` (or `url`) parameter is required",
                )
            body = {"urls": list(urls) if not isinstance(urls, list) else urls}
            for k in ("prompt", "schema", "systemPrompt", "allowExternalLinks", "enableWebSearch"):
                if k in params and params[k] is not None:
                    body[k] = params[k]
            return "/v1/extract", body

        raise DataNotAvailable(  # pragma: no cover
            provider_kind=self.kind,
            capability=capability,
            reason="internal routing bug",
        )

    async def _post_json(
        self,
        path: str,
        body: dict[str, Any],
        capability: str,
    ) -> dict[str, Any] | list[Any]:
        url = f"{self._base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.entry.api_key or ''}",
            "Content-Type": "application/json",
            "Accept": "application/json",
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
        if resp.status_code == 404:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason=resp.text.strip() or "not found",
            )
        if resp.status_code == 422:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason=resp.text[:500] or "unprocessable parameters",
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
