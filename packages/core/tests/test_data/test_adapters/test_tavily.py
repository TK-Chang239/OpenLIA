"""Tests for the Tavily adapter."""

import httpx
import pytest
import respx
from openlia.data.adapters.tavily import TavilyAdapter
from openlia.data.errors import AuthenticationError, DataNotAvailable
from openlia.data.types import ProviderCategory, ProviderEntry, ProviderMode

_BASE = "https://api.tavily.com"


def _entry(base_url: str = _BASE) -> ProviderEntry:
    return ProviderEntry(
        id="00000000-0000-0000-0000-000000000021",
        kind="tavily",
        label="Tavily",
        category=ProviderCategory.SEARCH,
        mode=ProviderMode.API_KEY,
        api_key="tvly-TESTKEY",
        base_url=base_url,
    )


def test_declared_metadata() -> None:
    assert TavilyAdapter.kind == "tavily"
    assert TavilyAdapter.category is ProviderCategory.SEARCH
    assert TavilyAdapter.capabilities == frozenset(
        {"web_search", "web_extract", "web_crawl", "web_map"}
    )


@respx.mock
async def test_web_search_posts_with_bearer_and_returns_payload() -> None:
    route = respx.post(f"{_BASE}/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "query": "openlia",
                "results": [{"title": "T", "url": "https://x.test", "content": "snip"}],
            },
        )
    )
    adapter = TavilyAdapter(_entry())
    result = await adapter.fetch(
        "web_search",
        {"query": "openlia", "max_results": 3, "topic": "general"},
    )
    assert route.called
    request = route.calls[0].request
    assert request.headers["Authorization"] == "Bearer tvly-TESTKEY"
    body = result.payload
    assert body["results"][0]["url"] == "https://x.test"


@respx.mock
async def test_search_protocol_returns_normalized_results() -> None:
    respx.post(f"{_BASE}/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {"title": "T1", "url": "https://a.test", "content": "C1"},
                    {"title": "T2", "url": "https://b.test", "content": "C2"},
                ]
            },
        )
    )
    adapter = TavilyAdapter(_entry())
    out = await adapter.search("hello")
    assert [r.url for r in out] == ["https://a.test", "https://b.test"]
    assert out[0].snippet == "C1"


@respx.mock
async def test_extract_accepts_single_or_list_urls() -> None:
    route = respx.post(f"{_BASE}/extract").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    adapter = TavilyAdapter(_entry())
    await adapter.fetch("web_extract", {"url": "https://example.com"})
    body = route.calls[0].request.read().decode()
    assert '"urls":["https://example.com"]' in body.replace(" ", "")


async def test_unknown_capability_raises() -> None:
    adapter = TavilyAdapter(_entry())
    with pytest.raises(DataNotAvailable):
        await adapter.fetch("foo", {"query": "x"})


async def test_search_requires_query() -> None:
    adapter = TavilyAdapter(_entry())
    with pytest.raises(DataNotAvailable):
        await adapter.fetch("web_search", {})


async def test_crawl_requires_url() -> None:
    adapter = TavilyAdapter(_entry())
    with pytest.raises(DataNotAvailable):
        await adapter.fetch("web_crawl", {})


@respx.mock
async def test_auth_error_on_401() -> None:
    respx.post(f"{_BASE}/search").mock(return_value=httpx.Response(401, text="bad key"))
    adapter = TavilyAdapter(_entry())
    with pytest.raises(AuthenticationError):
        await adapter.fetch("web_search", {"query": "x"})


@respx.mock
async def test_400_maps_to_data_not_available() -> None:
    respx.post(f"{_BASE}/search").mock(return_value=httpx.Response(400, text="bad params"))
    adapter = TavilyAdapter(_entry())
    with pytest.raises(DataNotAvailable):
        await adapter.fetch("web_search", {"query": "x"})
