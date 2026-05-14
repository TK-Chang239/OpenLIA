from __future__ import annotations

from typing import Any, ClassVar

import pytest
from _fakes import FakeDataDispatcher, FakeSearchAdapter
from openlia.llm.runtime.tools import (
    MAX_TOOLS_PER_REQUEST,
    ToolCallResult,
    ToolDispatcher,
    _EscalationCache,
)
from openlia.llm.runtime.web_search import WebSearchResolution, WebSearchResult
from openlia.llm.types import ToolCall, ToolSchema

pytestmark = pytest.mark.asyncio

_MANIFEST = {
    "equity_research": {
        "stock_quote": {
            "name": "stock_quote",
            "description": "Real-time stock quote for a ticker.",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        },
        "financial_statements": {
            "name": "financial_statements",
            "description": "Latest 10-K/10-Q filings.",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        },
    }
}


async def test_build_returns_mapping_tools_plus_request_additional_tools() -> None:
    data = FakeDataDispatcher(manifest=_MANIFEST)
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(available=False, variant=None, adapter=None),
    )
    tools = await disp.build("equity_research", has_web_search=False)
    names = [t.name for t in tools]
    assert "stock_quote" in names
    assert "financial_statements" in names
    assert "request_additional_tools" in names
    assert "web_search" not in names


async def test_build_appends_web_search_when_available() -> None:
    data = FakeDataDispatcher(manifest=_MANIFEST)
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(
            available=True, variant="configured", adapter=FakeSearchAdapter()
        ),
    )
    tools = await disp.build("equity_research", has_web_search=True)
    assert "web_search" in [t.name for t in tools]


async def test_build_omits_web_search_even_if_has_flag_when_unavailable() -> None:
    data = FakeDataDispatcher(manifest=_MANIFEST)
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(available=False, variant=None, adapter=None),
    )
    tools = await disp.build("equity_research", has_web_search=True)
    assert "web_search" not in [t.name for t in tools]


async def test_dispatch_requirement_tool_returns_ok_result() -> None:
    data = FakeDataDispatcher(
        manifest=_MANIFEST,
        results={"stock_quote": {"symbol": "AAPL", "price": 190.5}},
    )
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
    )
    result = await disp.dispatch(
        department_id="equity_research",
        call=ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"}),
    )
    assert isinstance(result, ToolCallResult)
    assert result.ok is True
    assert result.payload == {"symbol": "AAPL", "price": 190.5}
    assert "AAPL" in result.summary


async def test_dispatch_requirement_tool_surfaces_failure_as_ok_false() -> None:
    data = FakeDataDispatcher(manifest=_MANIFEST, raise_for={"stock_quote"})
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
    )
    result = await disp.dispatch(
        department_id="equity_research",
        call=ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"}),
    )
    assert result.ok is False
    assert "Failed" in result.summary


async def test_dispatch_request_additional_tools_hit_adds_tool_for_next_turn() -> None:
    new_tool = {
        "name": "options_chain",
        "description": "Options chain",
        "parameters": {
            "type": "object",
            "properties": {"symbol": {"type": "string"}},
            "required": ["symbol"],
        },
    }
    data = FakeDataDispatcher(
        manifest=_MANIFEST,
        results={"expand::need options chain": new_tool},
    )
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
    )
    before = await disp.build("equity_research", has_web_search=False)
    assert "options_chain" not in [t.name for t in before]

    result = await disp.dispatch(
        department_id="equity_research",
        call=ToolCall(
            id="c1",
            name="request_additional_tools",
            arguments={"reason": "need options chain"},
        ),
    )
    assert result.ok is True
    assert "options_chain" in result.payload.get("added_tools", [])
    after = await disp.build("equity_research", has_web_search=False)
    assert "options_chain" in [t.name for t in after]


async def test_dispatch_request_additional_tools_miss_returns_ok_false() -> None:
    data = FakeDataDispatcher(manifest=_MANIFEST)
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
    )
    result = await disp.dispatch(
        department_id="equity_research",
        call=ToolCall(
            id="c1",
            name="request_additional_tools",
            arguments={"reason": "obscure thing nothing matches"},
        ),
    )
    assert result.ok is False
    assert "no" in result.summary.lower() and "match" in result.summary.lower()


