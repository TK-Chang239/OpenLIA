"""EODHD adapter — the default financial provider.

Covers four capabilities in Plan 3:
    stock_quote          GET /real-time/{ticker}.US
    historical_prices    GET /eod/{ticker}.US
    company_profile      GET /fundamentals/{ticker}.US (General block)
    company_news         GET /news?s={ticker}.US

Authentication: `?api_token=<key>` query param (EODHD's documented auth
method). We pass the key on every request.

Symbol convention: EODHD requires `{SYMBOL}.{EXCHANGE}` (e.g. AAPL.US).
For Plan 3 we hard-code the `.US` suffix — multi-exchange support is a
later enhancement.
"""

from typing import Any, ClassVar

import httpx

from openlia.data.base import ProviderAdapter
from openlia.data.errors import DataNotAvailable, DataSourceError, RateLimitError
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
        }
    )

    def __init__(self, entry: ProviderEntry) -> None:
        super().__init__(entry)
        assert entry.base_url is not None
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
        else:  # pragma: no cover - guarded above
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason="internal routing bug",
            )

        payload = await self._get_json(path, query)
        return ToolResult(
            provider_kind=self.kind,
            capability=capability,
            payload=payload,
        )

    async def health_check(self) -> bool:
        try:
            await self._get_json(_HEALTH_CHECK_PATH, {})
        except (DataNotAvailable, RateLimitError, DataSourceError, httpx.HTTPError):
            return False
        return True

    def _format_ticker(self, symbol: str) -> str:
        if "." in symbol:
            return symbol.upper()
        return f"{symbol.upper()}.US"

    async def _get_json(
        self,
        path: str,
        query: dict[str, Any],
    ) -> dict[str, Any] | list[Any]:
        params = dict(query)
        params["api_token"] = self.entry.api_key or ""
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
            try:
                resp = await client.get(url, params=params)
            except httpx.HTTPError as exc:
                raise DataSourceError(
                    provider_kind=self.kind,
                    detail=str(exc),
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
        if resp.status_code == 429:
            retry_after = _parse_retry_after(resp.headers.get("Retry-After"))
            raise RateLimitError(
                provider_kind=self.kind,
                retry_after_seconds=retry_after,
            )
        raise DataSourceError(
            provider_kind=self.kind,
            status_code=resp.status_code,
            detail=resp.text[:500],
        )


def _parse_retry_after(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
