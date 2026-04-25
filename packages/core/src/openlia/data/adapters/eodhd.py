"""EODHD adapter — the default financial provider.

Covers five capabilities in Plan 3:
    stock_quote            GET /real-time/{ticker}
    historical_prices      GET /eod/{ticker}
    company_profile        GET /fundamentals/{ticker} (General block)
    company_news           GET /news?s={ticker}
    company_fundamentals   GET /fundamentals/{ticker} (Financials block)

Authentication: `?api_token=<key>` query param (EODHD's documented auth
method). We pass the key on every request.

Symbol convention: EODHD requires `{SYMBOL}.{EXCHANGE}` (e.g. AAPL.US).
The exchange suffix defaults to `US` and can be overridden per-provider via
`extra_config["exchange_suffix"]`.
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

_HEALTH_CHECK_PATH = "/user"
_REQUEST_TIMEOUT_SECONDS = 30.0


class EODHDAdapter(ProviderAdapter):
    """EODHD financial-data adapter."""

    kind: ClassVar[str] = "eodhd"
    category: ClassVar[ProviderCategory] = ProviderCategory.FINANCIAL
    capabilities: ClassVar[frozenset[str]] = frozenset(
        {
            "stock_quote",
            "historical_prices",
            "company_profile",
            "company_news",
            "company_fundamentals",
        }
    )

    def __init__(self, entry: ProviderEntry) -> None:
        super().__init__(entry)
        if entry.base_url is None:
            raise ValueError("eodhd requires base_url")
        self._base_url = entry.base_url.rstrip("/")
        self._exchange_suffix = str(entry.extra_config.get("exchange_suffix", "US")).upper()

    async def fetch(
        self,
        capability: str,
        params: dict[str, Any],
    ) -> ToolResult:
        if capability not in self.capabilities:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason=f"capability {capability!r} not declared by eodhd",
            )

        symbol = params.get("symbol")
        if not symbol:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason="`symbol` parameter is required",
            )
        ticker = self._format_ticker(str(symbol))

        if capability == "stock_quote":
            path = f"/real-time/{ticker}"
            query: dict[str, Any] = {"fmt": "json"}
        elif capability == "historical_prices":
            path = f"/eod/{ticker}"
            query = {"fmt": "json"}
            if "from" in params:
                query["from"] = params["from"]
            if "to" in params:
                query["to"] = params["to"]
        elif capability == "company_profile":
            path = f"/fundamentals/{ticker}"
            query = {"fmt": "json"}
        elif capability == "company_news":
            path = "/news"
            query = {"s": ticker, "limit": params.get("limit", 50)}
        elif capability == "company_fundamentals":
            path = f"/fundamentals/{ticker}"
            query = {"fmt": "json"}
        else:  # pragma: no cover - guarded above
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason="internal routing bug",
            )

        payload = await self._get_json(path, query)
        if capability == "company_fundamentals" and isinstance(payload, dict):
            financials = payload.get("Financials")
            if financials is None:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="no Financials block in response",
                )
            payload = {"Financials": financials}
        return ToolResult(
            provider_kind=self.kind,
            capability=capability,
            payload=payload,
        )

    async def health_check(self) -> bool:
        try:
            await self._get_json(_HEALTH_CHECK_PATH, {})
        except (
            DataNotAvailable,
            RateLimitError,
            DataSourceError,
            AuthenticationError,
            httpx.HTTPError,
        ):
            return False
        return True

    def _format_ticker(self, symbol: str) -> str:
        if "." in symbol:
            return symbol.upper()
        return f"{symbol.upper()}.{self._exchange_suffix}"

    async def _get_json(
        self,
        path: str,
        query: dict[str, Any],
    ) -> dict[str, Any] | list[Any]:
        params = dict(query)
        params["api_token"] = self.entry.api_key or ""
        url = f"{self._base_url}{path}"

        async def _send() -> httpx.Response:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                return await client.get(url, params=params)

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
                capability=path.split("/", 2)[1] or "unknown",
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