async def test_dispatch_request_additional_tools_dedupes_against_existing() -> None:
    """A second escalation that returns an already-added tool must not
    re-add it nor flap ``ok``."""
    new_tool = {
        "name": "options_chain",
        "description": "Options chain",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }
    data = FakeDataDispatcher(
        manifest=_MANIFEST,
        results={
            "expand::first call": new_tool,
            "expand::second call": new_tool,
        },
    )
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
    )
    r1 = await disp.dispatch(
        department_id="equity_research",
        call=ToolCall(
            id="c1",
            name="request_additional_tools",
            arguments={"reason": "first call"},
        ),
    )
    assert r1.ok is True
    r2 = await disp.dispatch(
        department_id="equity_research",
        call=ToolCall(
            id="c2",
            name="request_additional_tools",
            arguments={"reason": "second call"},
        ),
    )
    # No new tool was added (dedupe), so the second call is ok=False.
    assert r2.ok is False
    after = await disp.build("equity_research", has_web_search=False)
    # The tool still appears exactly once.
    assert [t.name for t in after].count("options_chain") == 1


async def test_dispatch_web_search_configured_calls_adapter() -> None:
    adapter = FakeSearchAdapter(
        results=[WebSearchResult(title="AAPL news", url="https://u", snippet="...")]
    )
    data = FakeDataDispatcher(manifest=_MANIFEST)
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(True, "configured", adapter),
    )
    result = await disp.dispatch(
        department_id="equity_research",
        call=ToolCall(id="c1", name="web_search", arguments={"query": "AAPL earnings"}),
    )
    assert result.ok is True
    assert result.payload["results"][0]["title"] == "AAPL news"


async def test_dispatch_many_runs_in_parallel() -> None:
    data = FakeDataDispatcher(
        manifest=_MANIFEST,
        results={
            "stock_quote": {"symbol": "AAPL", "price": 1},
            "financial_statements": {"symbol": "AAPL", "filings": []},
        },
    )
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
    )
    results = await disp.dispatch_many(
        department_id="equity_research",
        calls=[
            ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"}),
            ToolCall(id="c2", name="financial_statements", arguments={"symbol": "AAPL"}),
        ],
    )
    assert len(results) == 2
    assert all(r.ok for r in results)
    assert [r.call_id for r in results] == ["c1", "c2"]


async def test_response_normalization_caps_arrays() -> None:
    from openlia.llm.runtime.tools import _normalize_payload

    big = {"items": list(range(100)), "nullable": None, "ok": True}
    out = _normalize_payload(big, max_array_len=10)
    assert len(out["items"]) == 10
    assert out["truncated"] is True
    assert "nullable" not in out
    assert out["ok"] is True


async def test_response_normalization_leaves_small_arrays_alone() -> None:
    from openlia.llm.runtime.tools import _normalize_payload

    out = _normalize_payload({"items": [1, 2, 3]}, max_array_len=10)
    assert out == {"items": [1, 2, 3]}


async def test_build_appends_extra_tools() -> None:
    data = FakeDataDispatcher(manifest={"secretary": {}})
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
    )
    extra = (
        {
            "name": "suggest_redirect",
            "description": "Suggest a specialist department.",
            "parameters": {
                "type": "object",
                "properties": {"department": {"type": "string"}},
                "required": ["department"],
            },
        },
    )
    tools = await disp.build("secretary", has_web_search=False, extra_tools=extra)
    assert [t.name for t in tools] == ["suggest_redirect"]


async def test_dispatch_extra_tool_echoes_arguments_into_structured() -> None:
    data = FakeDataDispatcher(manifest={"secretary": {}})
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
    )
    call = ToolCall(
        id="c1",
        name="suggest_redirect",
        arguments={"department": "equity_research", "reason": "needs research"},
    )
    result: ToolCallResult = await disp.dispatch(
        department_id="secretary",
        call=call,
        extra_tool_names=frozenset({"suggest_redirect"}),
    )
    assert result.ok is True
    assert result.structured == {
        "department": "equity_research",
        "reason": "needs research",
    }


