"""Tests for the Firecrawl adapter."""

import httpx
import pytest
import respx
from openlia.data.adapters.firecrawl import FirecrawlAdapter
from openlia.data.errors import AuthenticationError, DataNotAvailable, RateLimitError
from openlia.data.types import ProviderCategory, ProviderEntry, ProviderMode

_BASE = "https://api.firecrawl.dev"


def _entry(base_url: str = _BASE) -> ProviderEntry:
    return ProviderEntry(
        id="00000000-0000-0000-0000-000000000050",
        kind="firecrawl",
        label="Firecrawl",
        category=ProviderCategory.SEARCH,
        mode=ProviderMode.API_KEY,
        api_key="fc-TEST-KEY",
        base_url=base_url,
    )


def test_declared_metadata() -> None:
    assert FirecrawlAdapter.kind == "firecrawl"
    assert FirecrawlAdapter.category is ProviderCategory.SEARCH
    assert {"web_search", "web_scrape", "web_crawl", "web_map", "web_extract"} == set(
        FirecrawlAdapter.capabilities
    )


async def test_fetch_rejects_unknown_capability() -> None:
    adapter = FirecrawlAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("transcripts", {"query": "x"})
    assert exc.value.provider_kind == "firecrawl"


async def test_web_search_requires_query() -> None:
    adapter = FirecrawlAdapter(_entry())
    with pytest.raises(DataNotAvailable):
        await adapter.fetch("web_search", {})


async def test_web_scrape_requires_url() -> None:
    adapter = FirecrawlAdapter(_entry())
    with pytest.raises(DataNotAvailable):
        await adapter.fetch("web_scrape", {})


@respx.mock
async def test_web_search_sends_bearer_and_returns_payload() -> None:
    route = respx.post(f"{_BASE}/v1/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "title": "T1",
                        "url": "https://example.com",
                        "description": "S1",
                    }
                ]
            },
        )
    )
    adapter = FirecrawlAdapter(_entry())
    result = await adapter.fetch("web_search", {"query": "openlia", "limit": 3})
    assert route.called
    req = route.calls[0].request
    assert req.headers["Authorization"] == "Bearer fc-TEST-KEY"
    assert req.headers["Content-Type"] == "application/json"
    assert b'"query":"openlia"' in req.content
    assert b'"limit":3' in req.content
    assert result.capability == "web_search"
    assert result.payload["data"][0]["url"] == "https://example.com"


@respx.mock
async def test_search_protocol_normalizes_results() -> None:
    respx.post(f"{_BASE}/v1/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"title": "T1", "url": "https://a.test", "description": "S1"},
                    {"title": "T2", "url": "", "description": "skip"},
                    {"title": "T3", "url": "https://b.test", "snippet": "S3"},
                ]
            },
        )
    )
    adapter = FirecrawlAdapter(_entry())
    results = await adapter.search("openlia")
    assert [r.url for r in results] == ["https://a.test", "https://b.test"]
    assert results[0].title == "T1"
    assert results[1].snippet == "S3"


@respx.mock
async def test_unauthorized_raises_auth_error() -> None:
    respx.post(f"{_BASE}/v1/search").mock(
        return_value=httpx.Response(401, text="invalid api key")
    )
    adapter = FirecrawlAdapter(_entry())
    with pytest.raises(AuthenticationError) as exc:
        await adapter.fetch("web_search", {"query": "anything"})
    assert exc.value.status_code == 401


@respx.mock
async def test_rate_limit_propagates() -> None:
    respx.post(f"{_BASE}/v1/search").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "12"}, text="rate limited")
    )
    adapter = FirecrawlAdapter(_entry())
    with pytest.raises(RateLimitError) as exc:
        await adapter.fetch("web_search", {"query": "anything"})
    assert exc.value.retry_after_seconds == 12


@respx.mock
async def test_web_scrape_sends_url() -> None:
    route = respx.post(f"{_BASE}/v1/scrape").mock(
        return_value=httpx.Response(200, json={"data": {"markdown": "# hi"}}),
    )
    adapter = FirecrawlAdapter(_entry())
    result = await adapter.fetch(
        "web_scrape", {"url": "https://example.com", "formats": ["markdown"]}
    )
    assert route.called
    assert b'"url":"https://example.com"' in route.calls[0].request.content
    assert result.payload == {"data": {"markdown": "# hi"}}


def test_constructor_without_base_url_rejected_at_entry() -> None:
    with pytest.raises(ValueError):
        ProviderEntry(
            id="00000000-0000-0000-0000-000000000051",
            kind="firecrawl",
            label="Firecrawl",
            category=ProviderCategory.SEARCH,
            mode=ProviderMode.API_KEY,
            api_key="x",
            base_url=None,
        )
