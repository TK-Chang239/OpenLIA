import httpx
import pytest
import respx
from openlia.data.adapters.newsapi_ai import NewsAPIAIAdapter
from openlia.data.errors import (
    AuthenticationError,
    DataNotAvailable,
    DataSourceError,
    RateLimitError,
)
from openlia.data.types import ProviderCategory, ProviderEntry, ProviderMode

_BASE = "https://eventregistry.org/api/v1"


def _entry(base_url: str = _BASE) -> ProviderEntry:
    return ProviderEntry(
        id="00000000-0000-0000-0000-000000000010",
        kind="newsapi_ai",
        label="NewsAPI.ai",
        category=ProviderCategory.NEWS,
        mode=ProviderMode.API_KEY,
        api_key="TEST-KEY",
        base_url=base_url,
    )


def test_newsapi_ai_declared_metadata() -> None:
    assert NewsAPIAIAdapter.kind == "newsapi_ai"
    assert NewsAPIAIAdapter.category is ProviderCategory.NEWS
    expected = {
        "company_news",
        "general_news",
        "topic_news",
        "news_archive",
        "trending_news",
        "entity_news",
        "event_summary",
        "event_search",
    }
    assert expected <= NewsAPIAIAdapter.capabilities


async def test_fetch_rejects_unknown_capability() -> None:
    adapter = NewsAPIAIAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("insider_transactions", {"keyword": "Apple"})
    assert exc.value.provider_kind == "newsapi_ai"
    assert exc.value.capability == "insider_transactions"


@respx.mock
async def test_fetch_company_news_posts_with_keyword_and_api_key_in_body() -> None:
    route = respx.post(f"{_BASE}/article/getArticles").mock(
        return_value=httpx.Response(
            200,
            json={"articles": {"results": [{"title": "Apple beats earnings"}]}},
        )
    )
    adapter = NewsAPIAIAdapter(_entry())
    result = await adapter.fetch("company_news", {"symbol": "AAPL", "limit": 10})
    assert route.called
    assert result.provider_kind == "newsapi_ai"
    assert result.capability == "company_news"
    body = route.calls[0].request.read()
    assert b"TEST-KEY" in body
    assert b"AAPL" in body


@respx.mock
async def test_fetch_company_news_missing_keyword_raises() -> None:
    adapter = NewsAPIAIAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("company_news", {})
    assert "keyword" in exc.value.reason or "conceptUri" in exc.value.reason


@respx.mock
async def test_fetch_topic_news_with_concept_uri() -> None:
    route = respx.post(f"{_BASE}/article/getArticles").mock(
        return_value=httpx.Response(200, json={"articles": {"results": []}})
    )
    adapter = NewsAPIAIAdapter(_entry())
    result = await adapter.fetch(
        "topic_news",
        {"conceptUri": "http://en.wikipedia.org/wiki/Inflation"},
    )
    assert route.called
    assert result.capability == "topic_news"


@respx.mock
async def test_fetch_topic_news_missing_concept_or_category_raises() -> None:
    adapter = NewsAPIAIAdapter(_entry())
    with pytest.raises(DataNotAvailable):
        await adapter.fetch("topic_news", {})


@respx.mock
async def test_fetch_news_archive_requires_date_range() -> None:
    adapter = NewsAPIAIAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("news_archive", {"keyword": "AI"})
    assert "dateStart" in exc.value.reason


@respx.mock
async def test_fetch_news_archive_success() -> None:
    route = respx.post(f"{_BASE}/article/getArticles").mock(
        return_value=httpx.Response(200, json={"articles": {"results": [{"id": "x"}]}})
    )
    adapter = NewsAPIAIAdapter(_entry())
    result = await adapter.fetch(
        "news_archive",
        {
            "keyword": "AI",
            "dateStart": "2025-01-01",
            "dateEnd": "2025-12-31",
        },
    )
    assert route.called
    assert result.capability == "news_archive"


@respx.mock
async def test_fetch_entity_news_uses_get_with_apikey_query() -> None:
    route = respx.get(f"{_BASE}/suggestConceptsFast").mock(
        return_value=httpx.Response(200, json=[{"uri": "Apple_Inc.", "type": "wiki"}])
    )
    adapter = NewsAPIAIAdapter(_entry())
    result = await adapter.fetch("entity_news", {"prefix": "Apple"})
    assert route.called
    url = str(route.calls[0].request.url)
    assert "apiKey=TEST-KEY" in url
    assert "prefix=Apple" in url
    assert isinstance(result.payload, list)


