"""Tests for multi-turn writing phase in ReportRunner.

Four scenarios:
  1. Writing phase converges on submit_report immediately (turn 0).
  2. Writing phase calls read_payload then submit_report (2 writing turns).
  3. Writing phase forces submit on the final turn (monkeypatched MAX_WRITING_TURNS=2).
  4. writing.forced_submit trace fires when loop exhausts (monkeypatched MAX_WRITING_TURNS=2,
     model never returns submit_report).
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest
from _fakes import FakeDataDispatcher, FakeProvider, FakeProviderScript
from openlia.llm.runtime.events import ReportComplete, ReportError, ReportToolCall
from openlia.llm.runtime.messages import ReportRequest
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.report import ReportRunner
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import (
    Capabilities,
    ProviderCredentials,
    ResolvedModel,
    ToolCall,
)
from openlia.skills import FilesystemSkillStore, LayeredSkillStore, SkillRegistry

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SUBMIT_PAYLOAD = {
    "cover": {
        "title": "AAPL",
        "subtitle": "Coverage initiation",
        "tagline": "Constructive setup",
    },
    "sections": [],
}


def _empty_skill_registry(tmp_path: Path) -> SkillRegistry:
    fs = FilesystemSkillStore(root=tmp_path)
    return SkillRegistry(store=LayeredSkillStore(system=fs, user=fs))


def _resolved() -> ResolvedModel:
    return ResolvedModel(
        provider_kind="fake",
        provider_id="p1",
        model_id="m1",
        model_ref="fake-1",
        credentials=ProviderCredentials(api_key="k", base_url=None),
        capabilities=Capabilities(streaming=True, tool_calling=True, structured_output=True),
        overrides={},
    )


def _always(resolved: ResolvedModel):
    def _r(
        *,
        department_id: str,
        user_id: str | None,
        registry: Any,
        model_id_override: str | None = None,
    ) -> ResolvedModel:
        return resolved

    return _r


@pytest.fixture
def frameworks_root(tmp_path: Path) -> Path:
    root = tmp_path / "frameworks"
    root.mkdir()
    (root / "stock_initiation.json").write_text(
        json.dumps(
            {
                "title": "Stock Initiation",
                "sections": [
                    {"id": "overview", "title": "Overview", "instructions": "..."},
                ],
            }
        )
    )
    (root / "stock_initiation_style_guide.md").write_text("# Style\n")
    return root


@pytest.fixture
def prompts_root(tmp_path: Path) -> Path:
    root = tmp_path / "prompts"
    shared = root / "shared"
    shared.mkdir(parents=True)
    (shared / "output_discipline.yaml.j2").write_text("discipline.\n")
    (root / "equity_research.yaml").write_text(
        dedent(
            """\
            report:
              system: |
                Style: {{ style_guide }}
              stock_initiation:
                user: |
                  Topic: {{ user_input }}
                  Framework: {{ framework | tojson }}
            """
        )
    )
    return root


def _make_runner(
    provider: FakeProvider,
    prompts_root: Path,
    frameworks_root: Path,
    tmp_path: Path,
    *,
    trace: list[tuple[str, str, dict[str, Any] | None]] | None = None,
) -> ReportRunner:
    data = FakeDataDispatcher()
    dispatcher = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(available=False, variant=None, adapter=None),
    )

    def _trace(category: str, message: str, payload: dict[str, Any] | None) -> None:
        if trace is not None:
            trace.append((category, message, payload))

    return ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=dispatcher,
        resolve=_always(_resolved()),
        registry=object(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path),
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_writing_test",
        trace=_trace,
    )


async def _collect(runner: ReportRunner) -> list[Any]:
    return [
        e
        async for e in runner.run(
            department_id="equity_research",
            user_id="u1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    ]


# ---------------------------------------------------------------------------
# Test 1: submit_report on writing turn 0
# ---------------------------------------------------------------------------


async def test_writing_converges_immediately(
    prompts_root: Path,
    frameworks_root: Path,
    tmp_path: Path,
) -> None:
    """Writing turn 0 returns submit_report — no additional writing turns."""
    submit_call = ToolCall(id="w0", name="submit_report", arguments=_SUBMIT_PAYLOAD)

    # Data-fetch loop: one empty turn → break
    # Writing turn 0: submit_report immediately
    script = FakeProviderScript(
        turns=[
            ("final", ""),  # fetching_data loop — no tool calls, exits
            ("tool_calls", [submit_call]),  # writing turn 0 — immediate submit
        ]
    )
    provider = FakeProvider(script=script)
    trace: list[tuple[str, str, dict[str, Any] | None]] = []
    runner = _make_runner(provider, prompts_root, frameworks_root, tmp_path, trace=trace)
    events = await _collect(runner)

    # Should complete successfully
    completes = [e for e in events if isinstance(e, ReportComplete)]
    errors = [e for e in events if isinstance(e, ReportError)]
    assert not errors, f"Unexpected errors: {errors}"
    assert len(completes) == 1

    # Only 2 LLM calls total: 1 fetching_data + 1 writing
    assert len(provider.captured_requests) == 2

    # Verify writing turn 0 had tool_choice=None (not forced), NOT forced
    writing_req = provider.captured_requests[1]
    assert writing_req.tool_choice is None

    # No writing.forced_submit trace
    forced_traces = [t for t in trace if t[0] == "writing.forced_submit"]
    assert not forced_traces


# ---------------------------------------------------------------------------
# Test 2: read_payload on turn 0, then submit_report on turn 1
# ---------------------------------------------------------------------------


async def test_writing_read_payload_then_submit(
    prompts_root: Path,
    frameworks_root: Path,
    tmp_path: Path,
) -> None:
    """Writing turn 0 calls read_payload; turn 1 calls submit_report."""
    # We need an actual ref in the dispatcher's payload store. Since FakeDataDispatcher
    # returns tiny payloads (below threshold), read_payload with an unknown ref
    # will return an error — but we still verify the tool dispatch path fires.
    # Use a ref that doesn't exist; the dispatcher will return ok=False, but
    # the conversation still gets the tool result and the loop continues.
    read_call = ToolCall(id="rp0", name="read_payload", arguments={"ref": "r_fake_01"})
    submit_call = ToolCall(id="w1", name="submit_report", arguments=_SUBMIT_PAYLOAD)

    script = FakeProviderScript(
        turns=[
            ("final", ""),  # fetching_data loop — break
            ("tool_calls", [read_call]),  # writing turn 0 — read_payload
            ("tool_calls", [submit_call]),  # writing turn 1 — submit_report
        ]
    )
    provider = FakeProvider(script=script)
    trace: list[tuple[str, str, dict[str, Any] | None]] = []
    runner = _make_runner(provider, prompts_root, frameworks_root, tmp_path, trace=trace)
    events = await _collect(runner)

    completes = [e for e in events if isinstance(e, ReportComplete)]
    errors = [e for e in events if isinstance(e, ReportError)]
    assert not errors, f"Unexpected errors: {errors}"
    assert len(completes) == 1

    # 3 total LLM calls: 1 fetching_data + 2 writing
    assert len(provider.captured_requests) == 3

    # writing.read_payload trace should have fired
    rp_traces = [t for t in trace if t[0] == "writing.read_payload"]
    assert len(rp_traces) == 1

    # ReportToolCall event for read_payload
    tool_events = [e for e in events if isinstance(e, ReportToolCall)]
    assert any(e.tool_name == "read_payload" for e in tool_events)

    # No forced_submit trace
    forced_traces = [t for t in trace if t[0] == "writing.forced_submit"]
    assert not forced_traces

    # Writing turn 1 should NOT be forced (MAX_WRITING_TURNS=8, we're at turn 1)
    writing_req_1 = provider.captured_requests[2]
    assert writing_req_1.tool_choice is None


# ---------------------------------------------------------------------------
# Test 3: forced submit on final writing turn
# ---------------------------------------------------------------------------


async def test_writing_forces_submit_on_final_turn(
    prompts_root: Path,
    frameworks_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With MAX_WRITING_TURNS=2: turn 0 returns read_payload,
    turn 1 (final, forced) returns submit_report."""
    import openlia.llm.runtime.report as report_mod

    monkeypatch.setattr(report_mod, "MAX_WRITING_TURNS", 2)

    read_call = ToolCall(id="rp0", name="read_payload", arguments={"ref": "r_fake_01"})
    submit_call = ToolCall(id="w1", name="submit_report", arguments=_SUBMIT_PAYLOAD)

    script = FakeProviderScript(
        turns=[
            ("final", ""),  # fetching_data loop — break
            ("tool_calls", [read_call]),  # writing turn 0 — read_payload
            ("tool_calls", [submit_call]),  # writing turn 1 — forced submit_report
        ]
    )
    provider = FakeProvider(script=script)
    trace: list[tuple[str, str, dict[str, Any] | None]] = []
    runner = _make_runner(provider, prompts_root, frameworks_root, tmp_path, trace=trace)
    events = await _collect(runner)

    completes = [e for e in events if isinstance(e, ReportComplete)]
    errors = [e for e in events if isinstance(e, ReportError)]
    assert not errors, f"Unexpected errors: {errors}"
    assert len(completes) == 1

    # 3 LLM calls: 1 fetching + 2 writing
    assert len(provider.captured_requests) == 3

    # writing turn 0 (index 1): tool_choice=None
    writing_req_0 = provider.captured_requests[1]
    assert writing_req_0.tool_choice is None, (
        f"Turn 0 should not be forced; got {writing_req_0.tool_choice}"
    )

    # writing turn 1 (index 2): tool_choice forced (not None)
    writing_req_1 = provider.captured_requests[2]
    assert writing_req_1.tool_choice is not None, "Turn 1 (final) should have a forced tool_choice"

    # No forced_submit trace — loop broke via submit_call
    forced_traces = [t for t in trace if t[0] == "writing.forced_submit"]
    assert not forced_traces


