import httpx
import pytest
import respx
from openlia.data.adapters.finnhub import FinnhubAdapter
from openlia.data.errors import (
    AuthenticationError,
    DataNotAvailable,
    DataSourceError,
    RateLimitError,
)
from openlia.data.types import ProviderCategory, ProviderEntry, ProviderMode


def _entry(base_url: str = "https://finnhub.io/api/v1") -> ProviderEntry:
    return ProviderEntry(
        id="00000000-0000-0000-0000-00000000fnhb",
        kind="finnhub",
        label="Finnhub",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="TEST-KEY",
        base_url=base_url,
    )


def test_finnhub_declared_metadata() -> None:
    assert FinnhubAdapter.kind == "finnhub"
    assert FinnhubAdapter.category is ProviderCategory.FINANCIAL
    expected = {
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
    assert expected <= FinnhubAdapter.capabilities


async def test_fetch_rejects_unknown_capability() -> None:
    adapter = FinnhubAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("nonexistent_capability", {"symbol": "AAPL"})
    assert exc.value.provider_kind == "finnhub"
    assert exc.value.capability == "nonexistent_capability"


@respx.mock
async def test_fetch_stock_quote_success_uses_header_auth() -> None:
    route = respx.get("https://finnhub.io/api/v1/quote").mock(
        return_value=httpx.Response(
            200,
            json={"c": 225.1, "h": 226.0, "l": 220.0, "o": 222.0, "pc": 221.0, "t": 1714000000},
        )
    )
    adapter = FinnhubAdapter(_entry())
    result = await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert route.called
    assert result.provider_kind == "finnhub"
    assert result.capability == "stock_quote"
    assert result.payload["c"] == 225.1
    req = route.calls[0].request
    assert req.headers.get("X-Finnhub-Token") == "TEST-KEY"
    assert "symbol=AAPL" in str(req.url)
    # api key must NOT be in the query string
    assert "token=" not in str(req.url)


@respx.mock
async def test_fetch_company_profile_success() -> None:
    route = respx.get("https://finnhub.io/api/v1/stock/profile2").mock(
        return_value=httpx.Response(
            200,
            json={"name": "Apple Inc", "ticker": "AAPL", "exchange": "NASDAQ"},
        )
    )
    adapter = FinnhubAdapter(_entry())
    result = await adapter.fetch("company_profile", {"symbol": "AAPL"})
    assert route.called
    assert result.payload["name"] == "Apple Inc"


@respx.mock
async def test_fetch_historical_prices_success() -> None:
    route = respx.get("https://finnhub.io/api/v1/stock/candle").mock(
        return_value=httpx.Response(
            200,
            json={
                "c": [225.1, 226.0],
                "h": [226.0, 227.0],
                "l": [224.0, 225.0],
                "o": [225.0, 226.0],
                "t": [1714000000, 1714086400],
                "v": [10000, 11000],
                "s": "ok",
            },
        )
    )
    adapter = FinnhubAdapter(_entry())
    result = await adapter.fetch(
        "historical_prices",
        {"symbol": "MSFT", "from": 1713000000, "to": 1714000000, "resolution": "D"},
    )
    assert route.called
    assert result.payload["s"] == "ok"
    url = str(route.calls[0].request.url)
    assert "symbol=MSFT" in url
    assert "resolution=D" in url
    assert "from=1713000000" in url
    assert "to=1714000000" in url


@respx.mock
async def test_fetch_insider_transactions_success() -> None:
    route = respx.get("https://finnhub.io/api/v1/stock/insider-transactions").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"name": "Cook Tim", "share": 100, "transactionDate": "2026-01-01"}]},
        )
    )
    adapter = FinnhubAdapter(_entry())
    result = await adapter.fetch("insider_transactions", {"symbol": "AAPL"})
    assert route.called
    assert isinstance(result.payload, dict)
    assert result.payload["data"][0]["name"] == "Cook Tim"


async def test_fetch_historical_prices_missing_required_param() -> None:
    adapter = FinnhubAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("historical_prices", {"symbol": "AAPL"})
    assert "from" in exc.value.reason or "to" in exc.value.reason


async def test_fetch_stock_quote_missing_symbol() -> None:
    adapter = FinnhubAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("stock_quote", {})
    assert "symbol" in exc.value.reason


