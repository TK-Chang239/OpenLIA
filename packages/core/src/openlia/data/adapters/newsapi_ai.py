"""NewsAPI.ai (Event Registry) adapter.

Covers entity-rich news capabilities backed by the eventregistry.org REST API.

Capability map:
    company_news       POST /article/getArticles  (keyword=symbol/company name)
    general_news       POST /article/getArticles  (lang/dataType filters)
    topic_news         POST /article/getArticles  (conceptUri/categoryUri)
    news_archive       POST /article/getArticles  (dateStart/dateEnd window)
    trending_news      POST /article/getArticles  (sortBy=date, recent window)
    entity_news        GET  /suggestConceptsFast  (resolve entity -> conceptUri)
    event_summary      POST /event/getEvent       (single event detail)
    event_search       POST /event/getEvents      (clustered event search)

Authentication: NewsAPI.ai accepts the `apiKey` field in the JSON body for
POST endpoints and as `?apiKey=` for GET endpoints. The base URL is
`https://eventregistry.org/api/v1` by default (configured per-provider).

NewsAPI.ai sometimes returns HTTP 200 with a JSON body of `{"error": "..."}`.
We treat that as `AuthenticationError` when the message looks like a bad-key
signal, otherwise as a non-transient `DataSourceError`.
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

_REQUEST_TIMEOUT_SECONDS = 30.0
_HEALTH_CHECK_PATH = "/suggestConceptsFast"
_DEFAULT_LANG = "eng"
_DEFAULT_ARTICLE_COUNT = 50
_DEFAULT_EVENT_COUNT = 25
_AUTH_ERROR_NEEDLES = (
    "invalid api key",
    "invalid apikey",
    "wrong api key",
    "api key is not valid",
    "unauthorized",
    "not authorized",
    "authentication failed",
)


class NewsAPIAIAdapter(ProviderAdapter):
    """NewsAPI.ai (Event Registry) news + event adapter."""

    kind: ClassVar[str] = "newsapi_ai"
    category: ClassVar[ProviderCategory] = ProviderCategory.NEWS
    capabilities: ClassVar[frozenset[str]] = frozenset(
        {
            "company_news",
            "general_news",
            "topic_news",
            "news_archive",
            "trending_news",
            "entity_news",
            "event_summary",
            "event_search",
        }
    )

    def __init__(self, entry: ProviderEntry) -> None:
        super().__init__(entry)
        if entry.base_url is None:
            raise ValueError("newsapi_ai requires base_url")
        self._base_url = entry.base_url.rstrip("/")
        self._default_lang = str(entry.extra_config.get("lang", _DEFAULT_LANG))

    async def fetch(
        self,
        capability: str,
        params: dict[str, Any],
    ) -> ToolResult:
        if capability not in self.capabilities:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason=f"capability {capability!r} not declared by newsapi_ai",
            )

        if capability == "company_news":
            payload = await self._fetch_company_news(params)
        elif capability == "general_news":
            payload = await self._fetch_general_news(params)
        elif capability == "topic_news":
            payload = await self._fetch_topic_news(params)
        elif capability == "news_archive":
            payload = await self._fetch_news_archive(params)
        elif capability == "trending_news":
            payload = await self._fetch_trending_news(params)
        elif capability == "entity_news":
            payload = await self._fetch_entity_news(params)
        elif capability == "event_summary":
            payload = await self._fetch_event_summary(params)
        elif capability == "event_search":
            payload = await self._fetch_event_search(params)
        else:  # pragma: no cover - guarded above
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason="internal routing bug",
            )

        return ToolResult(
            provider_kind=self.kind,
            capability=capability,
            payload=payload,
        )

    async def health_check(self) -> bool:
        try:
            await self._get_json(_HEALTH_CHECK_PATH, {"prefix": "apple", "source": "concept"})
        except (
            DataNotAvailable,
            RateLimitError,
            DataSourceError,
            AuthenticationError,
            httpx.HTTPError,
        ):
            return False
        return True

    # ---------- per-capability builders ----------

    async def _fetch_company_news(self, params: dict[str, Any]) -> dict[str, Any] | list[Any]:
        keyword = params.get("keyword") or params.get("symbol") or params.get("company")
        concept_uri = params.get("conceptUri") or params.get("concept_uri")
        if not keyword and not concept_uri:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability="company_news",
                reason="`keyword`, `symbol`, `company`, or `conceptUri` is required",
            )
        body: dict[str, Any] = {
            "resultType": "articles",
            "articlesSortBy": params.get("sortBy", "date"),
            "articlesCount": int(params.get("limit", _DEFAULT_ARTICLE_COUNT)),
            "lang": params.get("lang", self._default_lang),
        }
        if concept_uri:
            body["conceptUri"] = concept_uri
        if keyword:
            body["keyword"] = str(keyword)
        if "dateStart" in params:
            body["dateStart"] = params["dateStart"]
        if "dateEnd" in params:
            body["dateEnd"] = params["dateEnd"]
        return await self._post_json("/article/getArticles", body)

    async def _fetch_general_news(self, params: dict[str, Any]) -> dict[str, Any] | list[Any]:
        body: dict[str, Any] = {
            "resultType": "articles",
            "articlesSortBy": params.get("sortBy", "date"),
            "articlesCount": int(params.get("limit", _DEFAULT_ARTICLE_COUNT)),
            "lang": params.get("lang", self._default_lang),
            "dataType": params.get("dataType", ["news"]),
        }
        if "keyword" in params:
            body["keyword"] = params["keyword"]
        return await self._post_json("/article/getArticles", body)

    async def _fetch_topic_news(self, params: dict[str, Any]) -> dict[str, Any] | list[Any]:
        concept_uri = params.get("conceptUri") or params.get("concept_uri")
        category_uri = params.get("categoryUri") or params.get("category_uri")
        if not concept_uri and not category_uri:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability="topic_news",
                reason="`conceptUri` or `categoryUri` is required",
            )
        body: dict[str, Any] = {
            "resultType": "articles",
            "articlesSortBy": params.get("sortBy", "rel"),
            "articlesCount": int(params.get("limit", _DEFAULT_ARTICLE_COUNT)),
            "lang": params.get("lang", self._default_lang),
        }
        if concept_uri:
            body["conceptUri"] = concept_uri
        if category_uri:
            body["categoryUri"] = category_uri
        return await self._post_json("/article/getArticles", body)

    async def _fetch_news_archive(self, params: dict[str, Any]) -> dict[str, Any] | list[Any]:
        date_start = params.get("dateStart") or params.get("from")
        date_end = params.get("dateEnd") or params.get("to")
        if not date_start or not date_end:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability="news_archive",
                reason="`dateStart` and `dateEnd` are required",
            )
        body: dict[str, Any] = {
            "resultType": "articles",
            "articlesSortBy": params.get("sortBy", "date"),
            "articlesCount": int(params.get("limit", _DEFAULT_ARTICLE_COUNT)),
            "lang": params.get("lang", self._default_lang),
            "dateStart": date_start,
            "dateEnd": date_end,
        }
        if "keyword" in params:
            body["keyword"] = params["keyword"]
        if "conceptUri" in params:
            body["conceptUri"] = params["conceptUri"]
        return await self._post_json("/article/getArticles", body)

    async def _fetch_trending_news(self, params: dict[str, Any]) -> dict[str, Any] | list[Any]:
        body: dict[str, Any] = {
            "resultType": "articles",
            "articlesSortBy": "date",
            "articlesCount": int(params.get("limit", _DEFAULT_ARTICLE_COUNT)),
            "lang": params.get("lang", self._default_lang),
            "dataType": ["news"],
        }
        if "categoryUri" in params:
            body["categoryUri"] = params["categoryUri"]
        return await self._post_json("/article/getArticles", body)

    async def _fetch_entity_news(self, params: dict[str, Any]) -> dict[str, Any] | list[Any]:
        prefix = params.get("prefix") or params.get("query")
        if not prefix:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability="entity_news",
                reason="`prefix` (entity search string) is required",
            )
        query: dict[str, Any] = {
            "prefix": str(prefix),
            "source": params.get("source", "concept"),
            "lang": params.get("lang", self._default_lang),
        }
        return await self._get_json("/suggestConceptsFast", query)

    async def _fetch_event_summary(self, params: dict[str, Any]) -> dict[str, Any] | list[Any]:
        event_uri = params.get("eventUri") or params.get("event_uri")
        if not event_uri:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability="event_summary",
                reason="`eventUri` is required",
            )
        body: dict[str, Any] = {
            "eventUri": event_uri,
            "infoArticleCount": int(params.get("articleCount", 5)),
            "lang": params.get("lang", self._default_lang),
        }
        return await self._post_json("/event/getEvent", body)

    async def _fetch_event_search(self, params: dict[str, Any]) -> dict[str, Any] | list[Any]:
        keyword = params.get("keyword")
        concept_uri = params.get("conceptUri") or params.get("concept_uri")
        if not keyword and not concept_uri:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability="event_search",
                reason="`keyword` or `conceptUri` is required",
            )
        body: dict[str, Any] = {
            "resultType": "events",
            "eventsSortBy": params.get("sortBy", "date"),
            "eventsCount": int(params.get("limit", _DEFAULT_EVENT_COUNT)),
            "lang": params.get("lang", self._default_lang),
        }
        if keyword:
            body["keyword"] = keyword
        if concept_uri:
            body["conceptUri"] = concept_uri
        if "dateStart" in params:
            body["dateStart"] = params["dateStart"]
        if "dateEnd" in params:
            body["dateEnd"] = params["dateEnd"]
        return await self._post_json("/event/getEvents", body)

    # ---------- transport ----------

    async def _post_json(
        self,
        path: str,
        body: dict[str, Any],
    ) -> dict[str, Any] | list[Any]:
        payload = dict(body)
        payload["apiKey"] = self.entry.api_key or ""
        url = f"{self._base_url}{path}"

        async def _send() -> httpx.Response:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                return await client.post(url, json=payload)

        return await self._dispatch(_send, path)

    async def _get_json(
        self,
        path: str,
        query: dict[str, Any],
    ) -> dict[str, Any] | list[Any]:
        params = dict(query)
        params["apiKey"] = self.entry.api_key or ""
        url = f"{self._base_url}{path}"

        async def _send() -> httpx.Response:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                return await client.get(url, params=params)

        return await self._dispatch(_send, path)

    async def _dispatch(
        self,
        send: Any,
        path: str,
    ) -> dict[str, Any] | list[Any]:
        def _classify_rate_limit(resp: httpx.Response) -> int | None:
            if resp.status_code != 429:
                return None
            ra = _parse_retry_after(resp.headers.get("Retry-After"))
            return ra if ra is not None else -1

        try:
            resp = await async_request_with_retry(
                send,
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
                data = resp.json()
            except ValueError as exc:
                raise DataSourceError(
                    provider_kind=self.kind,
                    status_code=200,
                    detail=f"malformed json: {exc}",
                ) from exc
            self._raise_if_body_error(data)
            return data
        if resp.status_code == 404:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=path.strip("/").split("/", 1)[0] or "unknown",
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

    def _raise_if_body_error(self, data: dict[str, Any] | list[Any]) -> None:
        """NewsAPI.ai returns 200 with `{"error": "..."}` on bad keys / bad params."""
        if not isinstance(data, dict):
            return
        err = data.get("error")
        if not err:
            return
        message = str(err)
        lowered = message.lower()
        if any(needle in lowered for needle in _AUTH_ERROR_NEEDLES):
            raise AuthenticationError(
                provider_kind=self.kind,
                status_code=200,
                detail=message[:500],
            )
        raise DataSourceError(
            provider_kind=self.kind,
            status_code=200,
            detail=message[:500],
        )
