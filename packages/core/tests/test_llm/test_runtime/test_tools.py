from __future__ import annotations

from typing import Any, ClassVar
from unittest.mock import patch

import pytest
from _fakes import FakeDataDispatcher, FakeSearchAdapter
from openlia.llm.runtime.schema_slim import (
    TOOL_DESCRIPTION_MAX_CHARS,
    SchemaSlimSystemicFailure,
)
from openlia.llm.runtime.tools import (
    _READ_PAYLOAD_NAME,
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


async def test_build_includes_request_additional_tools_with_empty_starter_pack() -> None:
    # Phase B contract: the report bridge returns an empty starter pack
    # (`list_requirement_tools` -> []) and the LLM is expected to escalate
    # for every data tool via `request_additional_tools`. The meta-tool
    # must therefore be exposed even when there are no mapped tools and
    # no cached escalation entries — otherwise the model has no entry
    # point to load data tools and the system prompt's promise is broken.
    data = FakeDataDispatcher(manifest={})
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
    )
    tools = await disp.build("equity_research", has_web_search=False)
    names = [t.name for t in tools]
    assert "request_additional_tools" in names
    assert "read_payload" in names


async def test_build_keeps_request_additional_tools_across_fetch_turns() -> None:
    # Regression: on every fetching-phase turn the meta-tool must remain
    # exposed so a model that escalates once can escalate again later.
    data = FakeDataDispatcher(manifest={})
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
    )
    for _ in range(3):
        tools = await disp.build("equity_research", has_web_search=False)
        assert "request_additional_tools" in [t.name for t in tools]


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
    names = [t.name for t in tools]
    assert "suggest_redirect" in names
    assert "read_payload" in names


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
    # — cap (MAX_TOOLS_PER_REQUEST) is enforced.
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
    # The truncated mapped slice keeps the alphabetical head.
    # With cap=48: header=2, budget=46; tools tool_000..tool_045 survive.
    assert "tool_000" in names
    # tools beyond budget are evicted.
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
    assert len(tools) == 4  # 2 mapped + request_additional_tools + read_payload


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
    async def test_dispatch_paths_emit_only_slim_summary_traces(self) -> None:
        """PR2.2 adds slim.summary from _pack_for_provider (called by build()).
        PR3.8 adds expand_tools.request and expand_tools.result from
        request_additional_tools dispatch. Requirement tool dispatch still
        emits no traces."""
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

        # Exercise build() — emits slim.summary + escalation_cache.summary
        await disp.build("dept_a", has_web_search=False)

        slim_calls_after_build = [c for c in calls if c[0] == "slim.summary"]
        assert len(slim_calls_after_build) == 1

        calls.clear()

        # Exercise dispatch() with a builtin (request_additional_tools)
        # — emits expand_tools.request and expand_tools.result (PR3.8)
        await disp.dispatch(
            department_id="dept_a",
            call=ToolCall(id="c1", name="request_additional_tools", arguments={"reason": "test"}),
        )

        expand_categories = {c[0] for c in calls}
        assert "expand_tools.request" in expand_categories
        assert "expand_tools.result" in expand_categories
        # No slim.summary or escalation_cache.summary from dispatch alone.
        assert "slim.summary" not in expand_categories
        assert "escalation_cache.summary" not in expand_categories

        calls.clear()

        # Exercise dispatch() with a requirement tool — only payload.stub trace emitted
        await disp.dispatch(
            department_id="dept_a",
            call=ToolCall(id="c2", name="tool_a", arguments={}),
        )

        req_categories = {c[0] for c in calls}
        assert req_categories == {"payload.stub"}
        # No slim/escalation traces from requirement dispatch.
        assert "slim.summary" not in req_categories
        assert "escalation_cache.summary" not in req_categories


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
        # emit order: header + mapped_sorted + expanded
        result = disp._pack_for_provider(mapped=[a, b], expanded=[c], header=[t1])
        assert result == [t1, a, b, c]

    def test_at_cap_no_truncation(self) -> None:
        disp = _make_dispatcher()
        header = [_make_schema(f"tail_{i}") for i in range(2)]
        budget = MAX_TOOLS_PER_REQUEST - len(header)
        # Use alphabetical names so sort is a no-op
        mapped = [_make_schema(f"m_{i:03d}") for i in range(budget // 2)]
        expanded = [_make_schema(f"e_{i}") for i in range(budget - len(mapped))]
        result = disp._pack_for_provider(mapped=mapped, expanded=expanded, header=header)
        # emit order: header + mapped_sorted + expanded
        assert result == header + sorted(mapped, key=lambda t: t.name) + expanded

    def test_over_cap_truncates_mapped_first(self) -> None:
        disp = _make_dispatcher()
        header = [_make_schema("t1"), _make_schema("t2")]
        expanded = [_make_schema("e1"), _make_schema("e2")]
        # mapped is large enough to push total over cap
        mapped = [_make_schema(f"m_{i}") for i in range(MAX_TOOLS_PER_REQUEST)]
        result = disp._pack_for_provider(mapped=mapped, expanded=expanded, header=header)
        assert len(result) == MAX_TOOLS_PER_REQUEST
        names = [t.name for t in result]
        # header preserved
        assert "t1" in names
        assert "t2" in names
        # expanded preserved
        assert "e1" in names
        assert "e2" in names

    def test_expanded_preserved_over_mapped(self) -> None:
        disp = _make_dispatcher()
        header = [_make_schema("t1")]
        expanded = [_make_schema(f"e_{i}") for i in range(10)]
        # mapped large enough to force truncation
        mapped = [_make_schema(f"m_{i}") for i in range(MAX_TOOLS_PER_REQUEST)]
        result = disp._pack_for_provider(mapped=mapped, expanded=expanded, header=header)
        names = [t.name for t in result]
        # all expanded items survive
        for i in range(10):
            assert f"e_{i}" in names

    def test_pathological_tail_exceeds_cap(self) -> None:
        disp = _make_dispatcher()
        header = [_make_schema(f"tail_{i}") for i in range(MAX_TOOLS_PER_REQUEST + 5)]
        mapped = [_make_schema("m1")]
        expanded = [_make_schema("e1")]
        result = disp._pack_for_provider(mapped=mapped, expanded=expanded, header=header)
        assert len(result) == MAX_TOOLS_PER_REQUEST
        # mapped and expanded are dropped; result is header slice
        names = [t.name for t in result]
        assert "m1" not in names
        assert "e1" not in names

    def test_empty_inputs(self) -> None:
        disp = _make_dispatcher()
        t1 = _make_schema("t1")
        result = disp._pack_for_provider(mapped=[], expanded=[], header=[t1])
        assert result == [t1]

    # ------------------------------------------------------------------
    # New tests: slim + sort + threshold + trace
    # ------------------------------------------------------------------

    def test_slim_applied_to_long_description(self) -> None:
        disp = _make_dispatcher()
        long_desc = "x" * 300
        fat = ToolSchema(name="fat_tool", description=long_desc, parameters={})
        result = disp._pack_for_provider(mapped=[fat], expanded=[], header=[])
        assert len(result) == 1
        assert len(result[0].description) <= TOOL_DESCRIPTION_MAX_CHARS

    def test_mapped_sorted_alphabetically(self) -> None:
        disp = _make_dispatcher()
        c, a, b = _make_schema("c"), _make_schema("a"), _make_schema("b")
        result = disp._pack_for_provider(mapped=[c, a, b], expanded=[], header=[])
        names = [t.name for t in result]
        assert names == ["a", "b", "c"]

    def test_expanded_preserves_addition_order(self) -> None:
        disp = _make_dispatcher()
        c, a, b = _make_schema("c"), _make_schema("a"), _make_schema("b")
        result = disp._pack_for_provider(mapped=[], expanded=[c, a, b], header=[])
        names = [t.name for t in result]
        assert names == ["c", "a", "b"]

    def test_header_preserved_in_receive_order(self) -> None:
        disp = _make_dispatcher()
        t2, t1 = _make_schema("t2"), _make_schema("t1")
        result = disp._pack_for_provider(mapped=[], expanded=[], header=[t2, t1])
        assert result[0].name == "t2"
        assert result[1].name == "t1"

    def test_trace_slim_summary_emitted(self) -> None:
        calls: list[tuple[str, str, dict[str, Any] | None]] = []

        def recorder(cat: str, msg: str, payload: dict[str, Any] | None) -> None:
            calls.append((cat, msg, payload))

        data = FakeDataDispatcher(manifest={})
        disp = ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(available=False, variant=None, adapter=None),
            trace=recorder,
        )
        disp._pack_for_provider(mapped=[_make_schema("a")], expanded=[], header=[_make_schema("h")])
        slim_events = [c for c in calls if c[0] == "slim.summary"]
        assert len(slim_events) == 1
        payload = slim_events[0][2]
        assert payload is not None
        assert "n_tools" in payload
        assert "n_failures" in payload
        assert "chars_before" in payload
        assert "chars_after" in payload
        assert "ratio" in payload

    def test_trace_shows_reduction_ratio(self) -> None:
        calls: list[tuple[str, str, dict[str, Any] | None]] = []

        def recorder(cat: str, msg: str, payload: dict[str, Any] | None) -> None:
            calls.append((cat, msg, payload))

        data = FakeDataDispatcher(manifest={})
        disp = ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(available=False, variant=None, adapter=None),
            trace=recorder,
        )
        # Build a fat tool: description of 300 chars — will be slimmed to <=200
        fat = ToolSchema(name="fat", description="w" * 300, parameters={})
        disp._pack_for_provider(mapped=[fat], expanded=[], header=[])
        slim_events = [c for c in calls if c[0] == "slim.summary"]
        payload = slim_events[0][2]
        assert payload is not None
        assert payload["ratio"] < 0.7

    def test_threshold_breach_raises(self) -> None:
        disp = _make_dispatcher()
        # 10 tools, slim fails on 6 => 6 >= 5 AND 6/10 = 60% > 20% => raise
        tools = [_make_schema(f"t{i}") for i in range(10)]
        fail_names = {t.name for t in tools[:6]}

        def fake_slim(t: ToolSchema) -> ToolSchema:
            if t.name in fail_names:
                raise ValueError("injected failure")
            return t

        with patch("openlia.llm.runtime.tools.slim_tool_schema", side_effect=fake_slim):
            with pytest.raises(SchemaSlimSystemicFailure):
                disp._pack_for_provider(mapped=tools, expanded=[], header=[])

    def test_threshold_not_breached_under_count(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 4 failures in 100 tools: count 4 < 5 → no raise
        import openlia.llm.runtime.tools as tools_mod

        monkeypatch.setattr(tools_mod, "MAX_TOOLS_PER_REQUEST", 200)
        disp = _make_dispatcher()
        tools = [_make_schema(f"t{i:03d}") for i in range(100)]
        fail_names = {t.name for t in tools[:4]}

        def fake_slim(t: ToolSchema) -> ToolSchema:
            if t.name in fail_names:
                raise ValueError("injected")
            return t

        with patch("openlia.llm.runtime.tools.slim_tool_schema", side_effect=fake_slim):
            result = disp._pack_for_provider(mapped=tools, expanded=[], header=[])
        assert len(result) == 100

    def test_threshold_not_breached_under_ratio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 5 failures in 50 tools: count 5 >= 5 but ratio 5/50 = 10% < 20% → no raise
        import openlia.llm.runtime.tools as tools_mod

        monkeypatch.setattr(tools_mod, "MAX_TOOLS_PER_REQUEST", 100)
        disp = _make_dispatcher()
        tools = [_make_schema(f"t{i:03d}") for i in range(50)]
        fail_names = {t.name for t in tools[:5]}

        def fake_slim(t: ToolSchema) -> ToolSchema:
            if t.name in fail_names:
                raise ValueError("injected")
            return t

        with patch("openlia.llm.runtime.tools.slim_tool_schema", side_effect=fake_slim):
            result = disp._pack_for_provider(mapped=tools, expanded=[], header=[])
        assert len(result) == 50

    def test_failed_tool_passes_through_unslimmed(self) -> None:
        disp = _make_dispatcher()
        original = ToolSchema(name="broken", description="original desc", parameters={})

        def fake_slim(t: ToolSchema) -> ToolSchema:
            raise ValueError("always fails")

        with patch("openlia.llm.runtime.tools.slim_tool_schema", side_effect=fake_slim):
            # Only 1 failure — won't breach threshold (count < 5)
            result = disp._pack_for_provider(mapped=[original], expanded=[], header=[])
        assert len(result) == 1
        assert result[0].description == "original desc"


# ---------------------------------------------------------------------------
# Touch-on-dispatch + LRU-eviction tests (PR3.5)
# ---------------------------------------------------------------------------


async def test_touch_on_successful_dispatch() -> None:
    """After a successful dispatch, the tool is moved to MRU in lru_order."""
    data = FakeDataDispatcher(
        manifest={},
        results={"tool_a": {"data": 1}, "tool_b": {"data": 2}},
    )
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(available=False, variant=None, adapter=None),
    )
    # Seed the escalation cache directly so touch() has something to work with.
    disp._escalation_cache.add("dept_x", [_make_schema("tool_a"), _make_schema("tool_b")])
    # Initially lru_order is addition order: tool_a first, tool_b last (MRU).
    assert disp._escalation_cache.lru_order("dept_x") == ["tool_a", "tool_b"]

    # Dispatch tool_a successfully — it should become MRU.
    result = await disp.dispatch(
        department_id="dept_x",
        call=ToolCall(id="c1", name="tool_a", arguments={}),
    )
    assert result.ok is True
    assert disp._escalation_cache.lru_order("dept_x") == ["tool_b", "tool_a"]


