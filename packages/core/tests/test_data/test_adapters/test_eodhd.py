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
        await adapter.fetch("not_a_real_capability", {"symbol": "AAPL"})
    assert exc.value.provider_kind == "eodhd"
    assert exc.value.capability == "not_a_real_capability"


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


# ---------- P0-3-04: financial_statements ----------


@respx.mock
async def test_fetch_financial_statements_extracts_financials_block() -> None:
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
    result = await adapter.fetch("financial_statements", {"symbol": "AAPL"})
    assert result.capability == "financial_statements"
    assert "Financials" in result.payload
    # General block should be stripped — only Financials returned.
    assert "General" not in result.payload


@respx.mock
async def test_fetch_financial_statements_missing_block_raises() -> None:
    respx.get("https://eodhd.com/api/fundamentals/MSFT.US").mock(
        return_value=httpx.Response(200, json={"General": {"Code": "MSFT"}}),
    )
    from openlia.data.errors import DataNotAvailable

    adapter = EODHDAdapter(_entry())
    with pytest.raises(DataNotAvailable):
        await adapter.fetch("financial_statements", {"symbol": "MSFT"})


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


# ---------- NEW: extended capabilities (earnings/economic/macro/insider/sentiment/...) ----------


@respx.mock
async def test_fetch_economic_events_calls_endpoint_and_passes_params() -> None:
    route = respx.get("https://eodhd.com/api/economic-events").mock(
        return_value=httpx.Response(200, json=[{"event": "CPI", "country": "US"}]),
    )
    adapter = EODHDAdapter(_entry())
    result = await adapter.fetch(
        "economic_events",
        {"country": "US", "from": "2026-01-01", "to": "2026-01-31"},
    )
    assert route.called
    qp = route.calls.last.request.url.params
    assert qp["country"] == "US"
    assert qp["from"] == "2026-01-01"
    assert result.capability == "economic_events"


@respx.mock
async def test_fetch_earnings_data_uses_calendar_earnings_endpoint() -> None:
    route = respx.get("https://eodhd.com/api/calendar/earnings").mock(
        return_value=httpx.Response(200, json={"earnings": []}),
    )
    adapter = EODHDAdapter(_entry())
    await adapter.fetch("earnings_data", {"symbol": "AAPL"})
    assert route.called
    assert route.calls.last.request.url.params["symbols"] == "AAPL.US"


@respx.mock
async def test_fetch_earnings_data_works_without_symbol() -> None:
    route = respx.get("https://eodhd.com/api/calendar/earnings").mock(
        return_value=httpx.Response(200, json={"earnings": []}),
    )
    adapter = EODHDAdapter(_entry())
    await adapter.fetch("earnings_data", {"from": "2026-04-01", "to": "2026-04-30"})
    assert route.called
    assert route.calls.last.request.url.params["from"] == "2026-04-01"


@respx.mock
async def test_fetch_macro_indicator_uses_country_path() -> None:
    route = respx.get("https://eodhd.com/api/macro-indicator/USA").mock(
        return_value=httpx.Response(200, json=[{"Indicator": "GDP", "Value": 1.0}]),
    )
    adapter = EODHDAdapter(_entry())
    await adapter.fetch("macro_indicator", {"indicator": "gdp_current_usd"})
    assert route.called
    assert route.calls.last.request.url.params["indicator"] == "gdp_current_usd"


@respx.mock
async def test_fetch_macro_indicator_honors_country_param() -> None:
    route = respx.get("https://eodhd.com/api/macro-indicator/DEU").mock(
        return_value=httpx.Response(200, json=[]),
    )
    adapter = EODHDAdapter(_entry())
    await adapter.fetch("macro_indicator", {"country": "DEU"})
    assert route.called


@respx.mock
async def test_fetch_insider_transactions_passes_code_filter() -> None:
    route = respx.get("https://eodhd.com/api/insider-transactions").mock(
        return_value=httpx.Response(200, json=[]),
    )
    adapter = EODHDAdapter(_entry())
    await adapter.fetch("insider_transactions", {"symbol": "AAPL"})
    assert route.called
    assert route.calls.last.request.url.params["code"] == "AAPL.US"


@respx.mock
async def test_fetch_insider_transactions_works_without_symbol() -> None:
    route = respx.get("https://eodhd.com/api/insider-transactions").mock(
        return_value=httpx.Response(200, json=[]),
    )
    adapter = EODHDAdapter(_entry())
    await adapter.fetch("insider_transactions", {"limit": 200})
    assert route.called
    assert "code" not in route.calls.last.request.url.params


@respx.mock
async def test_fetch_social_sentiment_passes_symbol() -> None:
    route = respx.get("https://eodhd.com/api/sentiments").mock(
        return_value=httpx.Response(200, json={"AAPL.US": []}),
    )
    adapter = EODHDAdapter(_entry())
    await adapter.fetch("social_sentiment", {"symbol": "AAPL"})
    assert route.called
    assert route.calls.last.request.url.params["s"] == "AAPL.US"


@respx.mock
async def test_fetch_analyst_ratings_extracts_block() -> None:
    respx.get("https://eodhd.com/api/fundamentals/AAPL.US").mock(
        return_value=httpx.Response(
            200,
            json={
                "General": {"Code": "AAPL"},
                "AnalystRatings": {"Rating": 1.5, "TargetPrice": 200.0},
            },
        )
    )
    adapter = EODHDAdapter(_entry())
    result = await adapter.fetch("analyst_ratings", {"symbol": "AAPL"})
    assert "AnalystRatings" in result.payload
    assert "General" not in result.payload


@respx.mock
async def test_fetch_analyst_ratings_missing_block_raises() -> None:
    respx.get("https://eodhd.com/api/fundamentals/MSFT.US").mock(
        return_value=httpx.Response(200, json={"General": {"Code": "MSFT"}}),
    )
    adapter = EODHDAdapter(_entry())
    with pytest.raises(DataNotAvailable):
        await adapter.fetch("analyst_ratings", {"symbol": "MSFT"})


@respx.mock
async def test_fetch_dividends_path() -> None:
    route = respx.get("https://eodhd.com/api/div/AAPL.US").mock(
        return_value=httpx.Response(200, json=[]),
    )
    adapter = EODHDAdapter(_entry())
    await adapter.fetch("dividends", {"symbol": "AAPL"})
    assert route.called


@respx.mock
async def test_fetch_splits_path() -> None:
    route = respx.get("https://eodhd.com/api/splits/AAPL.US").mock(
        return_value=httpx.Response(200, json=[]),
    )
    adapter = EODHDAdapter(_entry())
    await adapter.fetch("splits", {"symbol": "AAPL"})
    assert route.called


@respx.mock
async def test_fetch_ipo_calendar_works_without_symbol() -> None:
    route = respx.get("https://eodhd.com/api/calendar/ipos").mock(
        return_value=httpx.Response(200, json={"ipos": []}),
    )
    adapter = EODHDAdapter(_entry())
    await adapter.fetch("ipo_calendar", {"from": "2026-04-01", "to": "2026-04-30"})
    assert route.called


def test_eodhd_declares_extended_capabilities() -> None:
    must_cover = {
        "economic_events",
        "earnings_data",
        "macro_indicator",
        "insider_transactions",
        "social_sentiment",
        "analyst_ratings",
        "dividends",
        "splits",
        "ipo_calendar",
        "financial_statements",
    }
    assert must_cover <= EODHDAdapter.capabilities