# ---------------------------------------------------------------------------
# Refusal-recovery: text-only on writing turn 0 must NOT exit the loop
# ---------------------------------------------------------------------------


async def test_writing_recovers_from_text_only_refusal(
    prompts_root: Path,
    frameworks_root: Path,
    tmp_path: Path,
) -> None:
    """Production failure mode: model refuses on writing turn 0 with text-only
    response ("I'm sorry, I can't complete this report..."), no tool_calls.

    Previous behavior broke out of the writing loop on the first text-only
    turn and emitted "LLM did not call submit_report" — the user never saw
    a renderable report.

    Required behavior: push a reminder back to the model and continue. The
    next turn produces submit_report (or the final forced turn eventually
    does), and the runner emits ReportComplete."""
    submit_call = ToolCall(id="w1", name="submit_report", arguments=_SUBMIT_PAYLOAD)

    refusal_text = (
        "I'm sorry, but I can't complete this report as requested because the "
        "required data tools are not available in this session, and I should "
        "not fabricate financials."
    )

    script = FakeProviderScript(
        turns=[
            ("final", ""),  # fetching_data loop — break
            ("final", refusal_text),  # writing turn 0 — text-only refusal
            ("tool_calls", [submit_call]),  # writing turn 1 — finally submits
        ]
    )
    provider = FakeProvider(script=script)
    trace: list[tuple[str, str, dict[str, Any] | None]] = []
    runner = _make_runner(provider, prompts_root, frameworks_root, tmp_path, trace=trace)
    events = await _collect(runner)

    # Must complete successfully — no ReportError for refusal.
    errors = [e for e in events if isinstance(e, ReportError)]
    assert not errors, f"Refusal must be recovered, got errors: {[e.message for e in errors]}"
    completes = [e for e in events if isinstance(e, ReportComplete)]
    assert len(completes) == 1, f"Expected ReportComplete, got events: {events}"

    # Three LLM calls: 1 fetching + 2 writing (turn 0 refused, turn 1 submitted).
    assert len(provider.captured_requests) == 3, (
        f"Loop must continue past refusal; got {len(provider.captured_requests)} calls"
    )

    # The conversation sent on writing turn 1 must include a reminder produced
    # in response to the refusal — observable as either a tool-role or user-role
    # message appended after the refusal assistant turn.
    second_writing_request = provider.captured_requests[2]
    follow_up = [
        m
        for m in second_writing_request.messages
        if m.role in {"tool", "user"} and "submit_report" in (m.content or "")
    ]
    msg_summary = [(m.role, (m.content or "")[:60]) for m in second_writing_request.messages]
    assert follow_up, (
        "Expected a reminder message instructing the model to call submit_report "
        f"on writing turn 1; got messages: {msg_summary}"
    )