async def test_no_touch_on_failed_dispatch() -> None:
    """A failed dispatch must not touch the escalation cache."""
    data = FakeDataDispatcher(manifest={}, raise_for={"tool_a"})
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(available=False, variant=None, adapter=None),
    )
    disp._escalation_cache.add("dept_x", [_make_schema("tool_a"), _make_schema("tool_b")])
    original_order = disp._escalation_cache.lru_order("dept_x")

    result = await disp.dispatch(
        department_id="dept_x",
        call=ToolCall(id="c1", name="tool_a", arguments={}),
    )
    assert result.ok is False
    # LRU order unchanged — no touch on failure.
    assert disp._escalation_cache.lru_order("dept_x") == original_order


async def test_pack_evicts_by_lru_under_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """When expanded > budget, the LRU-oldest are dropped and MRU are kept."""
    import openlia.llm.runtime.tools as tools_mod

    monkeypatch.setattr(tools_mod, "MAX_TOOLS_PER_REQUEST", 10)

    data = FakeDataDispatcher(manifest={})
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(available=False, variant=None, adapter=None),
    )
    dept = "dept_lru"
    # Add 50 tools in order t_00 … t_49.
    all_schemas = [_make_schema(f"t_{i:02d}") for i in range(50)]
    disp._escalation_cache.add(dept, all_schemas)

    # Touch tools t_25 through t_49 (in order), so t_49 becomes MRU.
    for i in range(25, 50):
        disp._escalation_cache.touch(dept, f"t_{i:02d}")

    # header = 1 meta tool; budget = 10 - 1 = 9; expanded = 50; evict 41.
    # LRU-oldest 41 are t_00..t_24 (never touched) and t_25..t_40 (touched early).
    # Surviving 9 should be t_41..t_49 (most recently touched).
    header = [_make_schema("meta")]
    expanded = disp._escalation_cache.for_emission(dept)
    result = disp._pack_for_provider(
        mapped=[], expanded=expanded, header=header, department_id=dept
    )
    assert len(result) == 10
    names = [t.name for t in result]
    assert "meta" in names
    for i in range(41, 50):
        assert f"t_{i:02d}" in names, f"t_{i:02d} should survive eviction"
    for i in range(41):
        assert f"t_{i:02d}" not in names, f"t_{i:02d} should be evicted"


