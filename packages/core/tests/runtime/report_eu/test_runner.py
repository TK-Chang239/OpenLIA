import contextlib

import pytest
from openlia.llm.runtime.report_eu import CancelToken, EuDataTransports, LLMSession, Runner
from openlia.llm.runtime.report_eu import runner as runner_module
from openlia.llm.runtime.report_eu.schemas import EnabledConnectors, RunRequest
from openlia.llm.runtime.report_v2_3.research import ResearchTool, ToolResult
from openlia.llm.runtime.report_v2_3.research.tools import ToolDescriptor
from openlia.llm.runtime.report_v2_3.schemas import ComputedSource
from openlia.llm.runtime.report_v2_3.templates.spec import SectionSpec, TemplateSpec

from ._fakes import FakeLLMProvider, script_text, script_tool_calls


def _req(connectors: EnabledConnectors) -> RunRequest:
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
        enabled_connectors=connectors,
    )


def _transports() -> EuDataTransports:
    return EuDataTransports(
        fundamentals=lambda t: {},
        prices=lambda t, f, to: [],
        news=lambda t, n: [],
        earnings_calendar=lambda t: [],
    )


def _runner_with_fake(request: RunRequest, responses):
    session = LLMSession.create(provider_kind="anthropic", model="claude-sonnet-4-6")
    fake = FakeLLMProvider(scripted_responses=responses)
    session.attach_adapter(fake)
    runner = Runner(request=request, transports=_transports(), max_turns=20)
    return runner, session, fake


@pytest.mark.asyncio
async def test_runner_writes_then_finalizes():
    """All connectors off: turn 1 writes quick_take, turn 2 finalizes."""
    req = _req(EnabledConnectors(provider_ids=frozenset(), web_search=False))
    script = [
        script_tool_calls(
            ("write_section", {"section_id": "quick_take", "markdown": "Quick take body."})
        ),
        script_tool_calls(("finalize", {})),
    ]
    runner, session, _ = _runner_with_fake(req, script)
    result = await runner.run(session=session)
    assert result.status == "completed"
    assert any(s["section_id"] == "quick_take" for s in result.sections)


@pytest.mark.asyncio
async def test_runner_all_off_catalog_excludes_data_tools():
    """With every connector off the model is offered only output tools."""
    req = _req(EnabledConnectors(provider_ids=frozenset(), web_search=False))
    script = [
        script_tool_calls(("write_section", {"section_id": "quick_take", "markdown": "body."})),
        script_tool_calls(("finalize", {})),
    ]
    runner, session, fake = _runner_with_fake(req, script)
    result = await runner.run(session=session)
    assert result.status == "completed"
    offered = {t.name for t in fake.captured_requests[0].tools}
    assert "get_fundamentals" not in offered
    assert "get_earnings_calendar" not in offered
    assert {"write_section", "finalize"} <= offered
    assert fake.captured_requests[0].native_tools == ()


@pytest.mark.asyncio
async def test_runner_financial_on_offers_data_tools():
    req = _req(EnabledConnectors(provider_ids=frozenset({"eodhd"}), web_search=False))
    script = [
        script_tool_calls(("write_section", {"section_id": "quick_take", "markdown": "body."})),
        script_tool_calls(("finalize", {})),
    ]
    runner, session, fake = _runner_with_fake(req, script)
    result = await runner.run(session=session)
    assert result.status == "completed"
    offered = {t.name for t in fake.captured_requests[0].tools}
    assert {"get_fundamentals", "get_earnings_calendar"} <= offered


@pytest.mark.asyncio
async def test_runner_text_turn_without_finalize_fails():
    """Model ends a turn with text and no tool call before finalize ⇒ failed."""
    req = _req(EnabledConnectors(provider_ids=frozenset(), web_search=False))
    script = [script_text("All done, here is the report.")]
    runner, session, _ = _runner_with_fake(req, script)
    result = await runner.run(session=session)
    assert result.status == "failed"
    assert "without calling any tool" in result.message


@pytest.mark.asyncio
async def test_runner_max_turns_without_finalize_fails():
    """max_turns reached without a finalize call ⇒ failed."""
    req = _req(EnabledConnectors(provider_ids=frozenset(), web_search=False))
    session = LLMSession.create(provider_kind="anthropic", model="claude-sonnet-4-6")
    # Three non-finalizing tool-call turns, but the runner stops after two.
    script = [
        script_tool_calls(("write_section", {"section_id": "quick_take", "markdown": "a."})),
        script_tool_calls(("write_section", {"section_id": "quick_take", "markdown": "b."})),
        script_tool_calls(("write_section", {"section_id": "quick_take", "markdown": "c."})),
    ]
    fake = FakeLLMProvider(scripted_responses=script)
    session.attach_adapter(fake)
    runner = Runner(request=req, transports=_transports(), max_turns=2)
    result = await runner.run(session=session)
    assert result.status == "failed"
    assert "hard limit of 2 model turns" in result.message


