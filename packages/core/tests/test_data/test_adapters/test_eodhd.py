from datetime import UTC

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


# ---------- P0-3-04: company_fundamentals ----------


@respx.mock
async def test_fetch_company_fundamentals_extracts_financials_block() -> None:
    respx.get("https://eodhd.com/api/fundamentals/AAPL.US").mock(
        return_value=httpx.Response(
            200,
            json={
                "General": {"Code": "AAPL"},
                "Financials": {"Income_Statement": {"yearly": {"2024-09-30": {"netIncome": 1.0}}}},
            },
        )
    )
    adapter = EODHDAdapter(_entry())
    result = await adapter.fetch("company_fundamentals", {"symbol": "AAPL"})
    assert result.capability == "company_fundamentals"
    assert "Financials" in result.payload
    # General block should be stripped — only Financials returned.
    assert "General" not in result.payload


@respx.mock
async def test_fetch_company_fundamentals_missing_block_raises() -> None:
    respx.get("https://eodhd.com/api/fundamentals/MSFT.US").mock(
        return_value=httpx.Response(200, json={"General": {"Code": "MSFT"}}),
    )
    from openlia.data.errors import DataNotAvailable

    adapter = EODHDAdapter(_entry())
    with pytest.raises(DataNotAvailable):
        await adapter.fetch("company_fundamentals", {"symbol": "MSFT"})


# ---------- P1-3-06: typed errors for auth/transient/RFC1123 ----------


@respx.mock
async def test_eodhd_401_raises_authentication_error() -> None:
    from openlia.data.errors import AuthenticationError

    respx.get("https://eodhd.com/api/real-time/AAPL.US").mock(
        return_value=httpx.Response(401, text="bad key"),
    )
    adapter = EODHDAdapter(_entry())
    with pytest.raises(AuthenticationError) as exc:
        await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert exc.value.status_code == 401


@respx.mock
async def test_eodhd_403_raises_authentication_error() -> None:
    from openlia.data.errors import AuthenticationError

    respx.get("https://eodhd.com/api/real-time/AAPL.US").mock(
        return_value=httpx.Response(403, text="forbidden"),
    )
    adapter = EODHDAdapter(_entry())
    with pytest.raises(AuthenticationError) as exc:
        await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert exc.value.status_code == 403


@respx.mock
async def test_eodhd_5xx_marks_transient() -> None:
    respx.get("https://eodhd.com/api/real-time/AAPL.US").mock(
        return_value=httpx.Response(503, text="boom"),
    )
    adapter = EODHDAdapter(_entry())
    with pytest.raises(DataSourceError) as exc:
        await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert exc.value.is_transient is True
    assert exc.value.status_code == 503


@respx.mock
async def test_eodhd_timeout_marks_transient() -> None:
    respx.get("https://eodhd.com/api/real-time/AAPL.US").mock(
        side_effect=httpx.ConnectTimeout("slow"),
    )
    adapter = EODHDAdapter(_entry())
    with pytest.raises(DataSourceError) as exc:
        await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert exc.value.is_transient is True


def test_eodhd_http_date_retry_after() -> None:
    """RFC 1123 HTTP-date in Retry-After must be parsed to seconds-from-now."""
    from datetime import datetime, timedelta
    from email.utils import format_datetime

    from openlia.data.adapters.eodhd import _parse_retry_after

    target = datetime.now(tz=UTC) + timedelta(seconds=45)
    header = format_datetime(target, usegmt=True)
    parsed = _parse_retry_after(header)
    assert parsed is not None
    assert 30 <= parsed <= 60


def test_eodhd_retry_after_integer_seconds() -> None:
    from openlia.data.adapters.eodhd import _parse_retry_after

    assert _parse_retry_after("12") == 12
    assert _parse_retry_after("0") == 0
    assert _parse_retry_after(None) is None
    assert _parse_retry_after("garbage") is None


# ---------- P1-3-07: retry/backoff ----------


@respx.mock
async def test_rate_limit_retries_and_succeeds_on_third_attempt() -> None:
    side_effects = [
        httpx.Response(429, headers={"Retry-After": "0"}, text="throttled"),
        httpx.Response(429, headers={"Retry-After": "0"}, text="throttled"),
        httpx.Response(200, json={"close": 100.0}),
    ]
    route = respx.get("https://eodhd.com/api/real-time/AAPL.US").mock(
        side_effect=side_effects,
    )
    adapter = EODHDAdapter(_entry())
    result = await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert route.call_count == 3
    assert result.payload["close"] == 100.0


@respx.mock
async def test_rate_limit_exhausted_raises_rate_limit_error() -> None:
    respx.get("https://eodhd.com/api/real-time/AAPL.US").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "0"}, text="throttled"),
    )
    adapter = EODHDAdapter(_entry())
    with pytest.raises(RateLimitError):
        await adapter.fetch("stock_quote", {"symbol": "AAPL"})


# ---------- NEW-3-07: extra_config exchange suffix ----------


@respx.mock
async def test_format_ticker_honors_extra_config_suffix() -> None:
    entry = ProviderEntry(
        id="00000000-0000-0000-0000-000000000002",
        kind="eodhd",
        label="EODHD-LSE",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="K",
        base_url="https://eodhd.com/api",
        extra_config={"exchange_suffix": "LSE"},
    )
    route = respx.get("https://eodhd.com/api/real-time/HSBA.LSE").mock(
        return_value=httpx.Response(200, json={"close": 1.0}),
    )
    adapter = EODHDAdapter(entry)
    await adapter.fetch("stock_quote", {"symbol": "HSBA"})
    assert route.called
