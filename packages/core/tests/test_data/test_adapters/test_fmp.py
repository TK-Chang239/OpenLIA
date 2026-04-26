from datetime import UTC

import httpx
import pytest
import respx
from openlia.data.adapters.fmp import FMPAdapter
from openlia.data.errors import (
    AuthenticationError,
    DataNotAvailable,
    DataSourceError,
    RateLimitError,
)
from openlia.data.types import ProviderCategory, ProviderEntry, ProviderMode

_V3 = "https://financialmodelingprep.com/api/v3"
_V4 = "https://financialmodelingprep.com/api/v4"


def _entry(base_url: str = _V3, **extra: object) -> ProviderEntry:
    return ProviderEntry(
        id="00000000-0000-0000-0000-000000000010",
        kind="fmp",
        label="FMP",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="TEST-KEY",
        base_url=base_url,
        extra_config=extra or {},
    )


def test_fmp_declared_metadata() -> None:
    assert FMPAdapter.kind == "fmp"
    assert FMPAdapter.category is ProviderCategory.FINANCIAL
    expected_subset = {
        "stock_quote",
        "historical_prices",
        "company_profile",
        "company_news",
        "financial_statements",
        "stock_grade",
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
    }
    assert expected_subset <= FMPAdapter.capabilities


def test_fmp_requires_base_url() -> None:
    # ProviderEntry validator catches the missing base_url before we get here,
    # but the adapter constructor still defends against a None slipping in.
    with pytest.raises(ValueError):
        ProviderEntry(
            id="00000000-0000-0000-0000-000000000099",
            kind="fmp",
            label="FMP",
            category=ProviderCategory.FINANCIAL,
            mode=ProviderMode.API_KEY,
            api_key="K",
            base_url=None,
        )


async def test_fetch_rejects_unknown_capability() -> None:
    adapter = FMPAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("not_a_capability", {"symbol": "AAPL"})
    assert exc.value.provider_kind == "fmp"
    assert exc.value.capability == "not_a_capability"


async def test_fetch_missing_symbol_param() -> None:
    adapter = FMPAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("stock_quote", {})
    assert "symbol" in exc.value.reason


@respx.mock
async def test_fetch_stock_quote_success() -> None:
    route = respx.get(f"{_V3}/quote/AAPL").mock(
        return_value=httpx.Response(
            200,
            json=[{"symbol": "AAPL", "price": 225.1, "volume": 10_000_000}],
        )
    )
    adapter = FMPAdapter(_entry())
    result = await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert route.called
    assert result.provider_kind == "fmp"
    assert result.capability == "stock_quote"
    assert result.payload[0]["price"] == 225.1
    assert "apikey=TEST-KEY" in str(route.calls[0].request.url)


@respx.mock
async def test_fetch_historical_prices_passes_date_range() -> None:
    route = respx.get(f"{_V3}/historical-price-full/MSFT").mock(
        return_value=httpx.Response(
            200,
            json={"symbol": "MSFT", "historical": [{"date": "2026-04-10", "close": 400.0}]},
        )
    )
    adapter = FMPAdapter(_entry())
    result = await adapter.fetch(
        "historical_prices",
        {"symbol": "MSFT", "from": "2025-01-01", "to": "2026-01-01"},
    )
    assert route.called
    url = str(route.calls[0].request.url)
    assert "from=2025-01-01" in url
    assert "to=2026-01-01" in url
    assert isinstance(result.payload, dict)


@respx.mock
async def test_fetch_company_news_uses_tickers_param() -> None:
    route = respx.get(f"{_V3}/stock_news").mock(
        return_value=httpx.Response(
            200,
            json=[{"title": "Big news", "symbol": "AAPL"}],
        )
    )
    adapter = FMPAdapter(_entry())
    result = await adapter.fetch("company_news", {"symbol": "AAPL"})
    assert route.called
    url = str(route.calls[0].request.url)
    assert "tickers=AAPL" in url
    assert result.payload[0]["title"] == "Big news"


@respx.mock
async def test_fetch_insider_transactions_routes_to_v4() -> None:
    route = respx.get(f"{_V4}/insider-trading").mock(
        return_value=httpx.Response(
            200,
            json=[{"symbol": "AAPL", "transactionType": "S-Sale"}],
        )
    )
    adapter = FMPAdapter(_entry())
    result = await adapter.fetch("insider_transactions", {"symbol": "AAPL"})
    assert route.called
    url = str(route.calls[0].request.url)
    assert "/api/v4/insider-trading" in url
    assert "symbol=AAPL" in url
    assert result.payload[0]["transactionType"] == "S-Sale"


