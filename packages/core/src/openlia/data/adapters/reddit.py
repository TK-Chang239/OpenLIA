"""Reddit adapter — social media provider.

Reddit does not publish a first-party MCP server, so this adapter wraps the
Reddit Data API directly using the documented OAuth2 flow
(reddit.com/dev/api/oauth). Confidential server-side usage uses the
`client_credentials` grant; script-type apps use `password`.

Capabilities:
    social_sentiment   GET /search                site-wide post/comment search
    company_news       GET /r/{sub}/search        restricted to financial subs
    subreddit_hot      GET /r/{sub}/hot
    subreddit_top      GET /r/{sub}/top
    subreddit_new      GET /r/{sub}/new
    subreddit_search   GET /r/{sub}/search
    subreddit_about    GET /r/{sub}/about
    post_comments      GET /comments/{post_id}

Authentication:
    api_key  : "<client_id>:<client_secret>"  (HTTP Basic for the token endpoint)
    extra_config:
        user_agent  : str (required; Reddit blocks generic UAs — set to e.g.
                      "openlia/1.0 by /u/<your-reddit-username>")
        grant_type  : "client_credentials" (default) | "password"
        username    : required when grant_type == "password"
        password    : required when grant_type == "password"
        token_url   : override (default https://www.reddit.com/api/v1/access_token)
        default_subs: comma-separated list used by company_news when no `subreddit`
                      param is supplied (default "investing,stocks,wallstreetbets")

Default base URL: `https://oauth.reddit.com`.
"""

import asyncio
import base64
import time
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
_DEFAULT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_DEFAULT_SUBS = "investing,stocks,wallstreetbets"
_TOKEN_REFRESH_SAFETY_SECONDS = 60


