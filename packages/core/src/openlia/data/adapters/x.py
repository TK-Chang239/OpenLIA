"""X (Twitter) adapter — social media provider.

Wraps the X API v2 (api.x.com/2). The official X v2 endpoints used here mirror
the surface area of community X MCP servers (search, counts, trends, lookups).

Capabilities:
    social_sentiment   GET /2/tweets/search/recent   recent posts (cashtag query)
    company_news       GET /2/tweets/search/recent   alias used by RS recipe
    tweet_counts       GET /2/tweets/counts/recent   per-bucket post counts
    tweets_lookup      GET /2/tweets                 by ids
    user_tweets        GET /2/users/{id}/tweets
    user_lookup        GET /2/users/by/username/{u}
    trends_by_woeid    GET /2/trends/by/woeid/{woeid}

Authentication: header `Authorization: Bearer <bearer_token>` (App-only OAuth2
Bearer Token from the X Developer Portal). Set the bearer token in `api_key`.
Default base URL: `https://api.x.com/2`.
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
_DEFAULT_TWEET_FIELDS = "id,text,created_at,author_id,public_metrics,lang,entities"
_DEFAULT_USER_FIELDS = "id,name,username,verified,public_metrics"
_DEFAULT_EXPANSIONS = "author_id"


class XAdapter(ProviderAdapter):
    """X (Twitter) v2 adapter."""

    kind: ClassVar[str] = "x"
    category: ClassVar[ProviderCategory] = ProviderCategory.SOCIAL_MEDIA
    capabilities: ClassVar[frozenset[str]] = frozenset(
        {
            "social_sentiment",
            "company_news",
            "tweet_counts",
            "tweets_lookup",
            "user_tweets",
            "user_lookup",
            "trends_by_woeid",
        }
    )

    def __init__(self, entry: ProviderEntry) -> None:
        super().__init__(entry)
        if entry.base_url is None:
            raise ValueError("x requires base_url")
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
                reason=f"capability {capability!r} not declared by x",
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
            await self._get_json(
                "/tweets/search/recent",
                {"query": "openlia", "max_results": 10},
                capability="social_sentiment",
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
        if capability in ("social_sentiment", "company_news"):
            query_str = self._coerce_search_query(params, capability)
            query: dict[str, Any] = {"query": query_str}
            self._apply_search_window(query, params)
            query.setdefault("max_results", params.get("max_results", 100))
            query.setdefault("tweet.fields", params.get("tweet_fields", _DEFAULT_TWEET_FIELDS))
            query.setdefault("expansions", params.get("expansions", _DEFAULT_EXPANSIONS))
            query.setdefault("user.fields", params.get("user_fields", _DEFAULT_USER_FIELDS))
            if params.get("sort_order"):
                query["sort_order"] = params["sort_order"]
            if params.get("next_token"):
                query["next_token"] = params["next_token"]
            return "/tweets/search/recent", query

        if capability == "tweet_counts":
            query_str = self._coerce_search_query(params, capability)
            query = {"query": query_str, "granularity": params.get("granularity", "hour")}
            self._apply_search_window(query, params)
            return "/tweets/counts/recent", query

        if capability == "tweets_lookup":
            ids = params.get("ids") or params.get("id")
            if not ids:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`ids` parameter is required",
                )
            if isinstance(ids, list | tuple):
                ids = ",".join(str(x) for x in ids)
            query = {
                "ids": str(ids),
                "tweet.fields": params.get("tweet_fields", _DEFAULT_TWEET_FIELDS),
                "expansions": params.get("expansions", _DEFAULT_EXPANSIONS),
                "user.fields": params.get("user_fields", _DEFAULT_USER_FIELDS),
            }
            return "/tweets", query

        if capability == "user_tweets":
            user_id = params.get("user_id") or params.get("id")
            if not user_id:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`user_id` parameter is required",
                )
            query = {
                "max_results": params.get("max_results", 100),
                "tweet.fields": params.get("tweet_fields", _DEFAULT_TWEET_FIELDS),
            }
            for k in ("start_time", "end_time", "since_id", "until_id", "pagination_token"):
                if params.get(k):
                    query[k] = params[k]
            return f"/users/{user_id}/tweets", query

        if capability == "user_lookup":
            username = params.get("username") or params.get("handle")
            if not username:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`username` parameter is required",
                )
            query = {"user.fields": params.get("user_fields", _DEFAULT_USER_FIELDS)}
            return f"/users/by/username/{str(username).lstrip('@')}", query

        if capability == "trends_by_woeid":
            woeid = params.get("woeid")
            if woeid is None:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`woeid` parameter is required",
                )
            query = {}
            if params.get("max_trends"):
                query["max_trends"] = params["max_trends"]
            if params.get("trend_fields"):
                query["trend.fields"] = params["trend_fields"]
            return f"/trends/by/woeid/{woeid}", query

        raise DataNotAvailable(  # pragma: no cover
            provider_kind=self.kind,
            capability=capability,
            reason="internal routing bug",
        )

    def _coerce_search_query(self, params: dict[str, Any], capability: str) -> str:
        if params.get("query"):
            return str(params["query"])
        symbol = params.get("symbol") or params.get("ticker")
        if symbol:
            sym = str(symbol).lstrip("$").upper()
            return f"${sym} -is:retweet lang:en"
        raise DataNotAvailable(
            provider_kind=self.kind,
            capability=capability,
            reason="`query` or `symbol` parameter is required",
        )

    @staticmethod
    def _apply_search_window(query: dict[str, Any], params: dict[str, Any]) -> None:
        for k in ("start_time", "end_time", "since_id", "until_id"):
            if params.get(k):
                query[k] = params[k]

    async def _get_json(
        self,
        path: str,
        query: dict[str, Any],
        capability: str,
    ) -> dict[str, Any] | list[Any]:
        url = f"{self._base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.entry.api_key or ''}",
            "Accept": "application/json",
        }

        async def _send() -> httpx.Response:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                return await client.get(url, params=query, headers=headers)

        def _classify_rate_limit(resp: httpx.Response) -> int | None:
            if resp.status_code != 429:
                return None
            ra = _parse_retry_after(resp.headers.get("Retry-After"))
            if ra is None:
                # X exposes x-rate-limit-reset (epoch seconds) on 429.
                reset = resp.headers.get("x-rate-limit-reset")
                if reset:
                    try:
                        import time as _time

                        ra = max(0, int(reset) - int(_time.time()))
                    except ValueError:
                        ra = None
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
        if resp.status_code in (400, 422):
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
