"""Tests for the runtime_dispatch helper.

Covers `ToolCallResult` envelope shaping, `dispatch_with_envelope`'s
success / error / non-dict payload / truncation paths, and `dispatch_many`'s
order-preservation, mixed-outcome handling, and actual parallelism.

Pin the truncation rule against the legacy `_normalize_payload` from
`openlia.llm.runtime.tools` so consumer behavior is identical post-migration.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from openlia.connectors.dispatch import Dispatcher, PreparedConnector
from openlia.connectors.types import ToolDefinition
from openlia.llm.runtime.tools import _normalize_payload as _legacy_normalize
from openlia_server.services.runtime_dispatch import (
    ToolCallRequest,
    ToolCallResult,
    _normalize_payload,
    _summary_for,
    dispatch_many,
    dispatch_with_envelope,
)


def _td(name: str) -> ToolDefinition:
    return ToolDefinition(name=name, description=f"desc-{name}", input_schema={"type": "object"})


class _FakeTransport:
    def __init__(
        self,
        *,
        result: Any | None = None,
        results: dict[str, Any] | None = None,
        raise_exc: Exception | None = None,
        gate: asyncio.Event | None = None,
    ) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._result = result
        self._results = results
        self._raise = raise_exc
        self._gate = gate

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, arguments))
        if self._gate is not None:
            await self._gate.wait()
        if self._raise is not None:
            raise self._raise
        if self._results is not None:
            return self._results[name]
        return self._result


def _make_dispatcher(
    *,
    tool_to_result: dict[str, Any] | None = None,
    raise_exc: Exception | None = None,
    transport: _FakeTransport | None = None,
) -> tuple[Dispatcher, _FakeTransport]:
    if transport is None:
        transport = _FakeTransport(results=tool_to_result, raise_exc=raise_exc)
    tools = {name: _td(name) for name in (tool_to_result or {}).keys()}
    if not tools:
        tools = {"any_tool": _td("any_tool")}
    d = Dispatcher(
        connectors={
            "c1": PreparedConnector(
                connector_id="c1",
                provider_id="prov",
                transport=transport,
                tools=tools,
            ),
        },
        allowlist={},
    )
    return d, transport


# ---------------------------------------------------------------------------
# dispatch_with_envelope
# ---------------------------------------------------------------------------


async def test_dispatch_with_envelope_happy_path():
    d, _ = _make_dispatcher(tool_to_result={"get_quote": {"symbol": "AAPL", "price": 1.0}})
    res = await dispatch_with_envelope(
        d,
        prefixed_name="prov__get_quote",
        arguments={"symbol": "AAPL"},
        call_id="cid-1",
    )
    assert isinstance(res, ToolCallResult)
    assert res.ok is True
    assert res.call_id == "cid-1"
    assert "prov__get_quote" in res.summary
    assert res.payload == {"symbol": "AAPL", "price": 1.0}
    assert res.structured is None


async def test_dispatch_with_envelope_error_path():
    d, _ = _make_dispatcher(raise_exc=RuntimeError("boom"))
    res = await dispatch_with_envelope(
        d,
        prefixed_name="prov__any_tool",
        arguments={"symbol": "AAPL"},
        call_id="cid-err",
    )
    assert res.ok is False
    assert res.call_id == "cid-err"
    assert "boom" in res.summary
    assert "prov__any_tool" in res.summary
    assert res.payload == {"error": "boom"}


@pytest.mark.parametrize(
    "raw, expected",
    [
        (["a", "b", "c"], {"value": ["a", "b", "c"]}),
        ("hello", {"value": "hello"}),
        (42, {"value": 42}),
    ],
)
async def test_dispatch_with_envelope_non_dict_payload(raw: Any, expected: dict[str, Any]):
    d, _ = _make_dispatcher(tool_to_result={"any_tool": raw})
    res = await dispatch_with_envelope(
        d,
        prefixed_name="prov__any_tool",
        arguments={},
        call_id="cid-nd",
    )
    assert res.ok is True
    assert res.payload == expected


async def test_dispatch_with_envelope_truncates_long_lists():
    long_list = list(range(120))
    d, _ = _make_dispatcher(tool_to_result={"any_tool": {"items": long_list, "n": 120}})
    res = await dispatch_with_envelope(
        d,
        prefixed_name="prov__any_tool",
        arguments={},
        call_id="cid-trunc",
    )
    assert res.ok is True
    assert len(res.payload["items"]) == 50
    assert res.payload["truncated"] is True
    assert res.payload["n"] == 120


async def test_dispatch_with_envelope_drops_null_values():
    d, _ = _make_dispatcher(tool_to_result={"any_tool": {"a": 1, "b": None, "c": 2}})
    res = await dispatch_with_envelope(
        d,
        prefixed_name="prov__any_tool",
        arguments={},
        call_id="cid-null",
    )
    assert res.ok is True
    assert res.payload == {"a": 1, "c": 2}


async def test_dispatch_with_envelope_summary_uses_subject_keys():
    d, _ = _make_dispatcher(tool_to_result={"any_tool": {"x": 1}})
    res = await dispatch_with_envelope(
        d,
        prefixed_name="prov__any_tool",
        arguments={"symbol": "AAPL"},
        call_id="c",
    )
    assert "AAPL" in res.summary


# ---------------------------------------------------------------------------
# Pin: helper output matches legacy ToolDispatcher behavior on identical input
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        {"a": 1, "b": None, "c": [1, 2, 3]},
        {"items": list(range(120))},
        {"deep": {"x": None}},  # nested nulls preserved (legacy did not recurse)
        ["plain", "list"],
        "scalar",
        7,
    ],
)
def test_normalize_payload_matches_legacy(raw: Any):
    assert _normalize_payload(raw) == _legacy_normalize(raw)


def test_summary_for_matches_legacy_subject_format():
    # The legacy ToolDispatcher formatted successful requirement summaries as
    # `Fetched <name> for <subject>` when `symbol|ticker|query|name` was in the
    # arguments. Pin both branches.
    assert _summary_for("prov__t", {"symbol": "AAPL"}) == "Fetched prov__t for AAPL"
    assert _summary_for("prov__t", {}) == "Fetched prov__t"


# ---------------------------------------------------------------------------
# dispatch_many
# ---------------------------------------------------------------------------


async def test_dispatch_many_happy_path_preserves_order():
    d, _ = _make_dispatcher(
        tool_to_result={
            "a": {"v": "A"},
            "b": {"v": "B"},
            "c": {"v": "C"},
        }
    )
    calls = [
        ToolCallRequest(prefixed_name="prov__a", arguments={}, call_id="1"),
        ToolCallRequest(prefixed_name="prov__b", arguments={}, call_id="2"),
        ToolCallRequest(prefixed_name="prov__c", arguments={}, call_id="3"),
    ]
    results = await dispatch_many(d, calls)
    assert [r.call_id for r in results] == ["1", "2", "3"]
    assert all(r.ok for r in results)
    assert [r.payload["v"] for r in results] == ["A", "B", "C"]


async def test_dispatch_many_mixed_success_and_failure():
    class _MixedTransport:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, Any]]] = []

        async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
            self.calls.append((name, arguments))
            if name == "bad":
                raise RuntimeError("kaboom")
            return {"name": name}

    transport = _MixedTransport()
    d = Dispatcher(
        connectors={
            "c1": PreparedConnector(
                connector_id="c1",
                provider_id="prov",
                transport=transport,
                tools={"good": _td("good"), "bad": _td("bad")},
            ),
        },
        allowlist={},
    )
    calls = [
        ToolCallRequest(prefixed_name="prov__good", arguments={}, call_id="1"),
        ToolCallRequest(prefixed_name="prov__bad", arguments={}, call_id="2"),
        ToolCallRequest(prefixed_name="prov__good", arguments={"symbol": "X"}, call_id="3"),
    ]
    results = await dispatch_many(d, calls)
    assert [r.ok for r in results] == [True, False, True]
    assert [r.call_id for r in results] == ["1", "2", "3"]
    assert "kaboom" in results[1].summary
    assert results[2].payload == {"name": "good"}


async def test_dispatch_many_runs_in_parallel():
    """Both calls must wait on a shared gate; if dispatch_many serialized,
    the second call would never start before the first completes, so neither
    side could observe both `started` flags before releasing the gate."""

    started = asyncio.Event()
    second_started = asyncio.Event()
    gate = asyncio.Event()

    class _BarrierTransport:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
            self.calls.append(name)
            if name == "first":
                started.set()
            else:
                second_started.set()
            await gate.wait()
            return {"name": name}

    transport = _BarrierTransport()
    d = Dispatcher(
        connectors={
            "c1": PreparedConnector(
                connector_id="c1",
                provider_id="prov",
                transport=transport,
                tools={"first": _td("first"), "second": _td("second")},
            ),
        },
        allowlist={},
    )

    async def releaser() -> None:
        # Wait until both transport calls have entered, then release them.
        # If `dispatch_many` is serial, `second_started` will never set
        # because the second coroutine cannot start until the first returns.
        await asyncio.wait_for(started.wait(), timeout=1.0)
        await asyncio.wait_for(second_started.wait(), timeout=1.0)
        gate.set()

    calls = [
        ToolCallRequest(prefixed_name="prov__first", arguments={}, call_id="1"),
        ToolCallRequest(prefixed_name="prov__second", arguments={}, call_id="2"),
    ]
    results, _ = await asyncio.gather(dispatch_many(d, calls), releaser())
    assert [r.ok for r in results] == [True, True]
    assert [r.call_id for r in results] == ["1", "2"]


async def test_dispatch_many_empty_input_returns_empty_list():
    d, _ = _make_dispatcher()
    out = await dispatch_many(d, [])
    assert out == []