@respx.mock
async def test_401_raises_authentication_error() -> None:
    respx.get("https://finnhub.io/api/v1/quote").mock(
        return_value=httpx.Response(401, text="invalid api key"),
    )
    adapter = FinnhubAdapter(_entry())
    with pytest.raises(AuthenticationError) as exc:
        await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert exc.value.status_code == 401


@respx.mock
async def test_403_raises_authentication_error() -> None:
    respx.get("https://finnhub.io/api/v1/quote").mock(
        return_value=httpx.Response(403, text="forbidden"),
    )
    adapter = FinnhubAdapter(_entry())
    with pytest.raises(AuthenticationError) as exc:
        await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert exc.value.status_code == 403


@respx.mock
async def test_404_maps_to_data_not_available() -> None:
    respx.get("https://finnhub.io/api/v1/quote").mock(
        return_value=httpx.Response(404, text="not found"),
    )
    adapter = FinnhubAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("stock_quote", {"symbol": "ZZZZ"})
    assert exc.value.provider_kind == "finnhub"
    assert exc.value.capability == "stock_quote"


@respx.mock
async def test_429_retries_and_raises_rate_limit_error() -> None:
    route = respx.get("https://finnhub.io/api/v1/quote").mock(
        return_value=httpx.Response(429, text="too many requests"),
    )
    adapter = FinnhubAdapter(_entry())
    with pytest.raises(RateLimitError) as exc:
        await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    # exhausted all attempts
    assert route.call_count == 3
    # Finnhub does not send Retry-After, so retry_after_seconds must be None.
    assert exc.value.retry_after_seconds is None


@respx.mock
async def test_500_maps_to_transient_data_source_error() -> None:
    respx.get("https://finnhub.io/api/v1/quote").mock(
        return_value=httpx.Response(500, text="boom"),
    )
    adapter = FinnhubAdapter(_entry())
    with pytest.raises(DataSourceError) as exc:
        await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert exc.value.status_code == 500
    assert exc.value.is_transient is True


@respx.mock
async def test_health_check_returns_true_on_200() -> None:
    respx.get("https://finnhub.io/api/v1/quote").mock(
        return_value=httpx.Response(200, json={"c": 1.0}),
    )
    adapter = FinnhubAdapter(_entry())
    assert await adapter.health_check() is True


@respx.mock
async def test_health_check_returns_false_on_401() -> None:
    respx.get("https://finnhub.io/api/v1/quote").mock(
        return_value=httpx.Response(401, text="bad key"),
    )
    adapter = FinnhubAdapter(_entry())
    assert await adapter.health_check() is False


@respx.mock
async def test_health_check_returns_false_on_network_error() -> None:
    respx.get("https://finnhub.io/api/v1/quote").mock(
        side_effect=httpx.ConnectError("boom"),
    )
    adapter = FinnhubAdapter(_entry())
    assert await adapter.health_check() is False


@respx.mock
async def test_fetch_market_news_success() -> None:
    route = respx.get("https://finnhub.io/api/v1/news").mock(
        return_value=httpx.Response(200, json=[{"headline": "Big news"}]),
    )
    adapter = FinnhubAdapter(_entry())
    result = await adapter.fetch("market_news", {"category": "general"})
    assert route.called
    assert isinstance(result.payload, list)
    assert "category=general" in str(route.calls[0].request.url)


@respx.mock
async def test_fetch_peers_success() -> None:
    respx.get("https://finnhub.io/api/v1/stock/peers").mock(
        return_value=httpx.Response(200, json=["MSFT", "GOOGL", "AMZN"]),
    )
    adapter = FinnhubAdapter(_entry())
    result = await adapter.fetch("peers", {"symbol": "AAPL"})
    assert isinstance(result.payload, list)
    assert "MSFT" in result.payload


@respx.mock
async def test_fetch_economic_events_no_required_params() -> None:
    respx.get("https://finnhub.io/api/v1/calendar/economic").mock(
        return_value=httpx.Response(200, json={"economicCalendar": []}),
    )
    adapter = FinnhubAdapter(_entry())
    result = await adapter.fetch("economic_events", {})
    assert "economicCalendar" in result.payload