async def test_dispatch_known_data_tool_ignores_extra_tool_names() -> None:
    # Ensure extra_tool_names only diverts calls that actually match.
    data = FakeDataDispatcher(manifest=_MANIFEST, results={"stock_quote": {"symbol": "AAPL"}})
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
    )
    call = ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"})
    result = await disp.dispatch(
        department_id="equity_research",
        call=call,
        extra_tool_names=frozenset({"suggest_redirect"}),
    )
    assert result.ok is True
    assert result.structured is None


def _bulk_manifest(department_id: str, count: int) -> dict[str, dict[str, Any]]:
    return {
        department_id: {
            f"tool_{i:03d}": {
                "name": f"tool_{i:03d}",
                "description": f"Tool number {i}.",
                "parameters": {"type": "object", "properties": {}},
            }
            for i in range(count)
        }
    }


async def test_build_caps_total_tools_at_provider_limit() -> None:
    # 130 mapped tools + request_additional_tools + web_search would be 132
    # — OpenAI rejects anything past 128.
    data = FakeDataDispatcher(manifest=_bulk_manifest("equity_research", 130))
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(
            available=True, variant="configured", adapter=FakeSearchAdapter()
        ),
    )
    tools = await disp.build("equity_research", has_web_search=True)
    assert len(tools) == MAX_TOOLS_PER_REQUEST
    names = [t.name for t in tools]
    # Meta-tools must be preserved — they enable escalation and search.
    assert "request_additional_tools" in names
    assert "web_search" in names
    # The truncated mapped slice keeps the head, in declaration order.
    assert "tool_000" in names
    assert "tool_125" in names
    assert "tool_129" not in names


async def test_build_caps_preserves_expanded_over_mapped() -> None:
    # When over the cap, tools the LLM explicitly escalated for must
    # survive at the expense of warm-up mapped tools.
    data = FakeDataDispatcher(manifest=_bulk_manifest("equity_research", 130))
    expanded_entry: dict[str, Any] = {
        "name": "escalated_specialty_tool",
        "description": "Added via request_additional_tools mid-run.",
        "parameters": {"type": "object", "properties": {}},
    }
    data.results["expand::needed"] = expanded_entry
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
    )
    # Trigger escalation so `escalated_specialty_tool` lands in _expanded.
    await disp._dispatch_request_additional_tools(
        "equity_research",
        ToolCall(id="c1", name="request_additional_tools", arguments={"reason": "needed"}),
    )
    tools = await disp.build("equity_research", has_web_search=False)
    names = [t.name for t in tools]
    assert len(tools) == MAX_TOOLS_PER_REQUEST
    assert "escalated_specialty_tool" in names
    assert "request_additional_tools" in names


async def test_build_under_cap_unchanged() -> None:
    # Sanity: small manifests still flow through unchanged.
    data = FakeDataDispatcher(manifest=_MANIFEST)
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
    )
    tools = await disp.build("equity_research", has_web_search=False)
    assert len(tools) == 3  # 2 mapped + request_additional_tools


# ---------------------------------------------------------------------------
# _EscalationCache unit tests
# ---------------------------------------------------------------------------


def _make_schema(name: str) -> ToolSchema:
    return ToolSchema(name=name, description=f"{name} desc", parameters={})


