"""Tests for the Serper adapter."""

import httpx
import pytest
import respx
from openlia.data.adapters.serper import SerperAdapter
from openlia.data.errors import AuthenticationError, DataNotAvailable
from openlia.data.types import ProviderCategory, ProviderEntry, ProviderMode

_BASE = "https://google.serper.dev"
_SCRAPE = "https://scrape.serper.dev"


def _entry(base_url: str = _BASE) -> ProviderEntry:
    return ProviderEntry(
        id="00000000-0000-0000-0000-000000000022",
        kind="serper",
        label="Serper",
        category=ProviderCategory.SEARCH,
        mode=ProviderMode.API_KEY,
        api_key="SERPER-KEY",
        base_url=base_url,
    )


def test_declared_metadata() -> None:
    assert SerperAdapter.kind == "serper"
    assert SerperAdapter.category is ProviderCategory.SEARCH
    expected = {
        "web_search",
        "news_search",
        "image_search",
        "video_search",
        "places_search",
        "maps_search",
        "shopping_search",
        "scholar_search",
        "autocomplete",
        "web_scrape",
    }
    assert SerperAdapter.capabilities == frozenset(expected)


@respx.mock
async def test_web_search_posts_with_x_api_key() -> None:
    route = respx.post(f"{_BASE}/search").mock(
        return_value=httpx.Response(
            200,
            json={"organic": [{"title": "T", "link": "https://x.test", "snippet": "S"}]},
        )
    )
    adapter = SerperAdapter(_entry())
    result = await adapter.fetch("web_search", {"query": "openlia", "num": 5, "gl": "us"})
    assert route.called
    request = route.calls[0].request
    assert request.headers["X-API-KEY"] == "SERPER-KEY"
    body = request.read().decode()
    assert '"q":"openlia"' in body.replace(" ", "")
    assert '"num":5' in body.replace(" ", "")
    assert result.payload["organic"][0]["link"] == "https://x.test"


@respx.mock
async def test_search_protocol_normalizes_organic_results() -> None:
    respx.post(f"{_BASE}/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "organic": [
                    {"title": "T1", "link": "https://a.test", "snippet": "S1"},
                    {"title": "T2", "link": "https://b.test", "snippet": "S2"},
                ]
            },
        )
    )
    adapter = SerperAdapter(_entry())
    out = await adapter.search("hello")
    assert [r.url for r in out] == ["https://a.test", "https://b.test"]


@respx.mock
async def test_news_endpoint_routed_correctly() -> None:
    route = respx.post(f"{_BASE}/news").mock(return_value=httpx.Response(200, json={"news": []}))
    adapter = SerperAdapter(_entry())
    await adapter.fetch("news_search", {"query": "tesla"})
    assert route.called


@respx.mock
async def test_scrape_uses_separate_host() -> None:
    route = respx.post(_SCRAPE).mock(return_value=httpx.Response(200, json={"text": "hello world"}))
    adapter = SerperAdapter(_entry())
    await adapter.fetch("web_scrape", {"url": "https://example.com", "include_markdown": True})
    assert route.called
    body = route.calls[0].request.read().decode()
    assert '"url":"https://example.com"' in body.replace(" ", "")
    assert '"includeMarkdown":true' in body.replace(" ", "")


async def test_unknown_capability_raises() -> None:
    adapter = SerperAdapter(_entry())
    with pytest.raises(DataNotAvailable):
        await adapter.fetch("transcripts", {"query": "x"})


async def test_search_requires_query() -> None:
    adapter = SerperAdapter(_entry())
    with pytest.raises(DataNotAvailable):
        await adapter.fetch("web_search", {})


async def test_scrape_requires_url() -> None:
    adapter = SerperAdapter(_entry())
    with pytest.raises(DataNotAvailable):
        await adapter.fetch("web_scrape", {})


@respx.mock
async def test_auth_error_on_403() -> None:
    respx.post(f"{_BASE}/search").mock(return_value=httpx.Response(403, text="forbidden"))
    adapter = SerperAdapter(_entry())
    with pytest.raises(AuthenticationError):
        await adapter.fetch("web_search", {"query": "x"})
