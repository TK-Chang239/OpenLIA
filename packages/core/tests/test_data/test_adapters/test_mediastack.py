import httpx
import pytest
import respx
from openlia.data.adapters.mediastack import MediastackAdapter
from openlia.data.errors import (
    AuthenticationError,
    DataNotAvailable,
    DataSourceError,
    RateLimitError,
)
from openlia.data.types import ProviderCategory, ProviderEntry, ProviderMode

_BASE_URL = "https://api.mediastack.com/v1"


def _entry(base_url: str = _BASE_URL) -> ProviderEntry:
    return ProviderEntry(
        id="00000000-0000-0000-0000-0000000000aa",
        kind="mediastack",
        label="Mediastack",
        category=ProviderCategory.NEWS,
        mode=ProviderMode.API_KEY,
        api_key="TEST-KEY",
        base_url=base_url,
    )


def test_mediastack_declared_metadata() -> None:
    assert MediastackAdapter.kind == "mediastack"
    assert MediastackAdapter.category is ProviderCategory.NEWS
    assert {
        "general_news",
        "company_news",
        "news_archive",
        "top_headlines",
        "topic_news",
        "news_sources",
    } <= MediastackAdapter.capabilities


async def test_fetch_rejects_unknown_capability() -> None:
    adapter = MediastackAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("insider_transactions", {})
    assert exc.value.provider_kind == "mediastack"
    assert exc.value.capability == "insider_transactions"


@respx.mock
async def test_fetch_general_news_success_passes_access_key() -> None:
    route = respx.get(f"{_BASE_URL}/news").mock(
        return_value=httpx.Response(
            200,
            json={
                "pagination": {"limit": 25, "offset": 0, "count": 1, "total": 1},
                "data": [{"title": "Markets up", "source": "Reuters"}],
            },
        )
    )
    adapter = MediastackAdapter(_entry())
    result = await adapter.fetch("general_news", {"keywords": "markets"})
    assert route.called
    assert result.provider_kind == "mediastack"
    assert result.capability == "general_news"
    url = str(route.calls[0].request.url)
    assert "access_key=TEST-KEY" in url
    assert "keywords=markets" in url


@respx.mock
async def test_fetch_company_news_uses_keywords_param() -> None:
    route = respx.get(f"{_BASE_URL}/news").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"title": "Apple earnings"}]},
        )
    )
    adapter = MediastackAdapter(_entry())
    result = await adapter.fetch("company_news", {"symbol": "AAPL"})
    assert route.called
    assert "keywords=AAPL" in str(route.calls[0].request.url)
    assert isinstance(result.payload, dict)


@respx.mock
async def test_fetch_news_archive_builds_date_range() -> None:
    route = respx.get(f"{_BASE_URL}/news").mock(
        return_value=httpx.Response(200, json={"data": []}),
    )
    adapter = MediastackAdapter(_entry())
    await adapter.fetch(
        "news_archive",
        {"from": "2026-01-01", "to": "2026-01-31"},
    )
    url = str(route.calls[0].request.url)
    assert "date=2026-01-01%2C2026-01-31" in url or "date=2026-01-01,2026-01-31" in url


@respx.mock
async def test_fetch_top_headlines_sorts_by_published_desc() -> None:
    route = respx.get(f"{_BASE_URL}/news").mock(
        return_value=httpx.Response(200, json={"data": [{"title": "X"}]}),
    )
    adapter = MediastackAdapter(_entry())
    await adapter.fetch("top_headlines", {"limit": 10})
    url = str(route.calls[0].request.url)
    assert "sort=published_desc" in url
    assert "limit=10" in url


@respx.mock
async def test_fetch_news_sources_hits_sources_endpoint() -> None:
    route = respx.get(f"{_BASE_URL}/sources").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": "reuters", "name": "Reuters"}]},
        )
    )
    adapter = MediastackAdapter(_entry())
    result = await adapter.fetch("news_sources", {"limit": 5})
    assert route.called
    assert result.capability == "news_sources"


@respx.mock
async def test_fetch_general_news_missing_keywords_raises() -> None:
    adapter = MediastackAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("general_news", {})
    assert "keywords" in exc.value.reason


@respx.mock
async def test_401_raises_authentication_error() -> None:
    respx.get(f"{_BASE_URL}/news").mock(
        return_value=httpx.Response(401, text="bad key"),
    )
    adapter = MediastackAdapter(_entry())
    with pytest.raises(AuthenticationError) as exc:
        await adapter.fetch("general_news", {"keywords": "x"})
    assert exc.value.status_code == 401


