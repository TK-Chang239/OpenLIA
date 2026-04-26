"""Mediastack adapter — news provider.

Capabilities (Plan 3 NEWS):
    general_news       GET /news?keywords={query}
    company_news       GET /news?keywords={symbol or company}
    news_archive       GET /news?date=YYYY-MM-DD,YYYY-MM-DD
    top_headlines      GET /news?sort=published_desc&limit={n}
    topic_news         GET /news?categories={categories}
    news_sources       GET /sources

Authentication: `?access_key=<key>` query param on every request.

Response envelope quirk: Mediastack often returns HTTP 200 with an
`{"error": {"code": ..., "message": ...}}` body for failures. We map known
codes onto our typed error hierarchy:
    invalid_access_key, missing_access_key, inactive_user,
    usage_limit_reached  -> AuthenticationError
    rate_limit_reached   -> RateLimitError
    validation_error     -> DataNotAvailable
    everything else      -> DataSourceError
"""

from typing import Any, ClassVar

import httpx

from openlia.data._http import async_request_with_retry
from openlia.data.base import ProviderAdapter
from openlia.data.errors import (
    AuthenticationError,
    DataNotAvailable,
    DataSourceError,
    RateLimitError,
)
from openlia.data.types import ProviderCategory, ProviderEntry, ToolResult

_HEALTH_CHECK_PATH = "/sources"
_REQUEST_TIMEOUT_SECONDS = 30.0

_AUTH_ERROR_CODES: frozenset[str] = frozenset(
    {
        "invalid_access_key",
        "missing_access_key",
        "inactive_user",
        "usage_limit_reached",
    }
)
_RATE_LIMIT_ERROR_CODES: frozenset[str] = frozenset({"rate_limit_reached"})
_NOT_AVAILABLE_ERROR_CODES: frozenset[str] = frozenset({"validation_error"})


class MediastackAdapter(ProviderAdapter):
    """Mediastack news adapter."""

    kind: ClassVar[str] = "mediastack"
    category: ClassVar[ProviderCategory] = ProviderCategory.NEWS
    capabilities: ClassVar[frozenset[str]] = frozenset(
        {
            "general_news",
            "company_news",
            "news_archive",
            "top_headlines",
            "topic_news",
            "news_sources",
        }
    )

    def __init__(self, entry: ProviderEntry) -> None:
        super().__init__(entry)
        if entry.base_url is None:
            raise ValueError("mediastack requires base_url")
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
                reason=f"capability {capability!r} not declared by mediastack",
            )

        path, query = self._build_request(capability, params)
        payload = await self._get_json(path, query, capability=capability)
        return ToolResult(
            provider_kind=self.kind,
            capability=capability,
            payload=payload,
        )

    async def health_check(self) -> bool:
        try:
            await self._get_json(_HEALTH_CHECK_PATH, {"limit": 1}, capability="news_sources")
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
        if capability == "news_sources":
            query: dict[str, Any] = {}
            if "search" in params:
                query["search"] = params["search"]
            if "countries" in params:
                query["countries"] = params["countries"]
            if "categories" in params:
                query["categories"] = params["categories"]
            if "languages" in params:
                query["languages"] = params["languages"]
            if "limit" in params:
                query["limit"] = params["limit"]
            if "offset" in params:
                query["offset"] = params["offset"]
            return "/sources", query

        # all other capabilities hit /news
        query = {}

        if capability == "general_news":
            keywords = params.get("keywords") or params.get("query")
            if not keywords:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`keywords` parameter is required",
                )
            query["keywords"] = str(keywords)
        elif capability == "company_news":
            keywords = (
                params.get("keywords")
                or params.get("symbol")
                or params.get("company")
                or params.get("company_name")
            )
            if not keywords:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`symbol` or `keywords` parameter is required",
                )
            query["keywords"] = str(keywords)
        elif capability == "news_archive":
            date_value = params.get("date")
            if not date_value:
                from_date = params.get("from")
                to_date = params.get("to")
                if not from_date or not to_date:
                    raise DataNotAvailable(
                        provider_kind=self.kind,
                        capability=capability,
                        reason="`date` (or `from`+`to`) parameter is required",
                    )
                date_value = f"{from_date},{to_date}"
            query["date"] = str(date_value)
            if "keywords" in params:
                query["keywords"] = params["keywords"]
        elif capability == "top_headlines":
            query["sort"] = params.get("sort", "published_desc")
            query["limit"] = params.get("limit", 25)
            if "countries" in params:
                query["countries"] = params["countries"]
            if "categories" in params:
                query["categories"] = params["categories"]
            if "languages" in params:
                query["languages"] = params["languages"]
        elif capability == "topic_news":
            categories = params.get("categories") or params.get("topic")
            if not categories:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`categories` parameter is required",
                )
            query["categories"] = str(categories)
            if "keywords" in params:
                query["keywords"] = params["keywords"]
        else:  # pragma: no cover - guarded above
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason="internal routing bug",
            )

        for opt in ("languages", "countries", "sources", "limit", "offset", "sort"):
            if opt in params and opt not in query:
                query[opt] = params[opt]

        return "/news", query

    async def _get_json(
        self,
        path: str,
        query: dict[str, Any],
        *,
        capability: str,
    ) -> dict[str, Any] | list[Any]:
        params = dict(query)
        params["access_key"] = self.entry.api_key or ""
        url = f"{self._base_url}{path}"

        async def _send() -> httpx.Response:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                return await client.get(url, params=params)

        def _classify_rate_limit(resp: httpx.Response) -> int | None:
            if resp.status_code == 429:
                return -1
            if resp.status_code == 200:
                code = _extract_error_code(resp)
                if code in _RATE_LIMIT_ERROR_CODES:
                    return -1
            return None

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
                body = resp.json()
            except ValueError as exc:
                raise DataSourceError(
                    provider_kind=self.kind,
                    status_code=200,
                    detail=f"malformed json: {exc}",
                ) from exc
            self._raise_on_error_envelope(body, capability=capability)
            return body
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

    def _raise_on_error_envelope(
        self,
        body: dict[str, Any] | list[Any],
        *,
        capability: str,
    ) -> None:
        if not isinstance(body, dict):
            return
        error = body.get("error")
        if not isinstance(error, dict):
            return
        code = str(error.get("code") or "").strip()
        message = str(error.get("message") or "").strip()
        detail = f"{code}: {message}" if code else message or "unknown error"
        if code in _AUTH_ERROR_CODES:
            raise AuthenticationError(
                provider_kind=self.kind,
                status_code=200,
                detail=detail,
            )
        if code in _RATE_LIMIT_ERROR_CODES:
            raise RateLimitError(provider_kind=self.kind)
        if code in _NOT_AVAILABLE_ERROR_CODES:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason=detail,
            )
        raise DataSourceError(
            provider_kind=self.kind,
            status_code=200,
            detail=detail,
        )


def _extract_error_code(resp: httpx.Response) -> str | None:
    try:
        body = resp.json()
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None
    error = body.get("error")
    if not isinstance(error, dict):
        return None
    code = error.get("code")
    return str(code) if code else None
