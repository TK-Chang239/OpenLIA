"""Tavily adapter — search provider.

Mirrors the official Tavily MCP server (github.com/tavily-ai/tavily-mcp) on top
of the Tavily REST API at api.tavily.com.

Capabilities:
    web_search    POST /search    real-time web search with optional answer
    web_extract   POST /extract   intelligent page extraction (1+ urls)
    web_crawl     POST /crawl     site crawl from a root url
    web_map       POST /map       structured site map without content extraction

Authentication: header `Authorization: Bearer tvly-<key>`.
Default base URL: `https://api.tavily.com`.

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

_REQUEST_TIMEOUT_SECONDS = 60.0


class TavilyAdapter(ProviderAdapter):
    """Tavily adapter (also implements WebSearchAdapter Protocol)."""

    kind: ClassVar[str] = "tavily"
    category: ClassVar[ProviderCategory] = ProviderCategory.SEARCH
    capabilities: ClassVar[frozenset[str]] = frozenset(
        {
            "web_search",
            "web_extract",
            "web_crawl",
            "web_map",
        }
    )

    def __init__(self, entry: ProviderEntry) -> None:
        super().__init__(entry)
        if entry.base_url is None:
            raise ValueError("tavily requires base_url")
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
                reason=f"capability {capability!r} not declared by tavily",
            )
        path, body = self._build_request(capability, params)
        payload = await self._post_json(path, body, capability)
        return ToolResult(
            provider_kind=self.kind,
            capability=capability,
            payload=payload,
        )

    async def search(self, query: str) -> list[WebSearchResult]:
        result = await self.fetch(
            "web_search", {"query": query, "max_results": 10, "search_depth": "basic"}
        )
        items = (
            (result.payload or {}).get("results", []) if isinstance(result.payload, dict) else []
        )
        out: list[WebSearchResult] = []
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
                    snippet=str(item.get("content") or ""),
                )
            )
        return out

    async def health_check(self) -> bool:
        try:
            await self._post_json(
                "/search",
                {"query": "openlia health", "max_results": 1, "search_depth": "basic"},
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
            for key in (
                "search_depth",
                "topic",
                "max_results",
                "chunks_per_source",
                "time_range",
                "start_date",
                "end_date",
                "include_answer",
                "include_raw_content",
                "include_images",
                "include_image_descriptions",
                "include_favicon",
                "include_domains",
                "exclude_domains",
                "country",
                "auto_parameters",
                "exact_match",
                "include_usage",
                "safe_search",
            ):
                if key in params and params[key] is not None:
                    body[key] = params[key]
            return "/search", body

        if capability == "web_extract":
            urls = params.get("urls") or params.get("url")
            if not urls:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`urls` parameter is required",
                )
            body = {"urls": urls if isinstance(urls, list) else [str(urls)]}
            for key in (
                "query",
                "chunks_per_source",
                "extract_depth",
                "include_images",
                "include_favicon",
                "format",
                "timeout",
                "include_usage",
            ):
                if key in params and params[key] is not None:
                    body[key] = params[key]
            return "/extract", body

        if capability == "web_crawl":
            url = params.get("url")
            if not url:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`url` parameter is required",
                )
            body = {"url": str(url)}
            for key in (
                "instructions",
                "chunks_per_source",
                "max_depth",
                "max_breadth",
                "limit",
                "select_paths",
                "select_domains",
                "exclude_paths",
                "exclude_domains",
                "allow_external",
                "include_images",
                "extract_depth",
                "format",
                "include_favicon",
                "timeout",
                "include_usage",
            ):
                if key in params and params[key] is not None:
                    body[key] = params[key]
            return "/crawl", body

        if capability == "web_map":
            url = params.get("url")
            if not url:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`url` parameter is required",
                )
            body = {"url": str(url)}
            for key in (
                "instructions",
                "max_depth",
                "max_breadth",
                "limit",
                "select_paths",
                "select_domains",
                "exclude_paths",
                "exclude_domains",
                "allow_external",
                "categories",
                "include_usage",
            ):
                if key in params and params[key] is not None:
                    body[key] = params[key]
            return "/map", body

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
        if resp.status_code == 400:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason=resp.text[:500] or "bad request",
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
