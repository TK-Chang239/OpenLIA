"""Tests for CacheWrappedAdapter and build_cache_key."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openlia.llm.runtime.report_v2.connectors.base import ToolKind, ToolMeta, ToolResult
from openlia.llm.runtime.report_v2.connectors.cache_wrapper import (
    CacheWrappedAdapter,
    build_cache_key,
)

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


@dataclass
class FakeCacheDoc:
    content_text: str
    raw_metadata: dict = field(default_factory=dict)


class FakeStore:
    def __init__(self) -> None:
        self._data: dict[str, FakeCacheDoc] = {}
        self.upsert_calls: list[tuple[str, ToolResult]] = []

    def get(self, key: str) -> FakeCacheDoc | None:
        return self._data.get(key)

    def upsert(self, key: str, result: ToolResult, **meta: Any) -> None:
        self.upsert_calls.append((key, result))
        self._data[key] = FakeCacheDoc(
            content_text=str(result.content),
            raw_metadata=dict(result.metadata),
        )


class FakeAdapter:
    name = "fake"
    tool_kind: ToolKind = "internal"
    cacheable = True
    call_count = 0

    def __init__(self, tools: list[ToolMeta]) -> None:
        self._tools = tools
        self.call_count = 0

    def list_tools(self) -> list[ToolMeta]:
        return self._tools

    def call(self, tool: str, params: dict) -> ToolResult:
        self.call_count += 1
        return ToolResult(content=f"data:{tool}", metadata={"ts": "2026"})


def make_adapter(cacheable_tool: bool = True) -> FakeAdapter:
    tools = [
        ToolMeta(name="get_financials", description="Financials", cacheable=cacheable_tool),
        ToolMeta(name="get_live_price", description="Live price", cacheable=False),
    ]
    return FakeAdapter(tools)


# ---------------------------------------------------------------------------
# build_cache_key tests
# ---------------------------------------------------------------------------


def test_cache_key_with_ticker_and_fiscal_period():
    key = build_cache_key("eodhd", "get_financials", {"ticker": "AAPL", "fiscal_period": "2024Q1"})
    assert key == "eodhd:get_financials:AAPL:2024Q1"


def test_cache_key_no_fiscal_period_uses_hash():
    params = {"ticker": "MSFT", "limit": 10}
    key = build_cache_key("eodhd", "get_news", params)
    parts = key.split(":")
    assert parts[0] == "eodhd"
    assert parts[1] == "get_news"
    assert parts[2] == "MSFT"
    assert len(parts[3]) == 12  # sha256 first 12 chars


def test_cache_key_no_ticker_uses_underscore():
    key = build_cache_key("web", "search", {"query": "earnings"})
    parts = key.split(":")
    assert parts[2] == "_"


def test_cache_key_deterministic():
    params = {"ticker": "GOOG", "limit": 5}
    assert build_cache_key("sdk", "call", params) == build_cache_key("sdk", "call", params)


# ---------------------------------------------------------------------------
# CacheWrappedAdapter tests
# ---------------------------------------------------------------------------


def test_miss_then_hit():
    """First call is a miss (upstream called); second call is a hit (cached)."""
    adapter = make_adapter(cacheable_tool=True)
    store = FakeStore()
    wrapped = CacheWrappedAdapter(adapter, store)

    result1 = wrapped.call("get_financials", {"ticker": "AAPL", "fiscal_period": "2024Q1"})
    assert result1.served_from_cache is False
    assert adapter.call_count == 1
    assert len(store.upsert_calls) == 1

    result2 = wrapped.call("get_financials", {"ticker": "AAPL", "fiscal_period": "2024Q1"})
    assert result2.served_from_cache is True
    assert adapter.call_count == 1  # no additional upstream call
    assert result2.content == "data:get_financials"


def test_force_refresh_bypasses_cache():
    """force_refresh=True skips cache read and re-upserts."""
    adapter = make_adapter(cacheable_tool=True)
    store = FakeStore()
    wrapped = CacheWrappedAdapter(adapter, store)

    wrapped.call("get_financials", {"ticker": "AAPL", "fiscal_period": "2024Q1"})
    assert adapter.call_count == 1

    result = wrapped.call(
        "get_financials",
        {"ticker": "AAPL", "fiscal_period": "2024Q1"},
        force_refresh=True,
    )
    assert result.served_from_cache is False
    assert adapter.call_count == 2
    assert len(store.upsert_calls) == 2


def test_non_cacheable_tool_not_stored():
    """Tools with cacheable=False pass through and are never upserted."""
    adapter = make_adapter(cacheable_tool=True)
    store = FakeStore()
    wrapped = CacheWrappedAdapter(adapter, store)

    result = wrapped.call("get_live_price", {"ticker": "TSLA"})
    assert result.served_from_cache is False
    assert adapter.call_count == 1
    assert len(store.upsert_calls) == 0


def test_tool_meta_cacheable_flag_governs_not_adapter_flag():
    """Even if adapter.cacheable=True, per-tool ToolMeta.cacheable=False skips cache."""
    adapter = make_adapter(cacheable_tool=False)  # both tools non-cacheable
    store = FakeStore()
    wrapped = CacheWrappedAdapter(adapter, store)

    wrapped.call("get_financials", {"ticker": "AAPL", "fiscal_period": "2024Q1"})
    assert len(store.upsert_calls) == 0  # not stored


def test_proxy_properties():
    adapter = make_adapter()
    wrapped = CacheWrappedAdapter(adapter, FakeStore())
    assert wrapped.name == "fake"
    assert wrapped.tool_kind == "internal"
    assert wrapped.cacheable is True
    assert len(wrapped.list_tools()) == 2
