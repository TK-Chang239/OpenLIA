"""NewsAPI.org adapter — news provider.

Capabilities:
    company_news     GET /everything?qInTitle=<symbol_or_name>
    general_news     GET /everything?q=<query>
    topic_news       GET /everything?q=<query> (alias targeting topics)
    top_headlines    GET /top-headlines
    news_sources     GET /top-headlines/sources
    news_archive     GET /everything with from/to date params

Authentication: header `X-Api-Key: <key>` (preferred over query param).
Default base URL: `https://newsapi.org/v2`.

NewsAPI returns 200 with `{"status": "ok"|"error", "code": "...", "message": "..."}`.
When `status == "error"`, the `code` field is mapped to typed errors.
"""

from datetime import UTC
from email.utils import parsedate_to_datetime
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

_HEALTH_CHECK_PATH = "/top-headlines/sources"
_REQUEST_TIMEOUT_SECONDS = 30.0

_AUTH_ERROR_CODES = frozenset({"apiKeyInvalid", "apiKeyMissing", "apiKeyDisabled"})
_RATE_LIMIT_ERROR_CODES = frozenset({"rateLimited"})
_NOT_AVAILABLE_ERROR_CODES = frozenset({"parameterInvalid", "sourcesTooMany"})


class NewsAPIOrgAdapter(ProviderAdapter):
    """NewsAPI.org news adapter."""

    kind: ClassVar[str] = "newsapi_org"
    category: ClassVar[ProviderCategory] = ProviderCategory.NEWS
    capabilities: ClassVar[frozenset[str]] = frozenset(
        {
            "company_news",
            "general_news",
            "topic_news",
            "top_headlines",
            "news_sources",
            "news_archive",
        }
    )

    def __init__(self, entry: ProviderEntry) -> None:
        super().__init__(entry)
        if entry.base_url is None:
            raise ValueError("newsapi_org requires base_url")
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
                reason=f"capability {capability!r} not declared by newsapi_org",
            )

        path, query = self._build_request(capability, params)
        payload = await self._get_json(path, query, capability)
        return ToolResult(
            provider_kind=self.kind,
            capability=capability,
            payload=payload,
        )

    async def health_check(self) -> bool:
        try:
            await self._get_json(_HEALTH_CHECK_PATH, {}, capability="news_sources")
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
        if capability == "company_news":
            symbol = params.get("symbol") or params.get("query")
            if not symbol:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`symbol` or `query` parameter is required",
                )
            query: dict[str, Any] = {"qInTitle": str(symbol)}
            self._apply_common_search_params(query, params)
            return "/everything", query

        if capability in ("general_news", "topic_news"):
            q = params.get("query") or params.get("q")
            if not q:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`query` parameter is required",
                )
            query = {"q": str(q)}
            self._apply_common_search_params(query, params)
            return "/everything", query

        if capability == "news_archive":
            q = params.get("query") or params.get("q")
            if not q:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`query` parameter is required",
                )
            query = {"q": str(q)}
            if "from" in params:
                query["from"] = params["from"]
            if "to" in params:
                query["to"] = params["to"]
            self._apply_common_search_params(query, params)
            return "/everything", query

        if capability == "top_headlines":
            query = {}
            for key in ("country", "category", "sources", "q"):
                if key in params and params[key] is not None:
                    query[key] = params[key]
            if "page_size" in params:
                query["pageSize"] = params["page_size"]
            if "page" in params:
                query["page"] = params["page"]
            return "/top-headlines", query

        if capability == "news_sources":
            query = {}
            for key in ("category", "language", "country"):
                if key in params and params[key] is not None:
                    query[key] = params[key]
            return "/top-headlines/sources", query

        raise DataNotAvailable(  # pragma: no cover - guarded above
            provider_kind=self.kind,
            capability=capability,
            reason="internal routing bug",
        )

    @staticmethod
    def _apply_common_search_params(
        query: dict[str, Any],
        params: dict[str, Any],
    ) -> None:
        if "language" in params and params["language"] is not None:
            query["language"] = params["language"]
        if "sort_by" in params and params["sort_by"] is not None:
            query["sortBy"] = params["sort_by"]
        if "sources" in params and params["sources"] is not None:
            query["sources"] = params["sources"]
        if "domains" in params and params["domains"] is not None:
            query["domains"] = params["domains"]
        if "page_size" in params:
            query["pageSize"] = params["page_size"]
        if "page" in params:
            query["page"] = params["page"]

    async def _get_json(
        self,
        path: str,
        query: dict[str, Any],
        capability: str,
    ) -> dict[str, Any] | list[Any]:
        url = f"{self._base_url}{path}"
        headers = {"X-Api-Key": self.entry.api_key or ""}

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
                payload = resp.json()
            except ValueError as exc:
                raise DataSourceError(
                    provider_kind=self.kind,
                    status_code=200,
                    detail=f"malformed json: {exc}",
                ) from exc
            self._raise_for_envelope_error(payload, capability)
            return payload
        if resp.status_code == 404:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason=resp.text.strip() or "not found",
            )
        if resp.status_code in (401, 403, 426):
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

    def _raise_for_envelope_error(
        self,
        payload: Any,
        capability: str,
    ) -> None:
        if not isinstance(payload, dict):
            return
        if payload.get("status") != "error":
            return
        code = str(payload.get("code") or "")
        message = str(payload.get("message") or "")
        if code in _AUTH_ERROR_CODES:
            raise AuthenticationError(
                provider_kind=self.kind,
                status_code=200,
                detail=f"{code}: {message}",
            )
        if code in _RATE_LIMIT_ERROR_CODES:
            raise RateLimitError(provider_kind=self.kind)
        if code in _NOT_AVAILABLE_ERROR_CODES:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason=f"{code}: {message}",
            )
        raise DataSourceError(
            provider_kind=self.kind,
            status_code=200,
            detail=f"{code}: {message}",
        )


def _parse_retry_after(value: str | None) -> int | None:
    """Parse a Retry-After header value as integer seconds.

    Accepts integer-seconds (RFC 7231) and RFC 1123 HTTP-dates. Returns the
    delay in seconds, clamped at >= 0, or None when the header is absent or
    unparseable.
    """
    if value is None:
        return None
    try:
        return max(0, int(value))
    except ValueError:
        pass
    try:
        target = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if target is None:
        return None
    from datetime import datetime

    now = datetime.now(tz=UTC)
    if target.tzinfo is None:
        target = target.replace(tzinfo=UTC)
    delta = (target - now).total_seconds()
    return max(0, int(delta))