@respx.mock
async def test_fetch_event_summary_requires_event_uri() -> None:
    adapter = NewsAPIAIAdapter(_entry())
    with pytest.raises(DataNotAvailable):
        await adapter.fetch("event_summary", {})


@respx.mock
async def test_fetch_event_summary_success() -> None:
    route = respx.post(f"{_BASE}/event/getEvent").mock(
        return_value=httpx.Response(200, json={"eng-1234": {"title": "A summit"}})
    )
    adapter = NewsAPIAIAdapter(_entry())
    result = await adapter.fetch("event_summary", {"eventUri": "eng-1234"})
    assert route.called
    assert result.capability == "event_summary"


@respx.mock
async def test_401_raises_authentication_error() -> None:
    respx.post(f"{_BASE}/article/getArticles").mock(
        return_value=httpx.Response(401, text="bad key"),
    )
    adapter = NewsAPIAIAdapter(_entry())
    with pytest.raises(AuthenticationError) as exc:
        await adapter.fetch("company_news", {"keyword": "Apple"})
    assert exc.value.status_code == 401


@respx.mock
async def test_200_with_invalid_api_key_body_raises_authentication_error() -> None:
    respx.post(f"{_BASE}/article/getArticles").mock(
        return_value=httpx.Response(200, json={"error": "Invalid api key"}),
    )
    adapter = NewsAPIAIAdapter(_entry())
    with pytest.raises(AuthenticationError) as exc:
        await adapter.fetch("company_news", {"keyword": "Apple"})
    assert exc.value.status_code == 200
    assert "Invalid api key" in exc.value.detail


@respx.mock
async def test_200_with_generic_error_body_raises_data_source_error() -> None:
    respx.post(f"{_BASE}/article/getArticles").mock(
        return_value=httpx.Response(200, json={"error": "param `keyword` malformed"}),
    )
    adapter = NewsAPIAIAdapter(_entry())
    with pytest.raises(DataSourceError) as exc:
        await adapter.fetch("company_news", {"keyword": "Apple"})
    assert exc.value.status_code == 200
    assert exc.value.is_transient is False


@respx.mock
async def test_429_maps_to_rate_limit_error_after_retries() -> None:
    respx.post(f"{_BASE}/article/getArticles").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "0"}, text="throttled"),
    )
    adapter = NewsAPIAIAdapter(_entry())
    with pytest.raises(RateLimitError) as exc:
        await adapter.fetch("company_news", {"keyword": "Apple"})
    assert exc.value.provider_kind == "newsapi_ai"


@respx.mock
async def test_500_maps_to_data_source_error_transient() -> None:
    respx.post(f"{_BASE}/article/getArticles").mock(
        return_value=httpx.Response(500, text="boom"),
    )
    adapter = NewsAPIAIAdapter(_entry())
    with pytest.raises(DataSourceError) as exc:
        await adapter.fetch("company_news", {"keyword": "Apple"})
    assert exc.value.status_code == 500
    assert exc.value.is_transient is True


@respx.mock
async def test_health_check_returns_true_on_200() -> None:
    respx.get(f"{_BASE}/suggestConceptsFast").mock(
        return_value=httpx.Response(200, json=[]),
    )
    adapter = NewsAPIAIAdapter(_entry())
    assert await adapter.health_check() is True


@respx.mock
async def test_health_check_returns_false_on_401() -> None:
    respx.get(f"{_BASE}/suggestConceptsFast").mock(
        return_value=httpx.Response(401, text="bad key"),
    )
    adapter = NewsAPIAIAdapter(_entry())
    assert await adapter.health_check() is False


@respx.mock
async def test_health_check_returns_false_on_network_error() -> None:
    respx.get(f"{_BASE}/suggestConceptsFast").mock(
        side_effect=httpx.ConnectError("boom"),
    )
    adapter = NewsAPIAIAdapter(_entry())
    assert await adapter.health_check() is False


@respx.mock
async def test_health_check_returns_false_on_200_with_error_body() -> None:
    respx.get(f"{_BASE}/suggestConceptsFast").mock(
        return_value=httpx.Response(200, json={"error": "Invalid api key"}),
    )
    adapter = NewsAPIAIAdapter(_entry())
    assert await adapter.health_check() is False