@respx.mock
async def test_fetch_treasury_rates_no_symbol_required() -> None:
    route = respx.get(f"{_V4}/treasury").mock(
        return_value=httpx.Response(
            200,
            json=[{"date": "2026-04-01", "year10": 4.2}],
        )
    )
    adapter = FMPAdapter(_entry())
    result = await adapter.fetch(
        "treasury_rates",
        {"from": "2026-01-01", "to": "2026-04-01"},
    )
    assert route.called
    assert result.payload[0]["year10"] == 4.2


@respx.mock
async def test_fetch_sector_performance() -> None:
    route = respx.get(f"{_V3}/sector-performance").mock(
        return_value=httpx.Response(
            200,
            json=[{"sector": "Technology", "changesPercentage": "1.23%"}],
        )
    )
    adapter = FMPAdapter(_entry())
    result = await adapter.fetch("sector_performance", {})
    assert route.called
    assert result.payload[0]["sector"] == "Technology"


@respx.mock
async def test_401_raises_authentication_error() -> None:
    respx.get(f"{_V3}/quote/AAPL").mock(
        return_value=httpx.Response(401, text="Invalid API KEY"),
    )
    adapter = FMPAdapter(_entry())
    with pytest.raises(AuthenticationError) as exc:
        await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert exc.value.status_code == 401


@respx.mock
async def test_403_raises_authentication_error() -> None:
    respx.get(f"{_V3}/quote/AAPL").mock(
        return_value=httpx.Response(403, text="forbidden"),
    )
    adapter = FMPAdapter(_entry())
    with pytest.raises(AuthenticationError) as exc:
        await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert exc.value.status_code == 403


@respx.mock
async def test_404_maps_to_data_not_available() -> None:
    respx.get(f"{_V3}/quote/ZZZZ").mock(
        return_value=httpx.Response(404, text="not found"),
    )
    adapter = FMPAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("stock_quote", {"symbol": "ZZZZ"})
    assert exc.value.provider_kind == "fmp"


@respx.mock
async def test_empty_list_response_maps_to_data_not_available() -> None:
    respx.get(f"{_V3}/quote/UNKN").mock(return_value=httpx.Response(200, json=[]))
    adapter = FMPAdapter(_entry())
    with pytest.raises(DataNotAvailable):
        await adapter.fetch("stock_quote", {"symbol": "UNKN"})


@respx.mock
async def test_500_maps_to_data_source_error_transient() -> None:
    respx.get(f"{_V3}/quote/AAPL").mock(
        return_value=httpx.Response(500, text="boom"),
    )
    adapter = FMPAdapter(_entry())
    with pytest.raises(DataSourceError) as exc:
        await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert exc.value.status_code == 500
    assert exc.value.is_transient is True


@respx.mock
async def test_503_marks_transient() -> None:
    respx.get(f"{_V3}/quote/AAPL").mock(
        return_value=httpx.Response(503, text="boom"),
    )
    adapter = FMPAdapter(_entry())
    with pytest.raises(DataSourceError) as exc:
        await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert exc.value.is_transient is True
    assert exc.value.status_code == 503


@respx.mock
async def test_429_with_retry_after_raises_rate_limit_after_retries() -> None:
    route = respx.get(f"{_V3}/quote/AAPL").mock(
        return_value=httpx.Response(
            429,
            headers={"Retry-After": "0"},
            text="rate limited",
        )
    )
    adapter = FMPAdapter(_entry())
    with pytest.raises(RateLimitError) as exc:
        await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    # 0-second Retry-After is reported as 0, not None.
    assert exc.value.retry_after_seconds == 0
    # Default helper retries 3 times before giving up.
    assert route.call_count == 3


@respx.mock
async def test_429_then_success_on_retry() -> None:
    side_effects = [
        httpx.Response(429, headers={"Retry-After": "0"}, text="throttled"),
        httpx.Response(200, json=[{"symbol": "AAPL", "price": 100.0}]),
    ]
    route = respx.get(f"{_V3}/quote/AAPL").mock(side_effect=side_effects)
    adapter = FMPAdapter(_entry())
    result = await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert route.call_count == 2
    assert result.payload[0]["price"] == 100.0


@respx.mock
async def test_timeout_marks_transient() -> None:
    respx.get(f"{_V3}/quote/AAPL").mock(
        side_effect=httpx.ConnectTimeout("slow"),
    )
    adapter = FMPAdapter(_entry())
    with pytest.raises(DataSourceError) as exc:
        await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert exc.value.is_transient is True


@respx.mock
async def test_health_check_200_returns_true() -> None:
    respx.get(f"{_V3}/quote/AAPL").mock(
        return_value=httpx.Response(200, json=[{"symbol": "AAPL", "price": 1.0}]),
    )
    adapter = FMPAdapter(_entry())
    assert await adapter.health_check() is True