async def test_pack_preserves_emission_order_after_lru_evict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After LRU eviction, surviving tools appear in addition order, not LRU order."""
    import openlia.llm.runtime.tools as tools_mod

    monkeypatch.setattr(tools_mod, "MAX_TOOLS_PER_REQUEST", 5)

    data = FakeDataDispatcher(manifest={})
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(available=False, variant=None, adapter=None),
    )
    dept = "dept_order"
    # Add tools in alphabetical order that is NOT LRU order: alpha, beta, gamma, delta, epsilon.
    schemas = [
        _make_schema("alpha"),
        _make_schema("beta"),
        _make_schema("gamma"),
        _make_schema("delta"),
        _make_schema("epsilon"),
    ]
    disp._escalation_cache.add(dept, schemas)

    # Touch to create non-trivial LRU: touch alpha last (MRU), beta second.
    # LRU order (LRU first): gamma, delta, epsilon, beta, alpha.
    disp._escalation_cache.touch(dept, "beta")
    disp._escalation_cache.touch(dept, "alpha")

    # header = 1; budget = 4; expanded = 5; evict 1 (LRU = gamma).
    header = [_make_schema("hdr")]
    expanded = disp._escalation_cache.for_emission(dept)
    result = disp._pack_for_provider(
        mapped=[], expanded=expanded, header=header, department_id=dept
    )
    assert len(result) == 5
    names = [t.name for t in result]
    # gamma evicted (LRU-oldest).
    assert "gamma" not in names
    # Remaining 4 in addition order: alpha, beta, delta, epsilon.
    data_tools = [t.name for t in result if t.name != "hdr"]
    assert data_tools == ["alpha", "beta", "delta", "epsilon"]


# ---------------------------------------------------------------------------
# Task A: MAX_TOOLS_PER_REQUEST env override tests (PR3.6)
# ---------------------------------------------------------------------------


@pytest.mark.filterwarnings("ignore::pytest.PytestWarning")
class TestMaxToolsEnvOverride:
    pytestmark: ClassVar[list] = []  # sync tests; override module-level asyncio marker

    def test_max_tools_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No env var set — function returns default 48."""
        from openlia.llm.runtime.tools import _get_max_tools_per_request

        monkeypatch.delenv("OPENLIA_MAX_TOOLS_PER_REQUEST", raising=False)
        assert _get_max_tools_per_request() == 48

    def test_max_tools_env_override_valid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Valid env var overrides the default."""
        from openlia.llm.runtime.tools import _get_max_tools_per_request

        monkeypatch.setenv("OPENLIA_MAX_TOOLS_PER_REQUEST", "64")
        assert _get_max_tools_per_request() == 64

    def test_max_tools_env_override_invalid_falls_back(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Non-integer value falls back to 48 and logs a warning."""
        import logging

        from openlia.llm.runtime.tools import _get_max_tools_per_request

        monkeypatch.setenv("OPENLIA_MAX_TOOLS_PER_REQUEST", "not_an_integer")
        with caplog.at_level(logging.WARNING, logger="openlia.llm.runtime.tools"):
            result = _get_max_tools_per_request()
        assert result == 48
        assert any("not_an_integer" in r.message for r in caplog.records)

    def test_max_tools_env_override_zero_falls_back(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Zero (< 1) falls back to 48 and logs a warning."""
        import logging

        from openlia.llm.runtime.tools import _get_max_tools_per_request

        monkeypatch.setenv("OPENLIA_MAX_TOOLS_PER_REQUEST", "0")
        with caplog.at_level(logging.WARNING, logger="openlia.llm.runtime.tools"):
            result = _get_max_tools_per_request()
        assert result == 48
        assert any("0" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Task B: Re-escalation loop guard tests (PR3.7)
# ---------------------------------------------------------------------------


async def test_escalation_loop_guard_fires_at_threshold() -> None:
    """After 3 consecutive empty escalations, payload contains a directive."""
    data = FakeDataDispatcher(manifest=_MANIFEST)
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
    )
    for i in range(2):
        r = await disp.dispatch(
            department_id="equity_research",
            call=ToolCall(
                id=f"c{i}",
                name="request_additional_tools",
                arguments={"reason": "obscure thing nothing matches"},
            ),
        )
        assert r.ok is False
        assert "directive" not in r.payload

    # Third call fires the directive.
    r3 = await disp.dispatch(
        department_id="equity_research",
        call=ToolCall(
            id="c3",
            name="request_additional_tools",
            arguments={"reason": "obscure thing nothing matches"},
        ),
    )
    assert r3.ok is False
    assert "directive" in r3.payload
    directive_text = r3.payload["directive"].lower()
    assert "consecutive" in directive_text


async def test_escalation_loop_guard_counter_resets_on_success() -> None:
    """Counter resets after a successful escalation; directive not fired until threshold again."""
    new_tool = {
        "name": "options_chain",
        "description": "Options chain",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }
    data = FakeDataDispatcher(
        manifest=_MANIFEST,
        results={"expand::success call": new_tool},
    )
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
    )
    dept = "equity_research"

    # Two failures.
    for i in range(2):
        await disp.dispatch(
            department_id=dept,
            call=ToolCall(
                id=f"fail{i}",
                name="request_additional_tools",
                arguments={"reason": "nothing matches"},
            ),
        )

    # Success resets counter.
    r_success = await disp.dispatch(
        department_id=dept,
        call=ToolCall(
            id="success",
            name="request_additional_tools",
            arguments={"reason": "success call"},
        ),
    )
    assert r_success.ok is True
    assert disp._consecutive_escalation_failures.get(dept, 0) == 0

    # Two more failures after reset — counter at 2, directive NOT fired.
    for i in range(2):
        r = await disp.dispatch(
            department_id=dept,
            call=ToolCall(
                id=f"post{i}",
                name="request_additional_tools",
                arguments={"reason": "nothing matches again"},
            ),
        )
        assert "directive" not in r.payload

    assert disp._consecutive_escalation_failures.get(dept, 0) == 2


async def test_escalation_loop_guard_directive_trace_emitted() -> None:
    """expand_tools.directive_fired trace is emitted when threshold is hit."""
    trace_calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def recorder(cat: str, msg: str, payload: dict[str, Any] | None) -> None:
        trace_calls.append((cat, msg, payload))

    data = FakeDataDispatcher(manifest=_MANIFEST)
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
        trace=recorder,
    )
    for i in range(3):
        await disp.dispatch(
            department_id="equity_research",
            call=ToolCall(
                id=f"c{i}",
                name="request_additional_tools",
                arguments={"reason": "nothing matches"},
            ),
        )

    directive_traces = [c for c in trace_calls if c[0] == "expand_tools.directive_fired"]
    assert len(directive_traces) == 1
    payload = directive_traces[0][2]
    assert payload is not None
    assert payload["consecutive_failures"] == 3
    assert payload["department_id"] == "equity_research"


# ---------------------------------------------------------------------------
# Task C: Four new traces tests (PR3.8)
# ---------------------------------------------------------------------------


async def test_expand_tools_request_trace_emitted() -> None:
    """expand_tools.request trace has correct reason, category_hint, already_loaded."""
    trace_calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def recorder(cat: str, msg: str, payload: dict[str, Any] | None) -> None:
        trace_calls.append((cat, msg, payload))

    data = FakeDataDispatcher(manifest=_MANIFEST)
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
        trace=recorder,
    )
    await disp.dispatch(
        department_id="equity_research",
        call=ToolCall(
            id="c1",
            name="request_additional_tools",
            arguments={"reason": "need options data", "category_hint": "financial"},
        ),
    )

    req_traces = [c for c in trace_calls if c[0] == "expand_tools.request"]
    assert len(req_traces) == 1
    p = req_traces[0][2]
    assert p is not None
    assert p["reason"] == "need options data"
    assert p["category_hint"] == "financial"
    assert p["already_loaded"] == 0


async def test_expand_tools_result_trace_emitted() -> None:
    """expand_tools.result trace has matched_count, added_count, top_names, failure_reason."""
    new_tool = {
        "name": "options_chain",
        "description": "Options chain",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }
    trace_calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def recorder(cat: str, msg: str, payload: dict[str, Any] | None) -> None:
        trace_calls.append((cat, msg, payload))

    data = FakeDataDispatcher(
        manifest=_MANIFEST,
        results={"expand::need options": new_tool},
    )
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
        trace=recorder,
    )
    await disp.dispatch(
        department_id="equity_research",
        call=ToolCall(
            id="c1",
            name="request_additional_tools",
            arguments={"reason": "need options"},
        ),
    )

    result_traces = [c for c in trace_calls if c[0] == "expand_tools.result"]
    assert len(result_traces) == 1
    p = result_traces[0][2]
    assert p is not None
    assert p["matched_count"] == 1
    assert p["added_count"] == 1
    assert p["top_names"] == ["options_chain"]
    assert p["failure_reason"] is None


async def test_expand_tools_result_failure_reason_no_match() -> None:
    """failure_reason == 'no_match' when data dispatcher returns empty list."""
    trace_calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def recorder(cat: str, msg: str, payload: dict[str, Any] | None) -> None:
        trace_calls.append((cat, msg, payload))

    data = FakeDataDispatcher(manifest=_MANIFEST)
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
        trace=recorder,
    )
    await disp.dispatch(
        department_id="equity_research",
        call=ToolCall(
            id="c1",
            name="request_additional_tools",
            arguments={"reason": "obscure thing"},
        ),
    )

    result_traces = [c for c in trace_calls if c[0] == "expand_tools.result"]
    assert len(result_traces) == 1
    p = result_traces[0][2]
    assert p is not None
    assert p["failure_reason"] == "no_match"
    assert p["matched_count"] == 0


async def test_expand_tools_result_failure_reason_all_already_loaded() -> None:
    """failure_reason == 'all_already_loaded' when entries returned but all already in cache."""
    new_tool = {
        "name": "options_chain",
        "description": "Options chain",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }
    trace_calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def recorder(cat: str, msg: str, payload: dict[str, Any] | None) -> None:
        trace_calls.append((cat, msg, payload))

    data = FakeDataDispatcher(
        manifest=_MANIFEST,
        results={
            "expand::first": new_tool,
            "expand::second": new_tool,
        },
    )
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
        trace=recorder,
    )
    # First call — adds tool successfully.
    await disp.dispatch(
        department_id="equity_research",
        call=ToolCall(id="c1", name="request_additional_tools", arguments={"reason": "first"}),
    )
    trace_calls.clear()

    # Second call — tool already in cache.
    await disp.dispatch(
        department_id="equity_research",
        call=ToolCall(id="c2", name="request_additional_tools", arguments={"reason": "second"}),
    )
    result_traces = [c for c in trace_calls if c[0] == "expand_tools.result"]
    assert len(result_traces) == 1
    p = result_traces[0][2]
    assert p is not None
    assert p["failure_reason"] == "all_already_loaded"
    assert p["matched_count"] == 1
    assert p["added_count"] == 0


@pytest.mark.filterwarnings("ignore::pytest.PytestWarning")
class TestEscalationCacheTraces:
    pytestmark: ClassVar[list] = []  # sync tests

    _TraceList = list[tuple[str, str, dict[str, Any] | None]]

    def _make_traced_dispatcher(self) -> tuple[ToolDispatcher, _TraceList]:
        trace_calls: list[tuple[str, str, dict[str, Any] | None]] = []

        def recorder(cat: str, msg: str, payload: dict[str, Any] | None) -> None:
            trace_calls.append((cat, msg, payload))

        data = FakeDataDispatcher(manifest={})
        disp = ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(available=False, variant=None, adapter=None),
            trace=recorder,
        )
        return disp, trace_calls

    def test_escalation_cache_summary_trace(self) -> None:
        """escalation_cache.summary emitted from _pack_for_provider with correct counts."""
        disp, calls = self._make_traced_dispatcher()
        mapped = [_make_schema("m1"), _make_schema("m2")]
        expanded = [_make_schema("e1")]
        header = [_make_schema("h1")]
        disp._pack_for_provider(mapped=mapped, expanded=expanded, header=header)
        summary_traces = [c for c in calls if c[0] == "escalation_cache.summary"]
        assert len(summary_traces) == 1
        p = summary_traces[0][2]
        assert p is not None
        assert p["builtins"] == 1
        assert p["expanded"] == 1
        assert p["emitted"] == 4  # h1 + m1 + m2 + e1
        assert p["evicted"] == 0

    def test_escalation_cache_evict_trace_only_when_eviction_fires(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No evict trace when under budget; evict trace with evicted_names when over budget."""
        import openlia.llm.runtime.tools as tools_mod

        monkeypatch.setattr(tools_mod, "MAX_TOOLS_PER_REQUEST", 4)

        disp, calls = self._make_traced_dispatcher()
        header = [_make_schema("h1")]
        mapped = [_make_schema("m1")]
        expanded = [_make_schema("e1")]

        # Under budget: h1 + m1 + e1 = 3 < 4.
        disp._pack_for_provider(mapped=mapped, expanded=expanded, header=header)
        evict_traces = [c for c in calls if c[0] == "escalation_cache.evict"]
        assert len(evict_traces) == 0

        calls.clear()

        # Over budget: h1 + m1 + m2 + m3 + e1 = 5 > 4; evict 1 from mapped.
        disp._pack_for_provider(
            mapped=[_make_schema("m1"), _make_schema("m2"), _make_schema("m3")],
            expanded=[_make_schema("e1")],
            header=[_make_schema("h1")],
        )
        evict_traces = [c for c in calls if c[0] == "escalation_cache.evict"]
        assert len(evict_traces) == 1
        p = evict_traces[0][2]
        assert p is not None
        assert "evicted_names" in p
        assert len(p["evicted_names"]) == 1
        assert p["cap"] == 4


# ---------------------------------------------------------------------------
# PR4.3: PayloadStore + stubification tests
# ---------------------------------------------------------------------------


def _make_large_payload(n_rows: int = 200) -> dict[str, Any]:
    """Tabular payload large enough to exceed default stub threshold (8000 chars)."""
    rows = [
        {
            "date": f"2024-{(i % 12) + 1:02d}-01",
            "revenue": 1000000 + i * 12345,
            "expenses": 900000 + i * 9876,
            "ebitda": 100000 + i * 2469,
            "description": f"Quarter {i} results with some extra text to pad the payload size",
        }
        for i in range(n_rows)
    ]
    return {"rows": rows, "ticker": "AAPL", "period": "annual"}


def _make_small_payload() -> dict[str, Any]:
    return {"symbol": "AAPL", "price": 190.5, "volume": 1000000}


_TraceList = list[tuple[str, str, dict[str, Any] | None]]


def _make_dispatcher_traced() -> tuple[ToolDispatcher, _TraceList]:
    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def recorder(cat: str, msg: str, payload: dict[str, Any] | None) -> None:
        calls.append((cat, msg, payload))

    data = FakeDataDispatcher(manifest=_MANIFEST)
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(available=False, variant=None, adapter=None),
        trace=recorder,
    )
    return disp, calls


