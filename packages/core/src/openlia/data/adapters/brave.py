"""Brave Search adapter — search provider.

Mirrors the official Brave Search MCP server (github.com/brave/brave-search-mcp-server)
on top of the Brave Search REST API at api.search.brave.com/res/v1.

Capabilities:
    web_search       GET /web/search
    news_search      GET /news/search
    image_search     GET /images/search
    video_search     GET /videos/search
    local_pois       GET /local/pois          (ids=loc_id1,loc_id2,...)
    local_descriptions  GET /local/descriptions
    summarizer       GET /summarizer/search   (key from a prior web_search with summary=1)
    suggest          GET /suggest/v1/suggest

Authentication: header `X-Subscription-Token: <key>` plus `Accept: application/json`
and `Accept-Encoding: gzip` per Brave's published spec.
Default base URL: `https://api.search.brave.com/res/v1`.

Also implements the `WebSearchAdapter` Protocol (`search(query)`) so it can back
the runtime's `web_search` tool when the active LLM lacks native web search.
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
_HEALTH_CHECK_PATH = "/web/search"


class BraveSearchAdapter(ProviderAdapter):
    """Brave Search adapter (also implements WebSearchAdapter Protocol)."""

    kind: ClassVar[str] = "brave"
    category: ClassVar[ProviderCategory] = ProviderCategory.SEARCH
    capabilities: ClassVar[frozenset[str]] = frozenset(
        {
            "web_search",
            "news_search",
            "image_search",
            "video_search",
            "local_pois",
            "local_descriptions",
            "summarizer",
            "suggest",
        }
    )

    def __init__(self, entry: ProviderEntry) -> None:
        super().__init__(entry)
        if entry.base_url is None:
            raise ValueError("brave requires base_url")
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
                reason=f"capability {capability!r} not declared by brave",
            )
        path, query = self._build_request(capability, params)
        payload = await self._get_json(path, query, capability)
        return ToolResult(
            provider_kind=self.kind,
            capability=capability,
            payload=payload,
        )

    async def search(self, query: str) -> list[WebSearchResult]:
        """WebSearchAdapter Protocol implementation backed by /web/search."""
        result = await self.fetch("web_search", {"query": query, "count": 10})
        web = (result.payload or {}).get("web") if isinstance(result.payload, dict) else None
        items = (web or {}).get("results", []) if isinstance(web, dict) else []
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
                    snippet=str(item.get("description") or ""),
                )
            )
        return out

    async def health_check(self) -> bool:
        try:
            await self._get_json(
                _HEALTH_CHECK_PATH, {"q": "openlia health", "count": 1}, capability="web_search"
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
        if capability in (
            "web_search",
            "news_search",
            "image_search",
            "video_search",
        ):
            q = params.get("query") or params.get("q")
            if not q:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`query` parameter is required",
                )
            query: dict[str, Any] = {"q": str(q)}
            for key in (
                "country",
                "search_lang",
                "ui_lang",
                "safesearch",
                "freshness",
                "result_filter",
                "goggles_id",
                "units",
                "extra_snippets",
                "summary",
                "spellcheck",
                "text_decorations",
            ):
                if key in params and params[key] is not None:
                    query[key] = params[key]
            if "count" in params and params["count"] is not None:
                query["count"] = params["count"]
            if "offset" in params and params["offset"] is not None:
                query["offset"] = params["offset"]
            path_map = {
                "web_search": "/web/search",
                "news_search": "/news/search",
                "image_search": "/images/search",
                "video_search": "/videos/search",
            }
            return path_map[capability], query

        if capability in ("local_pois", "local_descriptions"):
            ids = params.get("ids")
            if not ids:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`ids` parameter is required",
                )
            if isinstance(ids, list | tuple):
                ids = ",".join(str(x) for x in ids)
            query = {"ids": str(ids)}
            for key in ("search_lang", "ui_lang", "units"):
                if key in params and params[key] is not None:
                    query[key] = params[key]
            path = "/local/pois" if capability == "local_pois" else "/local/descriptions"
            return path, query

        if capability == "summarizer":
            key = params.get("key")
            if not key:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`key` parameter is required (from a prior web_search summary=1 call)",
                )
            query = {"key": str(key)}
            for k in ("entity_info", "inline_references"):
                if k in params and params[k] is not None:
                    query[k] = params[k]
            return "/summarizer/search", query

        if capability == "suggest":
            q = params.get("query") or params.get("q")
            if not q:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`query` parameter is required",
                )
            query = {"q": str(q)}
            for k in ("country", "lang", "count", "rich"):
                if k in params and params[k] is not None:
                    query[k] = params[k]
            return "/suggest/v1/suggest", query

        raise DataNotAvailable(  # pragma: no cover
            provider_kind=self.kind,
            capability=capability,
            reason="internal routing bug",
        )

    async def _get_json(
        self,
        path: str,
        query: dict[str, Any],
        capability: str,
    ) -> dict[str, Any] | list[Any]:
        url = f"{self._base_url}{path}"
        headers = {
            "X-Subscription-Token": self.entry.api_key or "",
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
        }

        async def _send() -> httpx.Response:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                return await client.get(url, params=query, headers=headers)

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