@pytest.mark.filterwarnings("ignore::pytest.PytestWarning")
class TestEscalationCache:
    pytestmark: ClassVar[list] = []  # override module-level asyncio marker; these are sync tests

    def test_add_returns_newly_added_names(self) -> None:
        cache = _EscalationCache()
        added = cache.add("dept_a", [_make_schema("alpha"), _make_schema("beta")])
        assert added == ["alpha", "beta"]

    def test_add_ignores_duplicates(self) -> None:
        cache = _EscalationCache()
        cache.add("dept_a", [_make_schema("alpha")])
        added = cache.add("dept_a", [_make_schema("alpha"), _make_schema("gamma")])
        assert added == ["gamma"]

    def test_for_emission_returns_addition_order(self) -> None:
        cache = _EscalationCache()
        cache.add("dept_a", [_make_schema("alpha"), _make_schema("beta"), _make_schema("gamma")])
        schemas = cache.for_emission("dept_a")
        assert [s.name for s in schemas] == ["alpha", "beta", "gamma"]

    def test_for_emission_unchanged_after_touch(self) -> None:
        cache = _EscalationCache()
        cache.add("dept_a", [_make_schema("alpha"), _make_schema("beta"), _make_schema("gamma")])
        cache.touch("dept_a", "alpha")
        schemas = cache.for_emission("dept_a")
        assert [s.name for s in schemas] == ["alpha", "beta", "gamma"]

    def test_lru_order_puts_touched_name_last(self) -> None:
        cache = _EscalationCache()
        cache.add("dept_a", [_make_schema("alpha"), _make_schema("beta"), _make_schema("gamma")])
        cache.touch("dept_a", "alpha")
        assert cache.lru_order("dept_a") == ["beta", "gamma", "alpha"]

    def test_lru_order_multiple_touches(self) -> None:
        cache = _EscalationCache()
        cache.add("dept_a", [_make_schema("alpha"), _make_schema("beta"), _make_schema("gamma")])
        cache.touch("dept_a", "alpha")
        cache.touch("dept_a", "beta")
        # beta touched last => MRU last; alpha touched before beta => second-to-last
        assert cache.lru_order("dept_a") == ["gamma", "alpha", "beta"]

    def test_touch_nonexistent_name_is_noop(self) -> None:
        cache = _EscalationCache()
        cache.add("dept_a", [_make_schema("alpha")])
        cache.touch("dept_a", "nonexistent")  # must not raise
        assert cache.lru_order("dept_a") == ["alpha"]

    def test_for_emission_empty_department_returns_empty(self) -> None:
        cache = _EscalationCache()
        assert cache.for_emission("missing") == []

    def test_lru_order_empty_department_returns_empty(self) -> None:
        cache = _EscalationCache()
        assert cache.lru_order("missing") == []

    def test_has_any_false_on_empty(self) -> None:
        cache = _EscalationCache()
        assert cache.has_any("dept_a") is False

    def test_has_any_true_after_add(self) -> None:
        cache = _EscalationCache()
        cache.add("dept_a", [_make_schema("alpha")])
        assert cache.has_any("dept_a") is True

    def test_per_department_isolation(self) -> None:
        cache = _EscalationCache()
        cache.add("dept_a", [_make_schema("alpha")])
        assert cache.for_emission("dept_b") == []
        assert cache.has_any("dept_b") is False
        cache.add("dept_b", [_make_schema("beta")])
        assert [s.name for s in cache.for_emission("dept_a")] == ["alpha"]
        assert [s.name for s in cache.for_emission("dept_b")] == ["beta"]

    def test_add_empty_iterable_does_not_create_department_key(self) -> None:
        cache = _EscalationCache()
        result = cache.add("dept_a", [])
        assert result == []
        assert cache.has_any("dept_a") is False
        # Verify no ghost keys leaked into internal state:
        # has_any should return False because the key doesn't exist OR the value is empty.
        # Either is acceptable; the important invariant is has_any False.

    def test_touch_unknown_department_is_noop(self) -> None:
        cache = _EscalationCache()
        cache.touch("nonexistent_dept", "alpha")  # must not raise
        assert cache.lru_order("nonexistent_dept") == []


# ---------------------------------------------------------------------------
# TraceRecorder plumbing tests
# ---------------------------------------------------------------------------


