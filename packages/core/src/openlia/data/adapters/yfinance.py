"""Yahoo Finance adapter — keyless financial provider.

Hits Yahoo's public unauthenticated endpoints (the same ones the python
`yfinance` package wraps: query1.finance.yahoo.com / query2.finance.yahoo.com).

Capabilities and Yahoo endpoints:
    stock_quote            GET /v7/finance/quote?symbols={symbol}
    historical_prices      GET /v8/finance/chart/{symbol}
    company_profile        GET /v10/finance/quoteSummary/{symbol}
                                ?modules=assetProfile,summaryDetail,price
    financial_statements   GET /v10/finance/quoteSummary/{symbol}
                                ?modules=incomeStatementHistory,
                                         balanceSheetHistory,
                                         cashflowStatementHistory
    company_news           GET /v1/finance/search?q={symbol}&newsCount=N
    stock_grade            GET /v10/finance/quoteSummary/{symbol}
                                ?modules=upgradeDowngradeHistory,recommendationTrend
    insider_transactions   GET /v10/finance/quoteSummary/{symbol}
                                ?modules=insiderTransactions
    earnings               GET /v10/finance/quoteSummary/{symbol}
                                ?modules=earningsHistory,earningsTrend,calendarEvents
    options_chain          GET /v7/finance/options/{symbol}
    market_movers          GET /v1/finance/trending/{region}
    etf_holdings           GET /v10/finance/quoteSummary/{symbol}?modules=topHoldings
    peers                  GET /v6/finance/recommendationsbysymbol/{symbol}

Authentication: Yahoo's public API does not require an API key; `api_key`
is allowed to be None. A browser-like User-Agent is mandatory because
Yahoo otherwise returns 403.
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

_REQUEST_TIMEOUT_SECONDS = 30.0
_USER_AGENT = "Mozilla/5.0 (compatible; OpenLIA/1.0)"
_DEFAULT_BASE_URL = "https://query1.finance.yahoo.com"

_QUOTE_SUMMARY_MODULES: dict[str, tuple[str, ...]] = {
    "company_profile": ("assetProfile", "summaryDetail", "price"),
    "financial_statements": (
        "incomeStatementHistory",
        "balanceSheetHistory",
        "cashflowStatementHistory",
    ),
    "stock_grade": ("upgradeDowngradeHistory", "recommendationTrend"),
    "insider_transactions": ("insiderTransactions",),
    "earnings": ("earningsHistory", "earningsTrend", "calendarEvents"),
    "etf_holdings": ("topHoldings",),
}


class YFinanceAdapter(ProviderAdapter):
    """Yahoo Finance keyless financial-data adapter."""

    kind: ClassVar[str] = "yfinance"
    category: ClassVar[ProviderCategory] = ProviderCategory.FINANCIAL
    capabilities: ClassVar[frozenset[str]] = frozenset(
        {
            "stock_quote",
            "historical_prices",
            "company_profile",
            "financial_statements",
            "company_news",
            "stock_grade",
            "insider_transactions",
            "earnings",
            "options_chain",
            "market_movers",
            "etf_holdings",
            "peers",
        }
    )

    def __init__(self, entry: ProviderEntry) -> None:
        super().__init__(entry)
        self._base_url = (entry.base_url or _DEFAULT_BASE_URL).rstrip("/")

    async def fetch(
        self,
        capability: str,
        params: dict[str, Any],
    ) -> ToolResult:
        if capability not in self.capabilities:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason=f"capability {capability!r} not declared by yfinance",
            )

        if capability == "market_movers":
            region = str(params.get("region", "US")).upper()
            payload = await self._get_json(
                f"/v1/finance/trending/{region}",
                {"count": params.get("count", 25)},
            )
            return ToolResult(provider_kind=self.kind, capability=capability, payload=payload)

        symbol = params.get("symbol")
        if not symbol:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason="`symbol` parameter is required",
            )
        ticker = str(symbol).upper()

        if capability == "stock_quote":
            payload = await self._get_json("/v7/finance/quote", {"symbols": ticker})
        elif capability == "historical_prices":
            query: dict[str, Any] = {
                "interval": params.get("interval", "1d"),
                "range": params.get("range", "1y"),
            }
            if "period1" in params:
                query["period1"] = params["period1"]
            if "period2" in params:
                query["period2"] = params["period2"]
            payload = await self._get_json(f"/v8/finance/chart/{ticker}", query)
        elif capability == "company_news":
            payload = await self._get_json(
                "/v1/finance/search",
                {"q": ticker, "newsCount": params.get("limit", 20)},
            )
        elif capability == "options_chain":
            query = {}
            if "date" in params:
                query["date"] = params["date"]
            payload = await self._get_json(f"/v7/finance/options/{ticker}", query)
        elif capability == "peers":
            payload = await self._get_json(f"/v6/finance/recommendationsbysymbol/{ticker}", {})
        elif capability in _QUOTE_SUMMARY_MODULES:
            payload = await self._fetch_quote_summary(ticker, _QUOTE_SUMMARY_MODULES[capability])
        else:  # pragma: no cover - guarded by capabilities check above
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
            await self._get_json("/v7/finance/quote", {"symbols": "AAPL"})
        except (
            DataNotAvailable,
            RateLimitError,
            DataSourceError,
            AuthenticationError,
            httpx.HTTPError,
        ):
            return False
        return True

    async def _fetch_quote_summary(
        self,
        ticker: str,
        modules: tuple[str, ...],
    ) -> dict[str, Any] | list[Any]:
        return await self._get_json(
            f"/v10/finance/quoteSummary/{ticker}",
            {"modules": ",".join(modules)},
        )

    async def _get_json(
        self,
        path: str,
        query: dict[str, Any],
    ) -> dict[str, Any] | list[Any]:
        url = f"{self._base_url}{path}"
        headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}

        async def _send() -> httpx.Response:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                return await client.get(url, params=query, headers=headers)

        def _classify_rate_limit(resp: httpx.Response) -> int | None:
            if resp.status_code != 429:
                return None
            ra = resp.headers.get("Retry-After")
            try:
                return max(0, int(ra)) if ra is not None else -1
            except ValueError:
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
                capability=path.strip("/").split("/")[-1] or "unknown",
                reason=resp.text.strip()[:200] or "not found",
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