class RedditAdapter(ProviderAdapter):
    """Reddit adapter using the Reddit Data API + OAuth2."""

    kind: ClassVar[str] = "reddit"
    category: ClassVar[ProviderCategory] = ProviderCategory.SOCIAL_MEDIA
    capabilities: ClassVar[frozenset[str]] = frozenset(
        {
            "social_sentiment",
            "company_news",
            "subreddit_hot",
            "subreddit_top",
            "subreddit_new",
            "subreddit_search",
            "subreddit_about",
            "post_comments",
        }
    )

    def __init__(self, entry: ProviderEntry) -> None:
        super().__init__(entry)
        if entry.base_url is None:
            raise ValueError("reddit requires base_url")
        self._base_url = entry.base_url.rstrip("/")
        self._client_id, self._client_secret = self._parse_credentials(entry.api_key)
        cfg = entry.extra_config
        self._user_agent = str(cfg.get("user_agent") or "").strip()
        if not self._user_agent:
            raise ValueError(
                "reddit requires extra_config.user_agent (e.g. 'openlia/1.0 by /u/<username>')"
            )
        self._grant_type = str(cfg.get("grant_type") or "client_credentials")
        self._username = cfg.get("username")
        self._password = cfg.get("password")
        self._token_url = str(cfg.get("token_url") or _DEFAULT_TOKEN_URL)
        self._default_subs = str(cfg.get("default_subs") or _DEFAULT_SUBS)
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0
        self._token_lock = asyncio.Lock()

    @staticmethod
    def _parse_credentials(api_key: str | None) -> tuple[str, str]:
        if not api_key or ":" not in api_key:
            raise ValueError("reddit api_key must be 'client_id:client_secret'")
        client_id, _, client_secret = api_key.partition(":")
        if not client_id or not client_secret:
            raise ValueError("reddit api_key must include both client_id and client_secret")
        return client_id, client_secret

    async def fetch(
        self,
        capability: str,
        params: dict[str, Any],
    ) -> ToolResult:
        if capability not in self.capabilities:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason=f"capability {capability!r} not declared by reddit",
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
            await self._ensure_access_token(force_refresh=True)
        except (AuthenticationError, DataSourceError, RateLimitError, httpx.HTTPError):
            return False
        return True

    def _build_request(
        self,
        capability: str,
        params: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        if capability == "social_sentiment":
            q = self._coerce_query(params, capability)
            query: dict[str, Any] = {
                "q": q,
                "sort": params.get("sort", "new"),
                "type": params.get("type", "link"),
                "limit": params.get("limit", 50),
                "restrict_sr": "false",
                "raw_json": 1,
            }
            self._apply_time_window(query, params)
            return "/search", query

        if capability == "company_news":
            q = self._coerce_query(params, capability)
            sub = self._coerce_subreddit(params) or self._default_subs
            query = {
                "q": q,
                "sort": params.get("sort", "new"),
                "limit": params.get("limit", 25),
                "restrict_sr": "true",
                "raw_json": 1,
            }
            self._apply_time_window(query, params)
            return f"/r/{sub}/search", query

        if capability in ("subreddit_hot", "subreddit_top", "subreddit_new"):
            sub = self._coerce_subreddit(params)
            if not sub:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`subreddit` parameter is required",
                )
            listing = capability.split("_", 1)[1]
            query = {"limit": params.get("limit", 25), "raw_json": 1}
            if listing == "top" and params.get("time"):
                query["t"] = params["time"]
            return f"/r/{sub}/{listing}", query

        if capability == "subreddit_search":
            sub = self._coerce_subreddit(params)
            if not sub:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`subreddit` parameter is required",
                )
            q = self._coerce_query(params, capability)
            query = {
                "q": q,
                "sort": params.get("sort", "new"),
                "limit": params.get("limit", 25),
                "restrict_sr": "true",
                "raw_json": 1,
            }
            self._apply_time_window(query, params)
            return f"/r/{sub}/search", query

        if capability == "subreddit_about":
            sub = self._coerce_subreddit(params)
            if not sub:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`subreddit` parameter is required",
                )
            return f"/r/{sub}/about", {"raw_json": 1}

        if capability == "post_comments":
            post_id = params.get("post_id") or params.get("id")
            if not post_id:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="`post_id` parameter is required",
                )
            query = {"limit": params.get("limit", 100), "raw_json": 1}
            if params.get("sort"):
                query["sort"] = params["sort"]
            return f"/comments/{post_id}", query

        raise DataNotAvailable(  # pragma: no cover
            provider_kind=self.kind,
            capability=capability,
            reason="internal routing bug",
        )

    def _coerce_query(self, params: dict[str, Any], capability: str) -> str:
        q = params.get("query") or params.get("q") or params.get("symbol")
        if not q:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason="`query` or `symbol` parameter is required",
            )
        return str(q)

    @staticmethod
    def _coerce_subreddit(params: dict[str, Any]) -> str | None:
        sub = params.get("subreddit") or params.get("sub")
        if sub is None:
            return None
        if isinstance(sub, list | tuple):
            return "+".join(str(x).lstrip("/").removeprefix("r/") for x in sub)
        return str(sub).lstrip("/").removeprefix("r/")

    @staticmethod
    def _apply_time_window(query: dict[str, Any], params: dict[str, Any]) -> None:
        if params.get("time"):
            query["t"] = params["time"]
        if params.get("after"):
            query["after"] = params["after"]
        if params.get("before"):
            query["before"] = params["before"]

    async def _ensure_access_token(self, *, force_refresh: bool = False) -> str:
        async with self._token_lock:
            now = time.monotonic()
            if (
                not force_refresh
                and self._access_token
                and now < self._token_expires_at - _TOKEN_REFRESH_SAFETY_SECONDS
            ):
                return self._access_token

            credentials = base64.b64encode(
                f"{self._client_id}:{self._client_secret}".encode()
            ).decode("ascii")
            headers = {
                "Authorization": f"Basic {credentials}",
                "User-Agent": self._user_agent,
                "Accept": "application/json",
            }
            if self._grant_type == "password":
                if not self._username or not self._password:
                    raise AuthenticationError(
                        provider_kind=self.kind,
                        status_code=401,
                        detail="grant_type=password requires extra_config.username and password",
                    )
                data = {
                    "grant_type": "password",
                    "username": str(self._username),
                    "password": str(self._password),
                }
            else:
                data = {"grant_type": "client_credentials"}

            try:
                async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                    resp = await client.post(self._token_url, data=data, headers=headers)
            except httpx.TimeoutException as exc:
                raise DataSourceError(
                    provider_kind=self.kind,
                    detail=f"token timeout: {exc}",
                    is_transient=True,
                ) from exc
            except httpx.HTTPError as exc:
                raise DataSourceError(
                    provider_kind=self.kind,
                    detail=f"token transport: {exc}",
                    is_transient=True,
                ) from exc

            if resp.status_code in (401, 403):
                raise AuthenticationError(
                    provider_kind=self.kind,
                    status_code=resp.status_code,
                    detail=resp.text[:500],
                )
            if resp.status_code != 200:
                raise DataSourceError(
                    provider_kind=self.kind,
                    status_code=resp.status_code,
                    detail=resp.text[:500],
                    is_transient=500 <= resp.status_code < 600,
                )
            try:
                body = resp.json()
            except ValueError as exc:
                raise DataSourceError(
                    provider_kind=self.kind,
                    status_code=200,
                    detail=f"token: malformed json: {exc}",
                ) from exc
            token = body.get("access_token")
            expires_in = int(body.get("expires_in") or 3600)
            if not token:
                raise AuthenticationError(
                    provider_kind=self.kind,
                    status_code=200,
                    detail=f"missing access_token: {body!r}",
                )
            self._access_token = str(token)
            self._token_expires_at = now + expires_in
            return self._access_token

    async def _get_json(
        self,
        path: str,
        query: dict[str, Any],
        capability: str,
    ) -> dict[str, Any] | list[Any]:
        url = f"{self._base_url}{path}"

        async def _send() -> httpx.Response:
            token = await self._ensure_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "User-Agent": self._user_agent,
                "Accept": "application/json",
            }
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
        if resp.status_code == 401:
            # Token may have expired between cache check and request; force refresh and retry once.
            self._access_token = None
            raise AuthenticationError(
                provider_kind=self.kind,
                status_code=401,
                detail=resp.text[:500],
            )
        if resp.status_code == 403:
            raise AuthenticationError(
                provider_kind=self.kind,
                status_code=403,
                detail=resp.text[:500],
            )
        if resp.status_code == 404:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason=resp.text.strip() or "not found",
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