@pytest.mark.filterwarnings("ignore::pytest.PytestWarning")
class TestTracePlumbing:
    pytestmark: ClassVar[list] = []  # override module-level asyncio marker; these are sync tests

    def _make_dispatcher(self, **kwargs) -> ToolDispatcher:
        return ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(manifest=_MANIFEST),
            web_search=WebSearchResolution(available=False, variant=None, adapter=None),
            **kwargs,
        )

    def test_trace_defaults_to_noop(self) -> None:
        disp = self._make_dispatcher()
        assert callable(disp._trace)
        result = disp._trace("cat", "msg", {"key": "val"})
        assert result is None

    def test_trace_uses_provided_recorder(self) -> None:
        calls: list[tuple[str, str, dict[str, Any] | None]] = []

        def recorder(category: str, message: str, payload: dict[str, Any] | None) -> None:
            calls.append((category, message, payload))

        disp = self._make_dispatcher(trace=recorder)
        disp._trace("cat", "msg", {"key": "val"})
        assert calls == [("cat", "msg", {"key": "val"})]

    @pytest.mark.asyncio
    async def test_dispatch_paths_do_not_emit_traces_yet(self) -> None:
        """PR1.4 only adds plumbing; subsequent PRs will populate traces."""
        calls: list[tuple[str, str, dict[str, Any] | None]] = []

        def recorder(category: str, message: str, payload: dict[str, Any] | None) -> None:
            calls.append((category, message, payload))

        new_tool = {
            "name": "tool_a",
            "description": "d",
            "parameters": {},
        }
        data = FakeDataDispatcher(
            manifest={"dept_a": {"tool_a": new_tool}},
            results={"expand::test": new_tool},
        )
        disp = ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(available=False, variant=None, adapter=None),
            trace=recorder,
        )

        # Exercise build()
        await disp.build("dept_a", has_web_search=False)

        # Exercise dispatch() with a builtin (request_additional_tools)
        await disp.dispatch(
            department_id="dept_a",
            call=ToolCall(id="c1", name="request_additional_tools", arguments={"reason": "test"}),
        )

        # Exercise dispatch() with a requirement tool
        await disp.dispatch(
            department_id="dept_a",
            call=ToolCall(id="c2", name="tool_a", arguments={}),
        )

        assert calls == []


# ---------------------------------------------------------------------------
# Handler-table dispatch tests
# ---------------------------------------------------------------------------


class TestDispatchHandlerTable:
    """Pin the handler-table routing introduced in PR1.2.

    All four branches of dispatch() are covered:
      1. request_additional_tools  -> handler table -> _dispatch_request_additional_tools
      2. web_search                -> handler table -> _dispatch_web_search
      3. unknown built-in name     -> fallthrough   -> _dispatch_requirement
      4. name in extra_tool_names  -> echo branch   -> _dispatch_structured_echo
         (precedence: checked BEFORE the handler table)
    """

    pytestmark: ClassVar[list] = [pytest.mark.asyncio]

    async def test_request_additional_tools_routes_via_handler_table(self) -> None:
        new_tool = {
            "name": "sector_etf",
            "description": "Sector ETF flows.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }
        data = FakeDataDispatcher(
            manifest=_MANIFEST,
            results={"expand::sector data": new_tool},
        )
        disp = ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        )
        result = await disp.dispatch(
            department_id="equity_research",
            call=ToolCall(
                id="ht1",
                name="request_additional_tools",
                arguments={"reason": "sector data"},
            ),
        )
        # expand_tools was called — new tool added means ok=True and payload reflects it.
        assert result.ok is True
        assert "sector_etf" in result.payload.get("added_tools", [])

    async def test_web_search_routes_via_handler_table(self) -> None:
        adapter = FakeSearchAdapter(
            results=[WebSearchResult(title="Handler table hit", url="https://x", snippet="ok")]
        )
        data = FakeDataDispatcher(manifest=_MANIFEST)
        disp = ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(True, "configured", adapter),
        )
        result = await disp.dispatch(
            department_id="equity_research",
            call=ToolCall(id="ht2", name="web_search", arguments={"query": "handler table"}),
        )
        assert result.ok is True
        assert result.payload["results"][0]["title"] == "Handler table hit"

    async def test_unknown_name_falls_through_to_dispatch_requirement(self) -> None:
        data = FakeDataDispatcher(
            manifest=_MANIFEST,
            results={"fmp__quote": {"symbol": "MSFT", "price": 420.0}},
        )
        disp = ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        )
        result = await disp.dispatch(
            department_id="equity_research",
            call=ToolCall(id="ht3", name="fmp__quote", arguments={"symbol": "MSFT"}),
        )
        # Falls through to _dispatch_requirement which hits FakeDataDispatcher.dispatch_requirement.
        assert result.ok is True
        assert result.payload.get("symbol") == "MSFT"
        assert result.structured is None

    async def test_extra_tool_names_echo_beats_handler_table(self) -> None:
        # web_search is in both the handler table AND extra_tool_names.
        # The extra_tool_names branch must win (checked first).
        adapter = FakeSearchAdapter()
        data = FakeDataDispatcher(manifest=_MANIFEST)
        disp = ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(True, "configured", adapter),
        )
        call = ToolCall(id="ht4", name="web_search", arguments={"query": "should echo"})
        result = await disp.dispatch(
            department_id="equity_research",
            call=call,
            extra_tool_names=frozenset({"web_search"}),
        )
        # Echo path: ok=True, structured carries the arguments, payload is {"ack": True}.
        assert result.ok is True
        assert result.structured == {"query": "should echo"}
        assert result.payload == {"ack": True}


