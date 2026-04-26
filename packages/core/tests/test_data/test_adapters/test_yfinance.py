import httpx
import pytest
import respx
from openlia.data.adapters.yfinance import YFinanceAdapter
from openlia.data.errors import (
    AuthenticationError,
    DataNotAvailable,
    DataSourceError,
    RateLimitError,
)
from openlia.data.types import ProviderCategory, ProviderEntry, ProviderMode

_BASE = "https://query1.finance.yahoo.com"


def _entry(api_key: str | None = None) -> ProviderEntry:
    return ProviderEntry(
        id="00000000-0000-0000-0000-0000000000aa",
        kind="yfinance",
        label="Yahoo Finance",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key=api_key,
        base_url=_BASE,
    )


def test_yfinance_declared_metadata() -> None:
    assert YFinanceAdapter.kind == "yfinance"
    assert YFinanceAdapter.category is ProviderCategory.FINANCIAL
    expected = {
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
    assert expected <= YFinanceAdapter.capabilities


def test_constructor_accepts_none_api_key() -> None:
    adapter = YFinanceAdapter(_entry(api_key=None))
    assert adapter.entry.api_key is None


async def test_fetch_rejects_unknown_capability() -> None:
    adapter = YFinanceAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("forex_quote", {"symbol": "EURUSD=X"})
    assert exc.value.provider_kind == "yfinance"
    assert exc.value.capability == "forex_quote"


async def test_fetch_missing_required_symbol_param() -> None:
    adapter = YFinanceAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("stock_quote", {})
    assert "symbol" in exc.value.reason


@respx.mock
async def test_fetch_stock_quote_success_sets_user_agent() -> None:
    route = respx.get(f"{_BASE}/v7/finance/quote").mock(
        return_value=httpx.Response(
            200,
            json={
                "quoteResponse": {
                    "result": [{"symbol": "AAPL", "regularMarketPrice": 225.1}],
                    "error": None,
                }
            },
        )
    )
    adapter = YFinanceAdapter(_entry())
    result = await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert route.called
    assert result.provider_kind == "yfinance"
    assert result.capability == "stock_quote"
    assert "symbols=AAPL" in str(route.calls[0].request.url)
    ua = route.calls[0].request.headers.get("user-agent", "")
    assert "OpenLIA" in ua


@respx.mock
async def test_fetch_historical_prices_uses_chart_endpoint() -> None:
    route = respx.get(f"{_BASE}/v8/finance/chart/MSFT").mock(
        return_value=httpx.Response(
            200,
            json={"chart": {"result": [{"meta": {"symbol": "MSFT"}}], "error": None}},
        )
    )
    adapter = YFinanceAdapter(_entry())
    result = await adapter.fetch(
        "historical_prices",
        {"symbol": "MSFT", "interval": "1d", "range": "5y"},
    )
    assert route.called
    assert "interval=1d" in str(route.calls[0].request.url)
    assert "range=5y" in str(route.calls[0].request.url)
    assert "chart" in result.payload


@respx.mock
async def test_fetch_company_profile_uses_quote_summary_modules() -> None:
    route = respx.get(f"{_BASE}/v10/finance/quoteSummary/AAPL").mock(
        return_value=httpx.Response(
            200,
            json={"quoteSummary": {"result": [{"price": {"symbol": "AAPL"}}], "error": None}},
        )
    )
    adapter = YFinanceAdapter(_entry())
    result = await adapter.fetch("company_profile", {"symbol": "AAPL"})
    assert route.called
    url = str(route.calls[0].request.url)
    assert "modules=" in url
    assert "assetProfile" in url
    assert "summaryDetail" in url
    assert "price" in url
    assert result.capability == "company_profile"


@respx.mock
async def test_fetch_company_news_uses_search_endpoint() -> None:
    route = respx.get(f"{_BASE}/v1/finance/search").mock(
        return_value=httpx.Response(200, json={"news": [{"title": "AAPL beats earnings"}]})
    )
    adapter = YFinanceAdapter(_entry())
    result = await adapter.fetch("company_news", {"symbol": "AAPL", "limit": 10})
    assert route.called
    url = str(route.calls[0].request.url)
    assert "q=AAPL" in url
    assert "newsCount=10" in url
    assert "news" in result.payload


@respx.mock
async def test_fetch_market_movers_does_not_require_symbol() -> None:
    route = respx.get(f"{_BASE}/v1/finance/trending/US").mock(
        return_value=httpx.Response(200, json={"finance": {"result": [{"quotes": []}]}})
    )
    adapter = YFinanceAdapter(_entry())
    result = await adapter.fetch("market_movers", {})
    assert route.called
    assert result.capability == "market_movers"


@respx.mock
async def test_401_raises_authentication_error() -> None:
    respx.get(f"{_BASE}/v7/finance/quote").mock(
        return_value=httpx.Response(401, text="unauthorized"),
    )
    adapter = YFinanceAdapter(_entry())
    with pytest.raises(AuthenticationError) as exc:
        await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert exc.value.status_code == 401


@respx.mock
async def test_404_maps_to_data_not_available() -> None:
    respx.get(f"{_BASE}/v7/finance/quote").mock(
        return_value=httpx.Response(404, text="symbol not found"),
    )
    adapter = YFinanceAdapter(_entry())
    with pytest.raises(DataNotAvailable):
        await adapter.fetch("stock_quote", {"symbol": "ZZZZ"})


@respx.mock
async def test_429_after_retries_raises_rate_limit_error() -> None:
    route = respx.get(f"{_BASE}/v7/finance/quote").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "0"}, text="throttled")
    )
    adapter = YFinanceAdapter(_entry())
    with pytest.raises(RateLimitError):
        await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert route.call_count >= 2


@respx.mock
async def test_500_maps_to_transient_data_source_error() -> None:
    respx.get(f"{_BASE}/v7/finance/quote").mock(
        return_value=httpx.Response(500, text="boom"),
    )
    adapter = YFinanceAdapter(_entry())
    with pytest.raises(DataSourceError) as exc:
        await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert exc.value.status_code == 500
    assert exc.value.is_transient is True


@respx.mock
async def test_health_check_returns_true_on_200() -> None:
    respx.get(f"{_BASE}/v7/finance/quote").mock(
        return_value=httpx.Response(
            200,
            json={"quoteResponse": {"result": [], "error": None}},
        )
    )
    adapter = YFinanceAdapter(_entry())
    assert await adapter.health_check() is True


@respx.mock
async def test_health_check_returns_false_on_5xx() -> None:
    respx.get(f"{_BASE}/v7/finance/quote").mock(
        return_value=httpx.Response(503, text="down"),
    )
    adapter = YFinanceAdapter(_entry())
    assert await adapter.health_check() is False