@pytest.mark.filterwarnings("ignore::pytest.PytestWarning")
class TestPayloadStore:
    pytestmark: ClassVar[list] = [pytest.mark.asyncio]

    async def test_dispatch_under_threshold_returns_raw(self) -> None:
        """Small payload returned raw; payload.stub trace fired with stubbed=False."""
        small = _make_small_payload()
        data = FakeDataDispatcher(manifest=_MANIFEST, results={"stock_quote": small})
        disp, calls = _make_dispatcher_traced()
        disp._data = data

        result = await disp.dispatch(
            department_id="equity_research",
            call=ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"}),
        )

        assert result.ok is True
        # Raw payload returned (no stub fields).
        assert result.payload.get("symbol") == "AAPL"
        assert "ref" not in result.payload

        stub_traces = [c for c in calls if c[0] == "payload.stub"]
        assert len(stub_traces) == 1
        p = stub_traces[0][2]
        assert p is not None
        assert p["stubbed"] is False
        assert p["tool"] == "stock_quote"

    async def test_dispatch_over_threshold_stubifies(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Large payload stubified; full payload stored; payload.stub trace stubbed=True."""
        import openlia.llm.runtime.tools as tools_mod

        monkeypatch.setattr(tools_mod, "PAYLOAD_STUB_THRESHOLD_CHARS", 100)

        large = _make_large_payload()
        data = FakeDataDispatcher(manifest=_MANIFEST, results={"stock_quote": large})
        calls: list[tuple[str, str, dict[str, Any] | None]] = []

        def recorder(cat: str, msg: str, p: dict[str, Any] | None) -> None:
            calls.append((cat, msg, p))

        disp = ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(available=False, variant=None, adapter=None),
            trace=recorder,
        )

        result = await disp.dispatch(
            department_id="equity_research",
            call=ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"}),
        )

        assert result.ok is True
        # Stub returned: has ref field.
        assert "ref" in result.payload
        ref = result.payload["ref"]
        # Full payload stored.
        assert ref in disp._payload_store

        stub_traces = [c for c in calls if c[0] == "payload.stub"]
        assert len(stub_traces) == 1
        p = stub_traces[0][2]
        assert p is not None
        assert p["stubbed"] is True
        assert p["shape"] is not None

    async def test_stub_ref_format(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Refs follow pattern r_<4hex>_<seq>."""
        import re

        import openlia.llm.runtime.tools as tools_mod

        monkeypatch.setattr(tools_mod, "PAYLOAD_STUB_THRESHOLD_CHARS", 100)

        large = _make_large_payload()
        data = FakeDataDispatcher(manifest=_MANIFEST, results={"stock_quote": large})
        disp = ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(available=False, variant=None, adapter=None),
        )

        result = await disp.dispatch(
            department_id="equity_research",
            call=ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"}),
        )

        ref = result.payload["ref"]
        assert re.fullmatch(r"r_[0-9a-f]{4}_\d+", ref), f"Unexpected ref format: {ref!r}"

    async def test_per_run_scope(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Each dispatcher instance has its own store, independent of others."""
        import openlia.llm.runtime.tools as tools_mod

        monkeypatch.setattr(tools_mod, "PAYLOAD_STUB_THRESHOLD_CHARS", 100)

        large = _make_large_payload()
        data = FakeDataDispatcher(manifest=_MANIFEST, results={"stock_quote": large})

        disp1 = ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(available=False, variant=None, adapter=None),
        )
        disp2 = ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(available=False, variant=None, adapter=None),
        )

        r1 = await disp1.dispatch(
            department_id="equity_research",
            call=ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"}),
        )
        r2 = await disp2.dispatch(
            department_id="equity_research",
            call=ToolCall(id="c2", name="stock_quote", arguments={"symbol": "MSFT"}),
        )

        ref1 = r1.payload["ref"]
        ref2 = r2.payload["ref"]

        # Each dispatcher has its own store.
        assert ref1 in disp1._payload_store
        assert ref1 not in disp2._payload_store
        assert ref2 in disp2._payload_store
        assert ref2 not in disp1._payload_store


# ---------------------------------------------------------------------------
# PR4.4: read_payload tool tests
# ---------------------------------------------------------------------------


@pytest.mark.filterwarnings("ignore::pytest.PytestWarning")
class TestReadPayload:
    pytestmark: ClassVar[list] = [pytest.mark.asyncio]

    def _make_disp_with_store(
        self,
        stored: dict[str, Any],
        ref: str = "r_abcd_01",
    ) -> tuple[ToolDispatcher, list[tuple[str, str, dict[str, Any] | None]]]:
        calls: list[tuple[str, str, dict[str, Any] | None]] = []

        def recorder(cat: str, msg: str, p: dict[str, Any] | None) -> None:
            calls.append((cat, msg, p))

        data = FakeDataDispatcher(manifest=_MANIFEST)
        disp = ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(available=False, variant=None, adapter=None),
            trace=recorder,
        )
        disp._payload_store[ref] = stored
        return disp, calls

    async def test_read_payload_returns_full(self) -> None:
        """read_payload with no path returns the full stored payload."""
        stored = {"ticker": "AAPL", "price": 190.5, "volume": 1000}
        disp, _ = self._make_disp_with_store(stored)

        result = await disp.dispatch(
            department_id="equity_research",
            call=ToolCall(
                id="c1",
                name="read_payload",
                arguments={"ref": "r_abcd_01"},
            ),
        )

        assert result.ok is True
        assert result.payload == stored

    async def test_read_payload_with_path(self) -> None:
        """read_payload with a path returns a slice."""
        stored = {"ticker": "AAPL", "price": 190.5}
        disp, _ = self._make_disp_with_store(stored)

        result = await disp.dispatch(
            department_id="equity_research",
            call=ToolCall(
                id="c1",
                name="read_payload",
                arguments={"ref": "r_abcd_01", "path": "ticker"},
            ),
        )

        assert result.ok is True
        # Primitive result wrapped in {"value": ...}
        assert result.payload == {"value": "AAPL"}

    async def test_read_payload_unknown_ref_returns_error(self) -> None:
        """Unknown ref returns ok=False with descriptive error."""
        data = FakeDataDispatcher(manifest=_MANIFEST)
        disp = ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(available=False, variant=None, adapter=None),
        )

        result = await disp.dispatch(
            department_id="equity_research",
            call=ToolCall(
                id="c1",
                name="read_payload",
                arguments={"ref": "r_dead_99"},
            ),
        )

        assert result.ok is False
        assert "Unknown ref" in result.payload["error"]

    async def test_read_payload_parse_error(self) -> None:
        """Invalid path syntax returns ok=False with syntax error message."""
        stored = {"ticker": "AAPL"}
        disp, _ = self._make_disp_with_store(stored)

        result = await disp.dispatch(
            department_id="equity_research",
            call=ToolCall(
                id="c1",
                name="read_payload",
                arguments={"ref": "r_abcd_01", "path": ".invalid"},
            ),
        )

        assert result.ok is False
        assert "Invalid path syntax" in result.payload["error"]

    async def test_read_payload_resolve_error(self) -> None:
        """Valid syntax, path doesn't apply returns ok=False."""
        stored = {"ticker": "AAPL"}
        disp, _ = self._make_disp_with_store(stored)

        result = await disp.dispatch(
            department_id="equity_research",
            call=ToolCall(
                id="c1",
                name="read_payload",
                arguments={"ref": "r_abcd_01", "path": "rows[0]"},
            ),
        )

        assert result.ok is False
        assert "error" in result.payload

    async def test_read_payload_sub_stub_on_oversized(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Result larger than READ_PAYLOAD_CAP_CHARS returns a sub-stub."""
        import openlia.llm.runtime.tools as tools_mod

        monkeypatch.setattr(tools_mod, "READ_PAYLOAD_CAP_CHARS", 100)

        # Large stored payload
        stored = {f"key_{i}": "x" * 50 for i in range(100)}
        disp, _ = self._make_disp_with_store(stored)

        result = await disp.dispatch(
            department_id="equity_research",
            call=ToolCall(
                id="c1",
                name="read_payload",
                arguments={"ref": "r_abcd_01"},
            ),
        )

        assert result.ok is True
        # Sub-stub has ref, truncated, hint fields.
        assert result.payload.get("truncated") is True
        assert "hint" in result.payload
        assert result.payload.get("ref") == "r_abcd_01"

    async def test_read_payload_traces(self) -> None:
        """read_payload.call and read_payload.result traces fired."""
        stored = {"ticker": "AAPL", "price": 190.5}
        disp, calls = self._make_disp_with_store(stored)

        await disp.dispatch(
            department_id="equity_research",
            call=ToolCall(
                id="c1",
                name="read_payload",
                arguments={"ref": "r_abcd_01", "path": "ticker"},
            ),
        )

        categories = [c[0] for c in calls]
        assert "read_payload.call" in categories
        assert "read_payload.result" in categories

        call_trace = next(c for c in calls if c[0] == "read_payload.call")
        assert call_trace[2] is not None
        assert call_trace[2]["ref"] == "r_abcd_01"
        assert call_trace[2]["path"] == "ticker"

        result_trace = next(c for c in calls if c[0] == "read_payload.result")
        assert result_trace[2] is not None
        assert result_trace[2]["outcome"] == "ok"
        assert result_trace[2]["ref"] == "r_abcd_01"

    def test_read_payload_registered_in_builtin_handlers(self) -> None:
        """_READ_PAYLOAD_NAME is in the handler table."""
        data = FakeDataDispatcher(manifest=_MANIFEST)
        disp = ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(available=False, variant=None, adapter=None),
        )
        assert _READ_PAYLOAD_NAME in disp._builtin_handlers

    async def test_read_payload_in_build_output(self) -> None:
        """build() always includes the read_payload schema."""
        data = FakeDataDispatcher(manifest=_MANIFEST)
        disp = ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(available=False, variant=None, adapter=None),
        )
        tools = await disp.build("equity_research", has_web_search=False)
        names = [t.name for t in tools]
        assert "read_payload" in names