# ---------------------------------------------------------------------------
# _pack_for_provider unit tests
# ---------------------------------------------------------------------------


def _make_dispatcher() -> ToolDispatcher:
    data = FakeDataDispatcher(manifest={})
    return ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(available=False, variant=None, adapter=None),
    )


@pytest.mark.filterwarnings("ignore::pytest.PytestWarning")
class TestPackForProvider:
    pytestmark: ClassVar[list] = []  # sync tests; override module-level asyncio marker

    def test_under_budget_passthrough(self) -> None:
        disp = _make_dispatcher()
        a, b, c, t1 = _make_schema("a"), _make_schema("b"), _make_schema("c"), _make_schema("t1")
        result = disp._pack_for_provider(mapped=[a, b], expanded=[c], tail=[t1])
        assert result == [a, b, c, t1]

    def test_at_cap_no_truncation(self) -> None:
        disp = _make_dispatcher()
        tail = [_make_schema(f"tail_{i}") for i in range(2)]
        budget = MAX_TOOLS_PER_REQUEST - len(tail)
        mapped = [_make_schema(f"m_{i}") for i in range(budget // 2)]
        expanded = [_make_schema(f"e_{i}") for i in range(budget - len(mapped))]
        result = disp._pack_for_provider(mapped=mapped, expanded=expanded, tail=tail)
        assert result == mapped + expanded + tail

    def test_over_cap_truncates_mapped_first(self) -> None:
        disp = _make_dispatcher()
        tail = [_make_schema("t1"), _make_schema("t2")]
        expanded = [_make_schema("e1"), _make_schema("e2")]
        # mapped is large enough to push total over cap
        mapped = [_make_schema(f"m_{i}") for i in range(MAX_TOOLS_PER_REQUEST)]
        result = disp._pack_for_provider(mapped=mapped, expanded=expanded, tail=tail)
        assert len(result) == MAX_TOOLS_PER_REQUEST
        names = [t.name for t in result]
        # tail preserved
        assert "t1" in names
        assert "t2" in names
        # expanded preserved
        assert "e1" in names
        assert "e2" in names

    def test_expanded_preserved_over_mapped(self) -> None:
        disp = _make_dispatcher()
        tail = [_make_schema("t1")]
        expanded = [_make_schema(f"e_{i}") for i in range(10)]
        # mapped large enough to force truncation
        mapped = [_make_schema(f"m_{i}") for i in range(MAX_TOOLS_PER_REQUEST)]
        result = disp._pack_for_provider(mapped=mapped, expanded=expanded, tail=tail)
        names = [t.name for t in result]
        # all expanded items survive
        for i in range(10):
            assert f"e_{i}" in names

    def test_pathological_tail_exceeds_cap(self) -> None:
        disp = _make_dispatcher()
        tail = [_make_schema(f"tail_{i}") for i in range(MAX_TOOLS_PER_REQUEST + 5)]
        mapped = [_make_schema("m1")]
        expanded = [_make_schema("e1")]
        result = disp._pack_for_provider(mapped=mapped, expanded=expanded, tail=tail)
        assert len(result) == MAX_TOOLS_PER_REQUEST
        # mapped and expanded are dropped; result is tail slice
        names = [t.name for t in result]
        assert "m1" not in names
        assert "e1" not in names

    def test_empty_inputs(self) -> None:
        disp = _make_dispatcher()
        t1 = _make_schema("t1")
        result = disp._pack_for_provider(mapped=[], expanded=[], tail=[t1])
        assert result == [t1]
