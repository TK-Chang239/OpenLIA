"""Tests for the X (Twitter) adapter."""

import httpx
import pytest
import respx
from openlia.data.adapters.x import XAdapter
from openlia.data.errors import AuthenticationError, DataNotAvailable
from openlia.data.types import ProviderCategory, ProviderEntry, ProviderMode

_BASE = "https://api.x.com/2"


def _entry() -> ProviderEntry:
    return ProviderEntry(
        id="00000000-0000-0000-0000-000000000024",
        kind="x",
        label="X",
        category=ProviderCategory.SOCIAL_MEDIA,
        mode=ProviderMode.API_KEY,
        api_key="X-BEARER",
        base_url=_BASE,
    )


def test_declared_metadata() -> None:
    assert XAdapter.kind == "x"
    assert XAdapter.category is ProviderCategory.SOCIAL_MEDIA
    expected = {
        "social_sentiment",
        "company_news",
        "tweet_counts",
        "tweets_lookup",
        "user_tweets",
        "user_lookup",
        "trends_by_woeid",
    }
    assert XAdapter.capabilities == frozenset(expected)


@respx.mock
async def test_social_sentiment_uses_cashtag_when_only_symbol_given() -> None:
    route = respx.get(f"{_BASE}/tweets/search/recent").mock(
        return_value=httpx.Response(200, json={"data": [], "meta": {"result_count": 0}})
    )
    adapter = XAdapter(_entry())
    await adapter.fetch("social_sentiment", {"symbol": "AAPL"})
    assert route.called
    request = route.calls[0].request
    assert request.headers["Authorization"] == "Bearer X-BEARER"
    url = str(request.url)
    assert "query=" in url
    # query is URL-encoded; assert the cashtag and the no-retweet filter
    assert "%24AAPL" in url
    assert "is%3Aretweet" in url


@respx.mock
async def test_explicit_query_passed_through() -> None:
    route = respx.get(f"{_BASE}/tweets/search/recent").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    adapter = XAdapter(_entry())
    await adapter.fetch(
        "social_sentiment",
        {"query": "openlia lang:en", "max_results": 50, "sort_order": "relevancy"},
    )
    url = str(route.calls[0].request.url)
    assert "openlia+lang%3Aen" in url or "openlia%20lang%3Aen" in url
    assert "max_results=50" in url
    assert "sort_order=relevancy" in url


@respx.mock
async def test_tweet_counts_routes_to_counts_endpoint() -> None:
    route = respx.get(f"{_BASE}/tweets/counts/recent").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    adapter = XAdapter(_entry())
    await adapter.fetch("tweet_counts", {"symbol": "TSLA", "granularity": "day"})
    assert route.called
    assert "granularity=day" in str(route.calls[0].request.url)


@respx.mock
async def test_user_lookup_strips_at_sign() -> None:
    route = respx.get(f"{_BASE}/users/by/username/jack").mock(
        return_value=httpx.Response(200, json={"data": {"id": "12", "username": "jack"}})
    )
    adapter = XAdapter(_entry())
    await adapter.fetch("user_lookup", {"username": "@jack"})
    assert route.called


@respx.mock
async def test_trends_by_woeid_uses_path_param() -> None:
    route = respx.get(f"{_BASE}/trends/by/woeid/23424977").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    adapter = XAdapter(_entry())
    await adapter.fetch("trends_by_woeid", {"woeid": 23424977})
    assert route.called


async def test_search_requires_query_or_symbol() -> None:
    adapter = XAdapter(_entry())
    with pytest.raises(DataNotAvailable):
        await adapter.fetch("social_sentiment", {})


async def test_unknown_capability_raises() -> None:
    adapter = XAdapter(_entry())
    with pytest.raises(DataNotAvailable):
        await adapter.fetch("transcripts", {"symbol": "AAPL"})


@respx.mock
async def test_auth_error_on_401() -> None:
    respx.get(f"{_BASE}/tweets/search/recent").mock(
        return_value=httpx.Response(401, text="bad token")
    )
    adapter = XAdapter(_entry())
    with pytest.raises(AuthenticationError):
        await adapter.fetch("social_sentiment", {"symbol": "AAPL"})


@respx.mock
async def test_400_maps_to_data_not_available() -> None:
    respx.get(f"{_BASE}/tweets/search/recent").mock(
        return_value=httpx.Response(400, text="invalid query")
    )
    adapter = XAdapter(_entry())
    with pytest.raises(DataNotAvailable):
        await adapter.fetch("social_sentiment", {"symbol": "AAPL"})


@respx.mock
async def test_health_check_true_on_200() -> None:
    respx.get(f"{_BASE}/tweets/search/recent").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    adapter = XAdapter(_entry())
    assert await adapter.health_check() is True


@respx.mock
async def test_health_check_false_on_401() -> None:
    respx.get(f"{_BASE}/tweets/search/recent").mock(return_value=httpx.Response(401))
    adapter = XAdapter(_entry())
    assert await adapter.health_check() is False