def _make_async_tool(name: str, recorder: list[str]) -> ResearchTool:
    """A ResearchTool whose execute is a coroutine returning a ToolResult."""

    async def _aexec(args: dict) -> ToolResult:
        recorder.append(name)
        return ToolResult(
            payload={"ok": True, "echo": args},
            provenance=ComputedSource(method=name, derived_from=["(async)"]),
            summary=f"async tool {name} ran",
        )

    return ResearchTool(
        descriptor=ToolDescriptor(
            name=name,
            description="async test tool",
            parameters={"type": "object", "properties": {}},
        ),
        execute=_aexec,
    )


def _patch_catalog_with(monkeypatch, extra_tool: ResearchTool) -> None:
    """Wrap build_catalog so the runner's catalog also carries extra_tool."""
    real_build = runner_module.build_catalog

    def _wrapped(**kwargs):
        catalog = real_build(**kwargs)
        catalog.core_tools.append(extra_tool)
        return catalog

    monkeypatch.setattr(runner_module, "build_catalog", _wrapped)


@pytest.mark.asyncio
async def test_runner_dispatches_async_tool(monkeypatch):
    """A tool whose execute is a coroutine is awaited and its result reaches the loop."""
    req = _req(EnabledConnectors(provider_ids=frozenset(), web_search=False))
    recorder: list[str] = []
    _patch_catalog_with(monkeypatch, _make_async_tool("async_probe", recorder))
    script = [
        script_tool_calls(
            ("async_probe", {"x": 1}),
            ("write_section", {"section_id": "quick_take", "markdown": "body."}),
        ),
        script_tool_calls(("finalize", {})),
    ]
    runner, session, fake = _runner_with_fake(req, script)
    result = await runner.run(session=session)
    assert result.status == "completed"
    # The coroutine actually ran (await happened).
    assert recorder == ["async_probe"]
    # The awaited tool result (a serialized ToolResult, not a coroutine repr)
    # reached the model as a tool message on the next turn.
    second_messages = fake.captured_requests[1].messages
    tool_msgs = [m for m in second_messages if m.role == "tool"]
    assert any('"echo"' in m.content for m in tool_msgs)
    assert not any("coroutine" in m.content for m in tool_msgs)


@pytest.mark.asyncio
async def test_runner_enters_dispatcher_context():
    """When a dispatcher is supplied the turn loop runs inside in_department(...)."""

    class FakeDispatcher:
        def __init__(self) -> None:
            self.events: list[str] = []
            self.department: str | None = None

        @contextlib.asynccontextmanager
        async def in_department(self, department: str):
            self.department = department
            self.events.append("enter")
            try:
                yield
            finally:
                self.events.append("exit")

    req = _req(EnabledConnectors(provider_ids=frozenset(), web_search=False))
    dispatcher = FakeDispatcher()
    session = LLMSession.create(provider_kind="anthropic", model="claude-sonnet-4-6")
    fake = FakeLLMProvider(
        scripted_responses=[
            script_tool_calls(("write_section", {"section_id": "quick_take", "markdown": "body."})),
            script_tool_calls(("finalize", {})),
        ]
    )
    session.attach_adapter(fake)
    runner = Runner(
        request=req,
        transports=_transports(),
        max_turns=20,
        dispatcher=dispatcher,
    )
    result = await runner.run(session=session)
    assert result.status == "completed"
    assert dispatcher.events == ["enter", "exit"]
    assert dispatcher.department == "earnings_update"


@pytest.mark.asyncio
async def test_runner_cancellation_yields_failed():
    """A cancelled token ⇒ terminal failed status with a cancel message."""
    req = _req(EnabledConnectors(provider_ids=frozenset(), web_search=False))
    script = [script_tool_calls(("finalize", {}))]
    runner, session, _ = _runner_with_fake(req, script)
    token = CancelToken()
    token.cancel()
    result = await runner.run(session=session, cancel_token=token)
    assert result.status == "failed"
    assert "cancelled" in result.message.lower()
