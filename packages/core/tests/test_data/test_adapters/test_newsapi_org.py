import httpx
import pytest
import respx
from openlia.data.adapters.newsapi_org import NewsAPIOrgAdapter
from openlia.data.errors import (
    AuthenticationError,
    DataNotAvailable,
    DataSourceError,
    RateLimitError,
)
from openlia.data.types import ProviderCategory, ProviderEntry, ProviderMode

_BASE = "https://newsapi.org/v2"


def _entry(base_url: str = _BASE) -> ProviderEntry:
    return ProviderEntry(
        id="00000000-0000-0000-0000-000000000010",
        kind="newsapi_org",
        label="NewsAPI.org",
        category=ProviderCategory.NEWS,
        mode=ProviderMode.API_KEY,
        api_key="TEST-KEY",
        base_url=base_url,
    )


def test_declared_metadata() -> None:
    assert NewsAPIOrgAdapter.kind == "newsapi_org"
    assert NewsAPIOrgAdapter.category is ProviderCategory.NEWS
    expected = {
        "company_news",
        "general_news",
        "topic_news",
        "top_headlines",
        "news_sources",
        "news_archive",
    }
    assert expected <= NewsAPIOrgAdapter.capabilities


async def test_fetch_rejects_unknown_capability() -> None:
    adapter = NewsAPIOrgAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("insider_buzz", {"query": "x"})
    assert exc.value.provider_kind == "newsapi_org"
    assert exc.value.capability == "insider_buzz"


@respx.mock
async def test_fetch_company_news_success_and_sends_api_key_header() -> None:
    route = respx.get(f"{_BASE}/everything").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "ok",
                "totalResults": 1,
                "articles": [{"title": "Apple posts record quarter"}],
            },
        )
    )
    adapter = NewsAPIOrgAdapter(_entry())
    result = await adapter.fetch("company_news", {"symbol": "AAPL"})
    assert route.called
    assert result.provider_kind == "newsapi_org"
    assert result.capability == "company_news"
    assert result.payload["totalResults"] == 1
    request = route.calls[0].request
    assert request.headers.get("X-Api-Key") == "TEST-KEY"
    assert "qInTitle=AAPL" in str(request.url)


@respx.mock
async def test_fetch_top_headlines_success() -> None:
    route = respx.get(f"{_BASE}/top-headlines").mock(
        return_value=httpx.Response(
            200,
            json={"status": "ok", "totalResults": 0, "articles": []},
        )
    )
    adapter = NewsAPIOrgAdapter(_entry())
    result = await adapter.fetch("top_headlines", {"country": "us", "category": "business"})
    assert route.called
    assert result.capability == "top_headlines"
    url = str(route.calls[0].request.url)
    assert "country=us" in url
    assert "category=business" in url


@respx.mock
async def test_fetch_news_sources_success() -> None:
    route = respx.get(f"{_BASE}/top-headlines/sources").mock(
        return_value=httpx.Response(
            200,
            json={"status": "ok", "sources": [{"id": "bloomberg", "name": "Bloomberg"}]},
        )
    )
    adapter = NewsAPIOrgAdapter(_entry())
    result = await adapter.fetch("news_sources", {"category": "business"})
    assert route.called
    assert result.payload["sources"][0]["id"] == "bloomberg"


@respx.mock
async def test_fetch_news_archive_passes_date_params() -> None:
    route = respx.get(f"{_BASE}/everything").mock(
        return_value=httpx.Response(200, json={"status": "ok", "totalResults": 0, "articles": []})
    )
    adapter = NewsAPIOrgAdapter(_entry())
    await adapter.fetch(
        "news_archive",
        {"query": "tesla", "from": "2026-03-01", "to": "2026-03-15"},
    )
    url = str(route.calls[0].request.url)
    assert "q=tesla" in url
    assert "from=2026-03-01" in url
    assert "to=2026-03-15" in url


@respx.mock
async def test_company_news_missing_param_raises() -> None:
    adapter = NewsAPIOrgAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("company_news", {})
    assert "symbol" in exc.value.reason


@respx.mock
async def test_general_news_missing_query_raises() -> None:
    adapter = NewsAPIOrgAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("general_news", {})
    assert "query" in exc.value.reason


@respx.mock
async def test_401_maps_to_authentication_error() -> None:
    respx.get(f"{_BASE}/everything").mock(
        return_value=httpx.Response(401, text="bad key"),
    )
    adapter = NewsAPIOrgAdapter(_entry())
    with pytest.raises(AuthenticationError) as exc:
        await adapter.fetch("company_news", {"symbol": "AAPL"})
    assert exc.value.status_code == 401


