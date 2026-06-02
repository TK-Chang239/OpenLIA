"""EuRunState — step-wise driver parity with the inline Runner."""

import contextlib

import pytest
from openlia.llm.runtime.report_eu import EuDataTransports
from openlia.llm.runtime.report_eu.run_state import EuRunState
from openlia.llm.runtime.report_eu.schemas import EnabledConnectors, RunRequest
from openlia.llm.runtime.report_v2_3.templates.spec import SectionSpec, TemplateSpec

from ._fakes import script_text, script_tool_calls


def _req() -> RunRequest:
    return RunRequest(
        subject="MSFT.US Q3 FY26",
        template=TemplateSpec(
            template_id="eu_default",
            name="EU",
            shape_description="scorecard",
            ticker_anchored=True,
            default_length="normal",
            sections=[SectionSpec(id="quick_take", title="Quick Take", intent="TLDR")],
        ),
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        enabled_connectors=EnabledConnectors(provider_ids=frozenset(), web_search=False),
    )


def _transports() -> EuDataTransports:
    return EuDataTransports(
        fundamentals=lambda t: {},
        prices=lambda t, f, to: [],
        news=lambda t, n: [],
        earnings_calendar=lambda t: [],
    )


def _state(max_turns: int = 20) -> EuRunState:
    return EuRunState.from_request(
        _req(), transports=_transports(), custom_id="r1", max_turns=max_turns
    )


@pytest.mark.asyncio
async def test_write_then_finalize_completes():
    state = _state()
    # Turn 1: a request is pending; it carries system + tools + the user turn.
    req1 = state.pending_request()
    assert req1 is not None
    assert req1.system
    offered = {t.name for t in req1.tools}
    assert {"write_section", "finalize"} <= offered
    assert req1.cache_conversation is True

    await state.apply_response(
        script_tool_calls(
            ("write_section", {"section_id": "quick_take", "markdown": "Quick take body."})
        )
    )
    # Not finalized yet -> another request pending.
    assert state.pending_request() is not None
    assert state.result() is None

    await state.apply_response(script_tool_calls(("finalize", {})))
    assert state.pending_request() is None
    result = state.result()
    assert result is not None
    assert result.status == "completed"
    assert any(s["section_id"] == "quick_take" for s in result.sections)


@pytest.mark.asyncio
async def test_text_turn_without_finalize_fails():
    state = _state()
    state.pending_request()
    await state.apply_response(script_text("All done."))
    assert state.pending_request() is None
    assert state.result().status == "failed"
    assert "without calling any tool" in state.result().message


@pytest.mark.asyncio
async def test_max_turns_without_finalize_fails():
    state = _state(max_turns=2)
    # Two non-finalizing turns, then pending_request trips the hard cap.
    for _ in range(2):
        assert state.pending_request() is not None
        await state.apply_response(
            script_tool_calls(("write_section", {"section_id": "quick_take", "markdown": "x."}))
        )
    assert state.pending_request() is None
    assert state.result().status == "failed"
    assert "hard limit of 2 model turns" in state.result().message


@pytest.mark.asyncio
async def test_tool_dispatch_runs_inside_dispatcher_context():
    class FakeDispatcher:
        def __init__(self):
            self.events: list[str] = []
            self.department: str | None = None

        def candidate_tools(self) -> list[dict]:
            return []

        @contextlib.asynccontextmanager
        async def in_department(self, department: str):
            self.department = department
            self.events.append("enter")
            try:
                yield
            finally:
                self.events.append("exit")

    dispatcher = FakeDispatcher()
    state = EuRunState.from_request(
        _req(), transports=_transports(), custom_id="r1", dispatcher=dispatcher
    )
    state.pending_request()
    await state.apply_response(
        script_tool_calls(("write_section", {"section_id": "quick_take", "markdown": "b."}))
    )
    assert dispatcher.events == ["enter", "exit"]
    assert dispatcher.department == "earnings_update"


@pytest.mark.asyncio
async def test_snapshot_restore_round_trip():
    state = _state()
    state.pending_request()
    await state.apply_response(
        script_tool_calls(("write_section", {"section_id": "quick_take", "markdown": "Body text."}))
    )
    # Simulate a ledger entry (data tools would append these in a real run).
    state.ledger.append(tool_name="get_fundamentals", result_summary="fundamentals")

    snap = state.snapshot()
    restored = EuRunState.restore(snap, transports=_transports())

    # Message history, turn, workspace section, and ledger all round-trip.
    assert [m.role for m in restored.messages] == [m.role for m in state.messages]
    assert restored.messages[-1].content == state.messages[-1].content
    assert restored.turn == state.turn
    assert "quick_take" in restored.workspace.sections
    assert restored.workspace.sections["quick_take"].markdown == "Body text."
    assert len(restored.ledger) == len(state.ledger) == 1

    # The restored run is live: finalize completes it with the section intact.
    assert restored.pending_request() is not None
    await restored.apply_response(script_tool_calls(("finalize", {})))
    result = restored.result()
    assert result is not None
    assert result.status == "completed"
    assert any(s["section_id"] == "quick_take" for s in result.sections)


def test_snapshot_is_json_serializable():
    import json

    state = _state()
    snap = state.snapshot()
    # Round-trips through JSON without error (DB stores it as a JSON string).
    assert json.loads(json.dumps(snap))["custom_id"] == "r1"


@pytest.mark.asyncio
async def test_request_grows_message_history_across_turns():
    state = _state()
    req1 = state.pending_request()
    assert len(req1.messages) == 1  # just the initial user turn
    await state.apply_response(
        script_tool_calls(("write_section", {"section_id": "quick_take", "markdown": "body."}))
    )
    req2 = state.pending_request()
    # assistant turn + tool result appended.
    assert len(req2.messages) == 3
    assert req2.messages[-1].role == "tool"
