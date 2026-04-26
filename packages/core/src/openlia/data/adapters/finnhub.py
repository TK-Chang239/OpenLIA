"""Finnhub adapter — multi-capability financial provider.

Capabilities mapped to Finnhub REST endpoints:
    stock_quote                GET /quote?symbol=
    historical_prices          GET /stock/candle?symbol=&resolution=&from=&to=
    company_profile            GET /stock/profile2?symbol=
    company_news               GET /company-news?symbol=&from=&to=
    financial_statements       GET /stock/metric?symbol=&metric=all
    stock_grade                GET /stock/recommendation?symbol=
    price_target               GET /stock/price-target?symbol=
    upgrades_downgrades        GET /stock/upgrade-downgrade?symbol=
    insider_transactions       GET /stock/insider-transactions?symbol=
    insider_sentiment          GET /stock/insider-sentiment?symbol=&from=&to=
    earnings_surprises         GET /stock/earnings?symbol=
    earnings_estimate          GET /stock/eps-estimate?symbol=
    earnings_data              GET /calendar/earnings?from=&to=&symbol=
    dividends                  GET /stock/dividend?symbol=&from=&to=
    splits                     GET /stock/split?symbol=&from=&to=
    ipo_calendar               GET /calendar/ipo?from=&to=
    economic_events            GET /calendar/economic
    social_sentiment           GET /stock/social-sentiment?symbol=
    market_news                GET /news?category=
    forex_quote                GET /forex/rates?base=
    crypto_quote               GET /crypto/candle?symbol=&resolution=&from=&to=
    etf_holdings               GET /etf/holdings?symbol=
    etf_profile                GET /etf/profile?symbol=
    sec_filings                GET /stock/filings?symbol=
    transcripts                GET /stock/transcripts?symbol=
    peers                      GET /stock/peers?symbol=
    earnings_call_transcripts  GET /stock/transcripts?id=

Authentication: header `X-Finnhub-Token: <key>` on every request.

Rate-limit handling: Finnhub does not include `Retry-After` on 429s, so the
classifier returns -1 to signal "use base exponential backoff".
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

_HEALTH_CHECK_PATH = "/quote"
_HEALTH_CHECK_PARAMS: dict[str, Any] = {"symbol": "AAPL"}
_REQUEST_TIMEOUT_SECONDS = 30.0
_AUTH_HEADER = "X-Finnhub-Token"


class FinnhubAdapter(ProviderAdapter):
    """Finnhub financial-data adapter."""

    kind: ClassVar[str] = "finnhub"
    category: ClassVar[ProviderCategory] = ProviderCategory.FINANCIAL
    capabilities: ClassVar[frozenset[str]] = frozenset(
        {
            "stock_quote",
            "historical_prices",
            "company_profile",
            "company_news",
            "financial_statements",
            "stock_grade",
            "price_target",
            "upgrades_downgrades",
            "insider_transactions",
            "insider_sentiment",
            "earnings_surprises",
            "earnings_estimate",
            "earnings_data",
            "dividends",
            "splits",
            "ipo_calendar",
            "economic_events",
            "social_sentiment",
            "market_news",
            "forex_quote",
            "crypto_quote",
            "etf_holdings",
            "etf_profile",
            "sec_filings",
            "transcripts",
            "peers",
            "earnings_call_transcripts",
        }
    )

    def __init__(self, entry: ProviderEntry) -> None:
        super().__init__(entry)
        if entry.base_url is None:
            raise ValueError("finnhub requires base_url")
        self._base_url = entry.base_url.rstrip("/")
        self._default_resolution = str(entry.extra_config.get("resolution", "D"))

    async def fetch(
        self,
        capability: str,
        params: dict[str, Any],
    ) -> ToolResult:
        if capability not in self.capabilities:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason=f"capability {capability!r} not declared by finnhub",
            )

        path, query = self._route(capability, params)
        payload = await self._get_json(path, query, capability=capability)
        return ToolResult(
            provider_kind=self.kind,
            capability=capability,
            payload=payload,
        )

    async def health_check(self) -> bool:
        try:
            await self._get_json(
                _HEALTH_CHECK_PATH,
                dict(_HEALTH_CHECK_PARAMS),
                capability="health_check",
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

    def _route(
        self,
        capability: str,
        params: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        symbol = params.get("symbol")

        if capability == "stock_quote":
            self._require(capability, params, "symbol")
            return "/quote", {"symbol": str(symbol).upper()}

        if capability == "historical_prices":
            self._require(capability, params, "symbol", "from", "to")
            return "/stock/candle", {
                "symbol": str(symbol).upper(),
                "resolution": str(params.get("resolution", self._default_resolution)),
                "from": params["from"],
                "to": params["to"],
            }

        if capability == "company_profile":
            self._require(capability, params, "symbol")
            return "/stock/profile2", {"symbol": str(symbol).upper()}

        if capability == "company_news":
            self._require(capability, params, "symbol", "from", "to")
            return "/company-news", {
                "symbol": str(symbol).upper(),
                "from": params["from"],
                "to": params["to"],
            }

        if capability == "financial_statements":
            self._require(capability, params, "symbol")
            return "/stock/metric", {
                "symbol": str(symbol).upper(),
                "metric": str(params.get("metric", "all")),
            }

        if capability == "stock_grade":
            self._require(capability, params, "symbol")
            return "/stock/recommendation", {"symbol": str(symbol).upper()}

        if capability == "price_target":
            self._require(capability, params, "symbol")
            return "/stock/price-target", {"symbol": str(symbol).upper()}

        if capability == "upgrades_downgrades":
            self._require(capability, params, "symbol")
            return "/stock/upgrade-downgrade", {"symbol": str(symbol).upper()}

        if capability == "insider_transactions":
            self._require(capability, params, "symbol")
            query: dict[str, Any] = {"symbol": str(symbol).upper()}
            if "from" in params:
                query["from"] = params["from"]
            if "to" in params:
                query["to"] = params["to"]
            return "/stock/insider-transactions", query

        if capability == "insider_sentiment":
            self._require(capability, params, "symbol", "from", "to")
            return "/stock/insider-sentiment", {
                "symbol": str(symbol).upper(),
                "from": params["from"],
                "to": params["to"],
            }

        if capability == "earnings_surprises":
            self._require(capability, params, "symbol")
            query = {"symbol": str(symbol).upper()}
            if "limit" in params:
                query["limit"] = params["limit"]
            return "/stock/earnings", query

        if capability == "earnings_estimate":
            self._require(capability, params, "symbol")
            query = {"symbol": str(symbol).upper()}
            if "freq" in params:
                query["freq"] = params["freq"]
            return "/stock/eps-estimate", query

        if capability == "earnings_data":
            query = {}
            if "from" in params:
                query["from"] = params["from"]
            if "to" in params:
                query["to"] = params["to"]
            if "symbol" in params:
                query["symbol"] = str(params["symbol"]).upper()
            return "/calendar/earnings", query

        if capability == "dividends":
            self._require(capability, params, "symbol", "from", "to")
            return "/stock/dividend", {
                "symbol": str(symbol).upper(),
                "from": params["from"],
                "to": params["to"],
            }

        if capability == "splits":
            self._require(capability, params, "symbol", "from", "to")
            return "/stock/split", {
                "symbol": str(symbol).upper(),
                "from": params["from"],
                "to": params["to"],
            }

        if capability == "ipo_calendar":
            self._require(capability, params, "from", "to")
            return "/calendar/ipo", {"from": params["from"], "to": params["to"]}

        if capability == "economic_events":
            return "/calendar/economic", {}

        if capability == "social_sentiment":
            self._require(capability, params, "symbol")
            query = {"symbol": str(symbol).upper()}
            if "from" in params:
                query["from"] = params["from"]
            if "to" in params:
                query["to"] = params["to"]
            return "/stock/social-sentiment", query

        if capability == "market_news":
            return "/news", {"category": str(params.get("category", "general"))}

        if capability == "forex_quote":
            return "/forex/rates", {"base": str(params.get("base", "USD")).upper()}

        if capability == "crypto_quote":
            self._require(capability, params, "symbol", "from", "to")
            return "/crypto/candle", {
                "symbol": str(symbol).upper(),
                "resolution": str(params.get("resolution", self._default_resolution)),
                "from": params["from"],
                "to": params["to"],
            }

        if capability == "etf_holdings":
            self._require(capability, params, "symbol")
            return "/etf/holdings", {"symbol": str(symbol).upper()}

        if capability == "etf_profile":
            self._require(capability, params, "symbol")
            return "/etf/profile", {"symbol": str(symbol).upper()}

        if capability == "sec_filings":
            self._require(capability, params, "symbol")
            query = {"symbol": str(symbol).upper()}
            if "from" in params:
                query["from"] = params["from"]
            if "to" in params:
                query["to"] = params["to"]
            return "/stock/filings", query

        if capability == "transcripts":
            self._require(capability, params, "symbol")
            return "/stock/transcripts", {"symbol": str(symbol).upper()}

        if capability == "peers":
            self._require(capability, params, "symbol")
            return "/stock/peers", {"symbol": str(symbol).upper()}

        if capability == "earnings_call_transcripts":
            self._require(capability, params, "id")
            return "/stock/transcripts", {"id": params["id"]}

        # Should be unreachable given the capability gate above.
        raise DataNotAvailable(  # pragma: no cover
            provider_kind=self.kind,
            capability=capability,
            reason="internal routing bug",
        )

    def _require(
        self,
        capability: str,
        params: dict[str, Any],
        *names: str,
    ) -> None:
        for name in names:
            if name not in params or params[name] in (None, ""):
                raise DataNotAvailable(
                    provider_kind=self.kind,
                    capability=capability,
                    reason=f"`{name}` parameter is required",
                )

    async def _get_json(
        self,
        path: str,
        query: dict[str, Any],
        *,
        capability: str,
    ) -> dict[str, Any] | list[Any]:
        url = f"{self._base_url}{path}"
        headers = {_AUTH_HEADER: self.entry.api_key or ""}

        async def _send() -> httpx.Response:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                return await client.get(url, params=query, headers=headers)

        def _classify_rate_limit(resp: httpx.Response) -> int | None:
            if resp.status_code != 429:
                return None
            return -1

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
