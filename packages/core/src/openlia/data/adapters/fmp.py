"""Financial Modeling Prep (FMP) adapter.

Wide-coverage financial data provider. Maps capabilities to FMP endpoints
across the v3 and v4 API namespaces:

    stock_quote            v3  /quote/{symbol}
    historical_prices      v3  /historical-price-full/{symbol}
    company_profile        v3  /profile/{symbol}
    company_news           v3  /stock_news?tickers={symbol}
    financial_statements   v3  /income-statement/{symbol} (+ balance, cash flow merged)
    stock_grade            v3  /grade/{symbol}
    insider_transactions   v4  /insider-trading?symbol={symbol}
    earnings_data          v3  /earning_calendar
    earnings_transcripts   v3  /earning_call_transcript/{symbol}
    dividends              v3  /historical-price-full/stock_dividend/{symbol}
    splits                 v3  /historical-price-full/stock_split/{symbol}
    economic_events        v3  /economic_calendar
    sector_performance     v3  /sector-performance
    market_movers_gainers  v3  /stock_market/gainers
    market_movers_losers   v3  /stock_market/losers
    market_movers_actives  v3  /stock_market/actives
    ipo_calendar           v3  /ipo_calendar
    esg                    v4  /esg-environmental-social-governance-data?symbol={symbol}
    etf_holdings           v3  /etf-holder/{symbol}
    crypto_quote           v3  /quote/{symbol}
    forex_quote            v3  /quote/{symbol}
    treasury_rates         v4  /treasury
    social_sentiment       v4  /historical/social-sentiment?symbol={symbol}
    analyst_ratings        v3  /rating/{symbol}
    macro_indicator        v4  /economic?name={indicator}

Authentication: `?apikey=<key>` query param on every request.

Base URL convention: `extra_config["v3_base_url"]` and `["v4_base_url"]`
override the defaults; otherwise we derive both from `entry.base_url` by
stripping a trailing `/api/v3` or `/api/v4` and re-attaching the right
suffix per capability.
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

_REQUEST_TIMEOUT_SECONDS = 30.0
_DEFAULT_V3 = "https://financialmodelingprep.com/api/v3"
_DEFAULT_V4 = "https://financialmodelingprep.com/api/v4"

# Capabilities that route through the v4 namespace.
_V4_CAPABILITIES: frozenset[str] = frozenset(
    {
        "insider_transactions",
        "esg",
        "treasury_rates",
        "social_sentiment",
        "macro_indicator",
    }
)

# Capabilities requiring `symbol` in params.
_REQUIRES_SYMBOL: frozenset[str] = frozenset(
    {
        "stock_quote",
        "historical_prices",
        "company_profile",
        "company_news",
        "financial_statements",
        "stock_grade",
        "analyst_ratings",
        "insider_transactions",
        "earnings_transcripts",
        "dividends",
        "splits",
        "esg",
        "etf_holdings",
        "crypto_quote",
        "forex_quote",
        "social_sentiment",
    }
)


class FMPAdapter(ProviderAdapter):
    """Financial Modeling Prep adapter."""

    kind: ClassVar[str] = "fmp"
    category: ClassVar[ProviderCategory] = ProviderCategory.FINANCIAL
    capabilities: ClassVar[frozenset[str]] = frozenset(
        {
            "stock_quote",
            "historical_prices",
            "company_profile",
            "company_news",
            "financial_statements",
            "stock_grade",
            "analyst_ratings",
            "insider_transactions",
            "earnings_data",
            "earnings_transcripts",
            "dividends",
            "splits",
            "economic_events",
            "sector_performance",
            "market_movers_gainers",
            "market_movers_losers",
            "market_movers_actives",
            "ipo_calendar",
            "esg",
            "etf_holdings",
            "crypto_quote",
            "forex_quote",
            "treasury_rates",
            "social_sentiment",
            "macro_indicator",
        }
    )

    def __init__(self, entry: ProviderEntry) -> None:
        super().__init__(entry)
        if entry.base_url is None:
            raise ValueError("fmp requires base_url")
        v3_override = entry.extra_config.get("v3_base_url")
        v4_override = entry.extra_config.get("v4_base_url")
        v3, v4 = _derive_base_urls(entry.base_url, v3_override, v4_override)
        self._v3_base_url = v3
        self._v4_base_url = v4

    async def fetch(
        self,
        capability: str,
        params: dict[str, Any],
    ) -> ToolResult:
        if capability not in self.capabilities:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason=f"capability {capability!r} not declared by fmp",
            )

        if capability in _REQUIRES_SYMBOL and not params.get("symbol"):
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason="`symbol` parameter is required",
            )

        symbol = str(params["symbol"]).upper() if params.get("symbol") else None
        path, query = self._route(capability, symbol, params)
        payload = await self._get_json(capability, path, query)
        return ToolResult(
            provider_kind=self.kind,
            capability=capability,
            payload=payload,
        )

    async def health_check(self) -> bool:
        # Cheap v3 endpoint that returns 200 with valid key, 401/403 otherwise.
        try:
            await self._get_json("stock_quote", "/quote/AAPL", {})
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
        symbol: str | None,
        params: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        query: dict[str, Any] = {}

        if capability == "stock_quote":
            return f"/quote/{symbol}", query
        if capability == "historical_prices":
            if "from" in params:
                query["from"] = params["from"]
            if "to" in params:
                query["to"] = params["to"]
            return f"/historical-price-full/{symbol}", query
        if capability == "company_profile":
            return f"/profile/{symbol}", query
        if capability == "company_news":
            query["tickers"] = symbol
            query["limit"] = params.get("limit", 50)
            return "/stock_news", query
        if capability == "financial_statements":
            query["limit"] = params.get("limit", 5)
            if "period" in params:
                query["period"] = params["period"]
            return f"/income-statement/{symbol}", query
        if capability == "stock_grade":
            query["limit"] = params.get("limit", 50)
            return f"/grade/{symbol}", query
        if capability == "analyst_ratings":
            return f"/rating/{symbol}", query
        if capability == "insider_transactions":
            query["symbol"] = symbol
            if "page" in params:
                query["page"] = params["page"]
            return "/insider-trading", query
        if capability == "earnings_data":
            if "from" in params:
                query["from"] = params["from"]
            if "to" in params:
                query["to"] = params["to"]
            return "/earning_calendar", query
        if capability == "earnings_transcripts":
            if "year" in params:
                query["year"] = params["year"]
            if "quarter" in params:
                query["quarter"] = params["quarter"]
            return f"/earning_call_transcript/{symbol}", query
        if capability == "dividends":
            return f"/historical-price-full/stock_dividend/{symbol}", query
        if capability == "splits":
            return f"/historical-price-full/stock_split/{symbol}", query
        if capability == "economic_events":
            if "from" in params:
                query["from"] = params["from"]
            if "to" in params:
                query["to"] = params["to"]
            return "/economic_calendar", query
        if capability == "sector_performance":
            return "/sector-performance", query
        if capability == "market_movers_gainers":
            return "/stock_market/gainers", query
        if capability == "market_movers_losers":
            return "/stock_market/losers", query
        if capability == "market_movers_actives":
            return "/stock_market/actives", query
        if capability == "ipo_calendar":
            if "from" in params:
                query["from"] = params["from"]
            if "to" in params:
                query["to"] = params["to"]
            return "/ipo_calendar", query
        if capability == "esg":
            query["symbol"] = symbol
            return "/esg-environmental-social-governance-data", query
        if capability == "etf_holdings":
            return f"/etf-holder/{symbol}", query
        if capability == "crypto_quote":
            return f"/quote/{symbol}", query
        if capability == "forex_quote":
            return f"/quote/{symbol}", query
        if capability == "treasury_rates":
            if "from" in params:
                query["from"] = params["from"]
            if "to" in params:
                query["to"] = params["to"]
            return "/treasury", query
        if capability == "social_sentiment":
            query["symbol"] = symbol
            if "page" in params:
                query["page"] = params["page"]
            return "/historical/social-sentiment", query
        if capability == "macro_indicator":
            query["name"] = params.get("indicator") or params.get("name") or "GDP"
            if "from" in params:
                query["from"] = params["from"]
            if "to" in params:
                query["to"] = params["to"]
            return "/economic", query
        # Unreachable: capability membership checked in fetch().
        raise DataNotAvailable(  # pragma: no cover
            provider_kind=self.kind,
            capability=capability,
            reason="internal routing bug",
        )

    async def _get_json(
        self,
        capability: str,
        path: str,
        query: dict[str, Any],
    ) -> dict[str, Any] | list[Any]:
        params = dict(query)
        params["apikey"] = self.entry.api_key or ""
        base = self._v4_base_url if capability in _V4_CAPABILITIES else self._v3_base_url
        url = f"{base}{path}"

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
                payload = resp.json()
            except ValueError as exc:
                raise DataSourceError(
                    provider_kind=self.kind,
                    status_code=200,
                    detail=f"malformed json: {exc}",
                ) from exc
            # FMP frequently returns an empty list when an unknown symbol is
            # queried (instead of a 404). Surface that as DataNotAvailable so
            # the dispatch layer can tell the LLM "no data" rather than feed
            # it an empty list as if the data simply did not exist yet.
            if isinstance(payload, list) and len(payload) == 0:
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason="empty response (symbol unknown or no data)",
                )
            return payload
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


def _derive_base_urls(
    base_url: str,
    v3_override: Any,
    v4_override: Any,
) -> tuple[str, str]:
    """Resolve v3 and v4 base URLs from a single configured base_url.

    Admins typically configure one URL pointing at `/api/v3`. We strip the
    trailing version segment and re-attach the right one for each capability,
    falling back to the public defaults when stripping leaves nothing useful.
    """
    base = base_url.rstrip("/")
    if base.endswith("/api/v3"):
        root = base[: -len("/api/v3")]
    elif base.endswith("/api/v4"):
        root = base[: -len("/api/v4")]
    else:
        root = base
    v3 = str(v3_override).rstrip("/") if v3_override else f"{root}/api/v3"
    v4 = str(v4_override).rstrip("/") if v4_override else f"{root}/api/v4"
    return v3, v4


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


# Re-export defaults for callers/tests that need them.
__all__ = ["_DEFAULT_V3", "_DEFAULT_V4", "FMPAdapter", "_parse_retry_after"]
