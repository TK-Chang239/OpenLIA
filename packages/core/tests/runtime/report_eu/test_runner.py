import pytest
from openlia.llm.runtime.report_eu import CancelToken, EuDataTransports, LLMSession, Runner
from openlia.llm.runtime.report_eu.schemas import EnabledConnectors, RunRequest
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