@respx.mock
async def test_health_check_401_returns_false() -> None:
    respx.get(f"{_V3}/quote/AAPL").mock(
        return_value=httpx.Response(401, text="bad key"),
    )
    adapter = FMPAdapter(_entry())
    assert await adapter.health_check() is False


@respx.mock
async def test_health_check_network_error_returns_false() -> None:
    respx.get(f"{_V3}/quote/AAPL").mock(side_effect=httpx.ConnectError("boom"))
    adapter = FMPAdapter(_entry())
    assert await adapter.health_check() is False


@respx.mock
async def test_extra_config_overrides_v3_and_v4_base_urls() -> None:
    custom_v3 = "https://proxy.example.com/v3"
    custom_v4 = "https://proxy.example.com/v4"
    entry = _entry(
        base_url="https://financialmodelingprep.com/api/v3",
        v3_base_url=custom_v3,
        v4_base_url=custom_v4,
    )
    route_v3 = respx.get(f"{custom_v3}/quote/AAPL").mock(
        return_value=httpx.Response(200, json=[{"symbol": "AAPL", "price": 1.0}]),
    )
    route_v4 = respx.get(f"{custom_v4}/insider-trading").mock(
        return_value=httpx.Response(200, json=[{"symbol": "AAPL"}]),
    )
    adapter = FMPAdapter(entry)
    await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    await adapter.fetch("insider_transactions", {"symbol": "AAPL"})
    assert route_v3.called
    assert route_v4.called


@respx.mock
async def test_v4_routing_when_base_url_points_at_v3() -> None:
    """A base_url ending in /api/v3 should still let v4 capabilities work."""
    route = respx.get(f"{_V4}/treasury").mock(
        return_value=httpx.Response(200, json=[{"date": "2026-04-01", "year10": 4.2}]),
    )
    adapter = FMPAdapter(_entry(base_url="https://financialmodelingprep.com/api/v3"))
    await adapter.fetch("treasury_rates", {})
    assert route.called


def test_parse_retry_after_integer_seconds() -> None:
    from openlia.data.adapters.fmp import _parse_retry_after

    assert _parse_retry_after("12") == 12
    assert _parse_retry_after("0") == 0
    assert _parse_retry_after(None) is None
    assert _parse_retry_after("garbage") is None


def test_parse_retry_after_http_date() -> None:
    from datetime import datetime, timedelta
    from email.utils import format_datetime

    from openlia.data.adapters.fmp import _parse_retry_after

    target = datetime.now(tz=UTC) + timedelta(seconds=45)
    header = format_datetime(target, usegmt=True)
    parsed = _parse_retry_after(header)
    assert parsed is not None
    assert 30 <= parsed <= 60


# ---------- NEW: analyst_ratings + macro_indicator ----------


@respx.mock
async def test_fetch_analyst_ratings_uses_v3_rating_endpoint() -> None:
    route = respx.get("https://financialmodelingprep.com/api/v3/rating/AAPL").mock(
        return_value=httpx.Response(200, json=[{"symbol": "AAPL", "rating": "S+"}]),
    )
    adapter = FMPAdapter(_entry())
    result = await adapter.fetch("analyst_ratings", {"symbol": "AAPL"})
    assert route.called
    assert result.capability == "analyst_ratings"


@respx.mock
async def test_fetch_macro_indicator_routes_to_v4_economic_endpoint() -> None:
    route = respx.get("https://financialmodelingprep.com/api/v4/economic").mock(
        return_value=httpx.Response(200, json=[{"date": "2026-01-01", "value": 1.0}]),
    )
    adapter = FMPAdapter(_entry())
    await adapter.fetch(
        "macro_indicator", {"indicator": "GDP", "from": "2020-01-01", "to": "2025-12-31"}
    )
    assert route.called
    qp = route.calls.last.request.url.params
    assert qp["name"] == "GDP"
    assert qp["from"] == "2020-01-01"


@respx.mock
async def test_fetch_macro_indicator_defaults_to_gdp() -> None:
    route = respx.get("https://financialmodelingprep.com/api/v4/economic").mock(
        return_value=httpx.Response(200, json=[{"date": "2026-01-01", "value": 1.0}]),
    )
    adapter = FMPAdapter(_entry())
    await adapter.fetch("macro_indicator", {})
    assert route.called
    assert route.calls.last.request.url.params["name"] == "GDP"


def test_fmp_declares_renamed_capabilities() -> None:
    must_cover = {
        "financial_statements",
        "earnings_data",
        "economic_events",
        "analyst_ratings",
        "macro_indicator",
    }
    assert must_cover <= FMPAdapter.capabilities