@respx.mock
async def test_200_with_invalid_access_key_envelope_raises_auth_error() -> None:
    respx.get(f"{_BASE_URL}/news").mock(
        return_value=httpx.Response(
            200,
            json={
                "error": {
                    "code": "invalid_access_key",
                    "message": "You have not supplied a valid API Access Key.",
                }
            },
        )
    )
    adapter = MediastackAdapter(_entry())
    with pytest.raises(AuthenticationError) as exc:
        await adapter.fetch("general_news", {"keywords": "x"})
    assert exc.value.status_code == 200
    assert "invalid_access_key" in exc.value.detail


@respx.mock
async def test_200_with_usage_limit_envelope_raises_auth_error() -> None:
    respx.get(f"{_BASE_URL}/news").mock(
        return_value=httpx.Response(
            200,
            json={"error": {"code": "usage_limit_reached", "message": "limit"}},
        )
    )
    adapter = MediastackAdapter(_entry())
    with pytest.raises(AuthenticationError):
        await adapter.fetch("general_news", {"keywords": "x"})


@respx.mock
async def test_200_with_rate_limit_envelope_raises_rate_limit_error() -> None:
    respx.get(f"{_BASE_URL}/news").mock(
        return_value=httpx.Response(
            200,
            json={"error": {"code": "rate_limit_reached", "message": "throttled"}},
        )
    )
    adapter = MediastackAdapter(_entry())
    with pytest.raises(RateLimitError) as exc:
        await adapter.fetch("general_news", {"keywords": "x"})
    assert exc.value.provider_kind == "mediastack"


@respx.mock
async def test_200_with_validation_error_envelope_raises_data_not_available() -> None:
    respx.get(f"{_BASE_URL}/news").mock(
        return_value=httpx.Response(
            200,
            json={"error": {"code": "validation_error", "message": "bad date"}},
        )
    )
    adapter = MediastackAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("general_news", {"keywords": "x"})
    assert "validation_error" in exc.value.reason


@respx.mock
async def test_200_with_unknown_error_envelope_raises_data_source_error() -> None:
    respx.get(f"{_BASE_URL}/news").mock(
        return_value=httpx.Response(
            200,
            json={"error": {"code": "wat_is_this", "message": "boom"}},
        )
    )
    adapter = MediastackAdapter(_entry())
    with pytest.raises(DataSourceError) as exc:
        await adapter.fetch("general_news", {"keywords": "x"})
    assert exc.value.status_code == 200


@respx.mock
async def test_429_maps_to_rate_limit_error_after_retries() -> None:
    route = respx.get(f"{_BASE_URL}/news").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "0"}, text="slow down"),
    )
    adapter = MediastackAdapter(_entry())
    with pytest.raises(RateLimitError):
        await adapter.fetch("general_news", {"keywords": "x"})
    assert route.call_count == 3


@respx.mock
async def test_500_maps_to_transient_data_source_error() -> None:
    respx.get(f"{_BASE_URL}/news").mock(
        return_value=httpx.Response(500, text="boom"),
    )
    adapter = MediastackAdapter(_entry())
    with pytest.raises(DataSourceError) as exc:
        await adapter.fetch("general_news", {"keywords": "x"})
    assert exc.value.status_code == 500
    assert exc.value.is_transient is True


@respx.mock
async def test_health_check_returns_true_on_200() -> None:
    respx.get(f"{_BASE_URL}/sources").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"id": "reuters"}]},
        )
    )
    adapter = MediastackAdapter(_entry())
    assert await adapter.health_check() is True


@respx.mock
async def test_health_check_returns_false_on_401() -> None:
    respx.get(f"{_BASE_URL}/sources").mock(
        return_value=httpx.Response(401, text="bad key"),
    )
    adapter = MediastackAdapter(_entry())
    assert await adapter.health_check() is False


@respx.mock
async def test_health_check_returns_false_on_error_envelope() -> None:
    respx.get(f"{_BASE_URL}/sources").mock(
        return_value=httpx.Response(
            200,
            json={"error": {"code": "invalid_access_key", "message": "no"}},
        )
    )
    adapter = MediastackAdapter(_entry())
    assert await adapter.health_check() is False


@respx.mock
async def test_health_check_returns_false_on_network_error() -> None:
    respx.get(f"{_BASE_URL}/sources").mock(
        side_effect=httpx.ConnectError("boom"),
    )
    adapter = MediastackAdapter(_entry())
    assert await adapter.health_check() is False
