"""EODHD adapter — the default financial provider.

Capabilities mapped to EODHD REST endpoints:
    stock_quote            GET /real-time/{ticker}
    historical_prices      GET /eod/{ticker}
    company_profile        GET /fundamentals/{ticker} (General block)
    company_news           GET /news?s={ticker}
    financial_statements   GET /fundamentals/{ticker} (Financials block)
    analyst_ratings        GET /fundamentals/{ticker} (AnalystRatings block)
    economic_events        GET /economic-events
    earnings_data          GET /calendar/earnings
    macro_indicator        GET /macro-indicator/{country}
    insider_transactions   GET /insider-transactions
    social_sentiment       GET /sentiments?s={tickers}
    dividends              GET /div/{ticker}
    splits                 GET /splits/{ticker}
    ipo_calendar           GET /calendar/ipos

Authentication: `?api_token=<key>` query param (EODHD's documented auth
method). We pass the key on every request.

Symbol convention: EODHD requires `{SYMBOL}.{EXCHANGE}` (e.g. AAPL.US).
The exchange suffix defaults to `US` and can be overridden per-provider via
`extra_config["exchange_suffix"]`.

Macro country convention: ISO-3166 alpha-3 (e.g. USA, FRA, DEU). Defaults
to `USA` and can be overridden via `params["country"]`.
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

# Capabilities that need a `symbol` param.
_REQUIRES_SYMBOL: frozenset[str] = frozenset(
    {
        "stock_quote",
        "historical_prices",
        "company_profile",
        "company_news",
        "financial_statements",
        "analyst_ratings",
        "dividends",
        "splits",
        "social_sentiment",
    }
)

# Sub-block extraction from the unified /fundamentals payload. The endpoint
# returns one large object; we slice it down to just the block the caller
# asked for so the LLM isn't paying tokens for irrelevant data.
_FUNDAMENTALS_BLOCK: dict[str, str] = {
    "financial_statements": "Financials",
    "analyst_ratings": "AnalystRatings",
}


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
            "financial_statements",
            "analyst_ratings",
            "economic_events",
            "earnings_data",
            "macro_indicator",
            "insider_transactions",
            "social_sentiment",
            "dividends",
            "splits",
            "ipo_calendar",
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

        if capability in _REQUIRES_SYMBOL and not params.get("symbol"):
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason="`symbol` parameter is required",
            )

        path, query = self._route(capability, params)
        payload = await self._get_json(path, query)

        block = _FUNDAMENTALS_BLOCK.get(capability)
        if block is not None and isinstance(payload, dict):
            sub = payload.get(block)
            if sub is None:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason=f"no {block} block in response",
                )
            payload = {block: sub}

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

    def _route(
        self,
        capability: str,
        params: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        ticker = self._format_ticker(str(params["symbol"])) if params.get("symbol") else None

        if capability == "stock_quote":
            return f"/real-time/{ticker}", {"fmt": "json"}
        if capability == "historical_prices":
            query: dict[str, Any] = {"fmt": "json"}
            if "from" in params:
                query["from"] = params["from"]
            if "to" in params:
                query["to"] = params["to"]
            return f"/eod/{ticker}", query
        if capability == "company_profile":
            return f"/fundamentals/{ticker}", {"fmt": "json"}
        if capability == "company_news":
            return "/news", {"s": ticker, "limit": params.get("limit", 50)}
        if capability in ("financial_statements", "analyst_ratings"):
            return f"/fundamentals/{ticker}", {"fmt": "json"}
        if capability == "economic_events":
            query = {"fmt": "json"}
            for key in ("country", "type", "comparison"):
                if key in params:
                    query[key] = params[key]
            if "from" in params:
                query["from"] = params["from"]
            if "to" in params:
                query["to"] = params["to"]
            query["limit"] = params.get("limit", 50)
            if "offset" in params:
                query["offset"] = params["offset"]
            return "/economic-events", query
        if capability == "earnings_data":
            query = {"fmt": "json"}
            symbols = _resolve_symbols_param(params, ticker)
            if symbols:
                query["symbols"] = symbols
            if "from" in params:
                query["from"] = params["from"]
            if "to" in params:
                query["to"] = params["to"]
            return "/calendar/earnings", query
        if capability == "macro_indicator":
            country = str(params.get("country") or "USA").upper()
            query = {
                "fmt": "json",
                "indicator": params.get("indicator", "gdp_current_usd"),
            }
            return f"/macro-indicator/{country}", query
        if capability == "insider_transactions":
            query = {"fmt": "json", "limit": params.get("limit", 100)}
            if ticker is not None:
                query["code"] = ticker
            if "from" in params:
                query["from"] = params["from"]
            if "to" in params:
                query["to"] = params["to"]
            return "/insider-transactions", query
        if capability == "social_sentiment":
            symbols = _resolve_symbols_param(params, ticker) or ticker
            query = {"fmt": "json", "s": symbols}
            if "from" in params:
                query["from"] = params["from"]
            if "to" in params:
                query["to"] = params["to"]
            return "/sentiments", query
        if capability == "dividends":
            query = {"fmt": "json"}
            if "from" in params:
                query["from"] = params["from"]
            if "to" in params:
                query["to"] = params["to"]
            return f"/div/{ticker}", query
        if capability == "splits":
            query = {"fmt": "json"}
            if "from" in params:
                query["from"] = params["from"]
            if "to" in params:
                query["to"] = params["to"]
            return f"/splits/{ticker}", query
        if capability == "ipo_calendar":
            query = {"fmt": "json"}
            if "from" in params:
                query["from"] = params["from"]
            if "to" in params:
                query["to"] = params["to"]
            return "/calendar/ipos", query
        raise DataNotAvailable(  # pragma: no cover - guarded above
            provider_kind=self.kind,
            capability=capability,
            reason="internal routing bug",
        )

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


def _resolve_symbols_param(params: dict[str, Any], ticker: str | None) -> str | None:
    """Extract a comma-joined symbols string from `symbols` or fall back to `ticker`.

    EODHD endpoints that accept multiple symbols use a single comma-separated
    value (e.g. `s=AAPL.US,MSFT.US`). Callers may pass `symbols` as a list or
    a pre-joined string; otherwise we use the single resolved ticker.
    """
    raw = params.get("symbols")
    if raw is None:
        return ticker
    if isinstance(raw, list):
        return ",".join(str(s) for s in raw) if raw else None
    return str(raw)


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
