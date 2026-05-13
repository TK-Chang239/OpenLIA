from __future__ import annotations

from dataclasses import dataclass

import pytest
from openlia.llm.runtime.web_search import (
    WebSearchAdapter,
    WebSearchResult,
    resolve_web_search,
)
from openlia.llm.types import Capabilities, ProviderCredentials, ResolvedModel

pytestmark = pytest.mark.asyncio


def _resolved(*, web_search_native: bool) -> ResolvedModel:
    return ResolvedModel(
        provider_kind="openai",
        provider_id="p1",
        model_id="m1",
        model_ref="gpt-5.4",
        credentials=ProviderCredentials(api_key="sk", base_url=None),
        capabilities=Capabilities(
            streaming=True,
            tool_calling=True,
            structured_output=True,
            vision=False,
            web_search_native=web_search_native,
        ),
        overrides={},
    )


@dataclass
class _FakeAdapter:
    name: str = "brave"
    will_return: list[WebSearchResult] | None = None

    async def search(self, query: str) -> list[WebSearchResult]:
        if self.will_return is None:
            return [WebSearchResult(title=f"Result for {query}", url="https://x", snippet="s")]
        return self.will_return


async def test_native_preferred_when_available() -> None:
    resolution = resolve_web_search(
        resolved=_resolved(web_search_native=True),
        search_adapter_factory=lambda: _FakeAdapter(),
    )
    assert resolution.available is True
    assert resolution.variant == "native"
    assert resolution.adapter is None


async def test_falls_back_to_configured_when_native_unavailable() -> None:
    adapter = _FakeAdapter(name="tavily")
    resolution = resolve_web_search(
        resolved=_resolved(web_search_native=False),
        search_adapter_factory=lambda: adapter,
    )
    assert resolution.available is True
    assert resolution.variant == "configured"
    assert resolution.adapter is adapter


async def test_unavailable_when_no_native_and_no_configured() -> None:
    resolution = resolve_web_search(
        resolved=_resolved(web_search_native=False),
        search_adapter_factory=lambda: None,
    )
    assert resolution.available is False
    assert resolution.variant is None
    assert resolution.adapter is None


async def test_configured_adapter_search_returns_normalized_results() -> None:
    adapter = _FakeAdapter(will_return=[WebSearchResult(title="T", url="https://u", snippet="S")])
    results = await adapter.search("AAPL earnings")
    assert results[0].title == "T"
    assert results[0].url == "https://u"
    assert results[0].snippet == "S"


async def test_web_search_adapter_protocol_accepts_any_async_callable() -> None:
    class _Custom:
        async def search(self, query: str) -> list[WebSearchResult]:
            return [WebSearchResult(title=query, url="https://q", snippet="")]

    a: WebSearchAdapter = _Custom()
    out = await a.search("x")
    assert out[0].title == "x"