@respx.mock
async def test_426_maps_to_authentication_error() -> None:
    respx.get(f"{_BASE}/everything").mock(
        return_value=httpx.Response(426, text="upgrade required"),
    )
    adapter = NewsAPIOrgAdapter(_entry())
    with pytest.raises(AuthenticationError) as exc:
        await adapter.fetch("company_news", {"symbol": "AAPL"})
    assert exc.value.status_code == 426


@respx.mock
async def test_200_envelope_apikey_invalid_maps_to_auth_error() -> None:
    respx.get(f"{_BASE}/everything").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "error",
                "code": "apiKeyInvalid",
                "message": "Your API key is invalid.",
            },
        ),
    )
    adapter = NewsAPIOrgAdapter(_entry())
    with pytest.raises(AuthenticationError) as exc:
        await adapter.fetch("company_news", {"symbol": "AAPL"})
    assert "apiKeyInvalid" in exc.value.detail


@respx.mock
async def test_200_envelope_rate_limited_maps_to_rate_limit_error() -> None:
    respx.get(f"{_BASE}/everything").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "error",
                "code": "rateLimited",
                "message": "You have made too many requests.",
            },
        ),
    )
    adapter = NewsAPIOrgAdapter(_entry())
    with pytest.raises(RateLimitError) as exc:
        await adapter.fetch("company_news", {"symbol": "AAPL"})
    assert exc.value.provider_kind == "newsapi_org"


@respx.mock
async def test_200_envelope_parameter_invalid_maps_to_data_not_available() -> None:
    respx.get(f"{_BASE}/everything").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "error",
                "code": "parameterInvalid",
                "message": "bad q",
            },
        ),
    )
    adapter = NewsAPIOrgAdapter(_entry())
    with pytest.raises(DataNotAvailable):
        await adapter.fetch("general_news", {"query": "x"})


@respx.mock
async def test_200_envelope_unknown_code_maps_to_data_source_error() -> None:
    respx.get(f"{_BASE}/everything").mock(
        return_value=httpx.Response(
            200,
            json={"status": "error", "code": "weirdo", "message": "?"},
        ),
    )
    adapter = NewsAPIOrgAdapter(_entry())
    with pytest.raises(DataSourceError):
        await adapter.fetch("general_news", {"query": "x"})


@respx.mock
async def test_429_maps_to_rate_limit_error_after_retries() -> None:
    route = respx.get(f"{_BASE}/everything").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "0"}, text="throttled"),
    )
    adapter = NewsAPIOrgAdapter(_entry())
    with pytest.raises(RateLimitError) as exc:
        await adapter.fetch("company_news", {"symbol": "AAPL"})
    assert exc.value.retry_after_seconds == 0
    assert route.call_count >= 2


@respx.mock
async def test_500_maps_to_transient_data_source_error() -> None:
    respx.get(f"{_BASE}/everything").mock(
        return_value=httpx.Response(500, text="boom"),
    )
    adapter = NewsAPIOrgAdapter(_entry())
    with pytest.raises(DataSourceError) as exc:
        await adapter.fetch("company_news", {"symbol": "AAPL"})
    assert exc.value.status_code == 500
    assert exc.value.is_transient is True


@respx.mock
async def test_health_check_returns_true_on_200() -> None:
    respx.get(f"{_BASE}/top-headlines/sources").mock(
        return_value=httpx.Response(200, json={"status": "ok", "sources": []}),
    )
    adapter = NewsAPIOrgAdapter(_entry())
    assert await adapter.health_check() is True


@respx.mock
async def test_health_check_returns_false_on_401() -> None:
    respx.get(f"{_BASE}/top-headlines/sources").mock(
        return_value=httpx.Response(401, text="bad key"),
    )
    adapter = NewsAPIOrgAdapter(_entry())
    assert await adapter.health_check() is False


@respx.mock
async def test_health_check_returns_false_on_network_error() -> None:
    respx.get(f"{_BASE}/top-headlines/sources").mock(
        side_effect=httpx.ConnectError("boom"),
    )
    adapter = NewsAPIOrgAdapter(_entry())
    assert await adapter.health_check() is False


@respx.mock
async def test_health_check_returns_false_on_envelope_error() -> None:
    respx.get(f"{_BASE}/top-headlines/sources").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "error",
                "code": "apiKeyInvalid",
                "message": "bad",
            },
        ),
    )
    adapter = NewsAPIOrgAdapter(_entry())
    assert await adapter.health_check() is False