# ---------------------------------------------------------------------------
# Test 4: writing.forced_submit fires when loop exhausts
# ---------------------------------------------------------------------------


async def test_writing_forced_submit_trace_fires_on_exhaustion(
    prompts_root: Path,
    frameworks_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With MAX_WRITING_TURNS=2, model never returns submit_report on turn 0
    and returns submit_report on the forced turn 1 — but we test the
    for/else path by making both turns return read_payload with the
    final turn also returning read_payload (tool_choice ignored by fake).
    The for/else fires; forced_submit trace is recorded."""
    import openlia.llm.runtime.report as report_mod

    monkeypatch.setattr(report_mod, "MAX_WRITING_TURNS", 2)

    read_call_0 = ToolCall(id="rp0", name="read_payload", arguments={"ref": "r_fake_01"})
    read_call_1 = ToolCall(id="rp1", name="read_payload", arguments={"ref": "r_fake_02"})

    script = FakeProviderScript(
        turns=[
            ("final", ""),  # fetching_data loop — break
            ("tool_calls", [read_call_0]),  # writing turn 0 — read_payload (no submit)
            ("tool_calls", [read_call_1]),  # writing turn 1 — still read_payload (no submit)
        ]
    )
    provider = FakeProvider(script=script)
    trace: list[tuple[str, str, dict[str, Any] | None]] = []
    runner = _make_runner(provider, prompts_root, frameworks_root, tmp_path, trace=trace)
    events = await _collect(runner)

    # Loop exhausted — for/else branch: forced_submit trace should fire.
    forced_traces = [t for t in trace if t[0] == "writing.forced_submit"]
    assert len(forced_traces) == 1, f"Expected 1 forced_submit trace, got {forced_traces}"
    assert forced_traces[0][2] is not None
    assert forced_traces[0][2]["max_turns"] == 2

    # final=None after loop exhaustion without break → ReportError
    errors = [e for e in events if isinstance(e, ReportError)]
    assert len(errors) == 1
    assert errors[0].error_class == "RuntimeError"
    assert "no LLM response" in errors[0].message
