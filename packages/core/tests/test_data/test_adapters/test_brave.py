"""Tests for the Brave Search adapter."""

import httpx
import pytest
import respx
from openlia.data.adapters.brave import BraveSearchAdapter
from openlia.data.errors import AuthenticationError, DataNotAvailable, RateLimitError
from openlia.data.types import ProviderCategory, ProviderEntry, ProviderMode

_BASE = "https://api.search.brave.com/res/v1"


def _entry(base_url: str = _BASE) -> ProviderEntry:
    return ProviderEntry(
        id="00000000-0000-0000-0000-000000000020",
        kind="brave",
        label="Brave",
        category=ProviderCategory.SEARCH,
        mode=ProviderMode.API_KEY,
        api_key="TEST-KEY",
        base_url=base_url,
    )


def test_declared_metadata() -> None:
    assert BraveSearchAdapter.kind == "brave"
    assert BraveSearchAdapter.category is ProviderCategory.SEARCH
    expected = {"web_search", "news_search", "image_search", "video_search", "summarizer"}
    assert expected <= BraveSearchAdapter.capabilities


async def test_fetch_rejects_unknown_capability() -> None:
    adapter = BraveSearchAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("transcripts", {"query": "x"})
    assert exc.value.provider_kind == "brave"


async def test_fetch_requires_query() -> None:
    adapter = BraveSearchAdapter(_entry())
    with pytest.raises(DataNotAvailable):
        await adapter.fetch("web_search", {})


@respx.mock
async def test_web_search_sends_token_header_and_returns_payload() -> None:
    route = respx.get(f"{_BASE}/web/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "web": {"results": [{"title": "t", "url": "https://x.test", "description": "d"}]}
            },
        )
    )
    adapter = BraveSearchAdapter(_entry())
    result = await adapter.fetch("web_search", {"query": "openlia", "count": 5})
    assert route.called
    request = route.calls[0].request
    assert request.headers["X-Subscription-Token"] == "TEST-KEY"
    assert request.headers["Accept"] == "application/json"
    assert "q=openlia" in str(request.url)
    assert "count=5" in str(request.url)
    assert result.capability == "web_search"
    assert result.payload["web"]["results"][0]["url"] == "https://x.test"


@respx.mock
async def test_search_protocol_normalizes_results() -> None:
    respx.get(f"{_BASE}/web/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {"title": "T1", "url": "https://a.test", "description": "S1"},
                        {"title": "T2", "url": "", "description": "skip-me"},
                        {"title": "T3", "url": "https://b.test", "description": "S3"},
                    ]
                }
            },
        )
    )
    adapter = BraveSearchAdapter(_entry())
    out = await adapter.search("hello")
    assert [r.url for r in out] == ["https://a.test", "https://b.test"]
    assert out[0].title == "T1"
    assert out[0].snippet == "S1"


@respx.mock
async def test_news_search_routes_to_news_path() -> None:
    route = respx.get(f"{_BASE}/news/search").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    adapter = BraveSearchAdapter(_entry())
    await adapter.fetch("news_search", {"query": "tesla", "country": "us"})
    assert route.called
    url = str(route.calls[0].request.url)
    assert "q=tesla" in url and "country=us" in url


@respx.mock
async def test_local_pois_requires_ids() -> None:
    adapter = BraveSearchAdapter(_entry())
    with pytest.raises(DataNotAvailable):
        await adapter.fetch("local_pois", {})


@respx.mock
async def test_summarizer_requires_key() -> None:
    adapter = BraveSearchAdapter(_entry())
    with pytest.raises(DataNotAvailable):
        await adapter.fetch("summarizer", {})


@respx.mock
async def test_auth_error_on_401() -> None:
    respx.get(f"{_BASE}/web/search").mock(return_value=httpx.Response(401, text="bad token"))
    adapter = BraveSearchAdapter(_entry())
    with pytest.raises(AuthenticationError):
        await adapter.fetch("web_search", {"query": "x"})


@respx.mock
async def test_rate_limit_raises_after_retries(monkeypatch) -> None:
    import openlia.data._http as _http

    async def _no_sleep(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(_http.asyncio, "sleep", _no_sleep)
    respx.get(f"{_BASE}/web/search").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "1"})
    )
    adapter = BraveSearchAdapter(_entry())
    with pytest.raises(RateLimitError) as exc:
        await adapter.fetch("web_search", {"query": "x"})
    assert exc.value.provider_kind == "brave"


@respx.mock
async def test_health_check_true_on_200() -> None:
    respx.get(f"{_BASE}/web/search").mock(return_value=httpx.Response(200, json={"web": {}}))
    adapter = BraveSearchAdapter(_entry())
    assert await adapter.health_check() is True


@respx.mock
async def test_health_check_false_on_401() -> None:
    respx.get(f"{_BASE}/web/search").mock(return_value=httpx.Response(401))
    adapter = BraveSearchAdapter(_entry())
    assert await adapter.health_check() is False
