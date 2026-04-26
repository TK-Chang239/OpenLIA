"""Tests for the Reddit adapter."""

import httpx
import pytest
import respx
from openlia.data.adapters.reddit import RedditAdapter
from openlia.data.errors import AuthenticationError, DataNotAvailable
from openlia.data.types import ProviderCategory, ProviderEntry, ProviderMode

_BASE = "https://oauth.reddit.com"
_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"


def _entry(
    *,
    api_key: str | None = "client-id-123:client-secret-abc",
    user_agent: str = "openlia-test/1.0 by /u/openlia",
    grant_type: str | None = None,
    extra: dict | None = None,
) -> ProviderEntry:
    cfg: dict = {"user_agent": user_agent}
    if grant_type:
        cfg["grant_type"] = grant_type
    if extra:
        cfg.update(extra)
    return ProviderEntry(
        id="00000000-0000-0000-0000-000000000023",
        kind="reddit",
        label="Reddit",
        category=ProviderCategory.SOCIAL_MEDIA,
        mode=ProviderMode.API_KEY,
        api_key=api_key,
        base_url=_BASE,
        extra_config=cfg,
    )


def test_declared_metadata() -> None:
    assert RedditAdapter.kind == "reddit"
    assert RedditAdapter.category is ProviderCategory.SOCIAL_MEDIA
    assert "social_sentiment" in RedditAdapter.capabilities
    assert "company_news" in RedditAdapter.capabilities
    assert "subreddit_hot" in RedditAdapter.capabilities


def test_requires_colon_separated_credentials() -> None:
    with pytest.raises(ValueError, match="client_id:client_secret"):
        RedditAdapter(_entry(api_key="onlyone"))


def test_requires_user_agent() -> None:
    with pytest.raises(ValueError, match="user_agent"):
        RedditAdapter(_entry(user_agent=""))


@respx.mock
async def test_social_sentiment_fetches_token_then_search() -> None:
    token_route = respx.post(_TOKEN_URL).mock(
        return_value=httpx.Response(
            200, json={"access_token": "TOKEN-1", "expires_in": 3600, "token_type": "bearer"}
        )
    )
    search_route = respx.get(f"{_BASE}/search").mock(
        return_value=httpx.Response(200, json={"data": {"children": []}})
    )
    adapter = RedditAdapter(_entry())
    await adapter.fetch("social_sentiment", {"symbol": "AAPL"})
    assert token_route.called
    assert search_route.called
    token_req = token_route.calls[0].request
    assert token_req.headers["User-Agent"].startswith("openlia-test")
    assert token_req.headers["Authorization"].startswith("Basic ")
    body = token_req.read().decode()
    assert "grant_type=client_credentials" in body
    search_req = search_route.calls[0].request
    assert search_req.headers["Authorization"] == "Bearer TOKEN-1"
    url = str(search_req.url)
    assert "q=AAPL" in url
    assert "type=link" in url


@respx.mock
async def test_token_cached_across_calls() -> None:
    token_route = respx.post(_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "TOKEN-1", "expires_in": 3600})
    )
    respx.get(f"{_BASE}/search").mock(
        return_value=httpx.Response(200, json={"data": {"children": []}})
    )
    adapter = RedditAdapter(_entry())
    await adapter.fetch("social_sentiment", {"symbol": "AAPL"})
    await adapter.fetch("social_sentiment", {"symbol": "MSFT"})
    assert token_route.call_count == 1


@respx.mock
async def test_company_news_uses_default_subs_and_restrict_sr() -> None:
    respx.post(_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "TOK", "expires_in": 3600})
    )
    route = respx.get(f"{_BASE}/r/investing,stocks,wallstreetbets/search").mock(
        return_value=httpx.Response(200, json={"data": {"children": []}})
    )
    adapter = RedditAdapter(_entry())
    await adapter.fetch("company_news", {"symbol": "TSLA"})
    assert route.called
    url = str(route.calls[0].request.url)
    assert "restrict_sr=true" in url


@respx.mock
async def test_subreddit_hot_with_explicit_subreddit() -> None:
    respx.post(_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "TOK", "expires_in": 3600})
    )
    route = respx.get(f"{_BASE}/r/wallstreetbets/hot").mock(
        return_value=httpx.Response(200, json={"data": {"children": []}})
    )
    adapter = RedditAdapter(_entry())
    await adapter.fetch("subreddit_hot", {"subreddit": "wallstreetbets", "limit": 10})
    assert route.called
    assert "limit=10" in str(route.calls[0].request.url)


async def test_subreddit_hot_requires_subreddit() -> None:
    adapter = RedditAdapter(_entry())
    with pytest.raises(DataNotAvailable):
        await adapter.fetch("subreddit_hot", {})


@respx.mock
async def test_password_grant_requires_credentials() -> None:
    adapter = RedditAdapter(_entry(grant_type="password"))
    # token endpoint never reached because credential check fails first
    with pytest.raises(AuthenticationError, match="username"):
        await adapter.fetch("social_sentiment", {"symbol": "AAPL"})


@respx.mock
async def test_token_401_raises_auth_error() -> None:
    respx.post(_TOKEN_URL).mock(return_value=httpx.Response(401, text="bad creds"))
    adapter = RedditAdapter(_entry())
    with pytest.raises(AuthenticationError):
        await adapter.fetch("social_sentiment", {"symbol": "AAPL"})


@respx.mock
async def test_health_check_true_when_token_obtained() -> None:
    respx.post(_TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "TOK", "expires_in": 3600})
    )
    adapter = RedditAdapter(_entry())
    assert await adapter.health_check() is True


@respx.mock
async def test_health_check_false_on_token_failure() -> None:
    respx.post(_TOKEN_URL).mock(return_value=httpx.Response(401))
    adapter = RedditAdapter(_entry())
    assert await adapter.health_check() is False
