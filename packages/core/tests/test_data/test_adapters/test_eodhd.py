import httpx
import pytest
import respx
from openlia.data.adapters.eodhd import EODHDAdapter
from openlia.data.errors import DataNotAvailable, DataSourceError, RateLimitError
from openlia.data.types import ProviderCategory, ProviderEntry, ProviderMode


def _entry(base_url: str = "https://eodhd.com/api") -> ProviderEntry:
    return ProviderEntry(
        id="00000000-0000-0000-0000-000000000001",
        kind="eodhd",
        label="EODHD",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="TEST-KEY",
        base_url=base_url,
    )


def test_eodhd_declared_metadata() -> None:
    assert EODHDAdapter.kind == "eodhd"
    assert EODHDAdapter.category is ProviderCategory.FINANCIAL
    assert {"stock_quote", "historical_prices", "company_profile", "company_news"} <= (
        EODHDAdapter.capabilities
    )


async def test_fetch_rejects_unknown_capability() -> None:
    adapter = EODHDAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("insider_transactions", {"symbol": "AAPL"})
    assert exc.value.provider_kind == "eodhd"
    assert exc.value.capability == "insider_transactions"


@respx.mock
async def test_fetch_stock_quote_success() -> None:
    route = respx.get(
        "https://eodhd.com/api/real-time/AAPL.US",
    ).mock(
        return_value=httpx.Response(
            200,
            json={"code": "AAPL.US", "close": 225.1, "volume": 10_000_000},
        )
    )
    adapter = EODHDAdapter(_entry())
    result = await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert route.called
    assert result.provider_kind == "eodhd"
    assert result.capability == "stock_quote"
    assert result.payload["close"] == 225.1
    # api key must be passed as ?api_token=
    assert "api_token=TEST-KEY" in str(route.calls[0].request.url)


@respx.mock
async def test_fetch_stock_quote_missing_symbol_param() -> None:
    adapter = EODHDAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("stock_quote", {})
    assert "symbol" in exc.value.reason


@respx.mock
async def test_fetch_historical_prices_uses_eod_endpoint() -> None:
    route = respx.get("https://eodhd.com/api/eod/MSFT.US").mock(
        return_value=httpx.Response(
            200,
            json=[{"date": "2026-04-10", "close": 400.0}],
        )
    )
    adapter = EODHDAdapter(_entry())
    result = await adapter.fetch(
        "historical_prices",
        {"symbol": "MSFT", "from": "2025-01-01", "to": "2026-01-01"},
    )
    assert route.called
    assert isinstance(result.payload, list)


@respx.mock
async def test_429_maps_to_rate_limit_error() -> None:
    respx.get("https://eodhd.com/api/real-time/AAPL.US").mock(
        return_value=httpx.Response(
            429,
            headers={"Retry-After": "30"},
            text="rate limited",
        )
    )
    adapter = EODHDAdapter(_entry())
    with pytest.raises(RateLimitError) as exc:
        await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert exc.value.retry_after_seconds == 30


@respx.mock
async def test_404_maps_to_data_not_available() -> None:
    respx.get("https://eodhd.com/api/real-time/ZZZZ.US").mock(
        return_value=httpx.Response(404, text="symbol not found"),
    )
    adapter = EODHDAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("stock_quote", {"symbol": "ZZZZ"})
    assert exc.value.provider_kind == "eodhd"


@respx.mock
async def test_500_maps_to_data_source_error() -> None:
    respx.get("https://eodhd.com/api/real-time/AAPL.US").mock(
        return_value=httpx.Response(500, text="boom"),
    )
    adapter = EODHDAdapter(_entry())
    with pytest.raises(DataSourceError) as exc:
        await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert exc.value.status_code == 500


@respx.mock
async def test_health_check_hits_user_endpoint_and_returns_true_on_200() -> None:
    respx.get("https://eodhd.com/api/user").mock(
        return_value=httpx.Response(200, json={"email": "x@y.z"})
    )
    adapter = EODHDAdapter(_entry())
    assert await adapter.health_check() is True


@respx.mock
async def test_health_check_returns_false_on_401() -> None:
    respx.get("https://eodhd.com/api/user").mock(return_value=httpx.Response(401, text="bad key"))
    adapter = EODHDAdapter(_entry())
    assert await adapter.health_check() is False


@respx.mock
async def test_health_check_returns_false_on_network_error() -> None:
    respx.get("https://eodhd.com/api/user").mock(
        side_effect=httpx.ConnectError("boom"),
    )
    adapter = EODHDAdapter(_entry())
    assert await adapter.health_check() is False


def test_registry_exposes_eodhd() -> None:
    from openlia.data.adapters import ADAPTERS

    assert ADAPTERS["eodhd"] is EODHDAdapter
