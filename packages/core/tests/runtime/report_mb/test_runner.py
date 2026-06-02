import contextlib

import pytest
from openlia.llm.runtime.report_mb import (
    BriefingContext,
    CancelToken,
    LLMSession,
    MbDataTransports,
    Runner,
)
from openlia.llm.runtime.report_mb.schemas import EnabledConnectors, RunRequest
from openlia.llm.runtime.report_v2_3.templates.spec import SectionSpec, TemplateSpec

from ._fakes import FakeLLMProvider, script_text, script_tool_calls


def _req(connectors: EnabledConnectors) -> RunRequest:
    return RunRequest(
        subject="Morning Briefing - 2026-06-02",
        template=TemplateSpec(
            template_id="mb_default",
            name="Morning Briefing",
            shape_description="Recurring market briefing",
            ticker_anchored=False,
            default_length="normal",
            sections=[SectionSpec(id="overnight", title="Overnight", intent="What moved")],
        ),
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        enabled_connectors=connectors,
        briefing_context=BriefingContext(run_date="2026-06-02"),
    )


def _transports() -> MbDataTransports:
    return MbDataTransports(
        quotes=lambda tickers: [{"ticker": t, "close": 1.0} for t in tickers],
        prices=lambda ticker, rng: [{"ticker": ticker, "range": rng}],
        news=lambda **kwargs: [{"title": "Markets rally", "symbol": kwargs.get("symbol")}],
        economic_calendar=lambda window: [{"event": "CPI", "window": window}],
        macro_indicators=lambda keys: {k: 1.0 for k in keys},
    )


def _runner_with_fake(request: RunRequest, responses):
    session = LLMSession.create(provider_kind="anthropic", model="claude-sonnet-4-6")
    fake = FakeLLMProvider(scripted_responses=responses)
    session.attach_adapter(fake)
    runner = Runner(request=request, transports=_transports(), max_turns=20)
    return runner, session, fake


@pytest.mark.asyncio
async def test_runner_data_tool_then_write_then_finalize():
    """One data-tool call, then write a section, then finalize -> completed."""
    req = _req(EnabledConnectors(provider_ids=frozenset({"eodhd"}), web_search=False))
    script = [
        script_tool_calls(("get_quotes", {"tickers": ["SPY.US"]})),
        script_tool_calls(
            ("write_section", {"section_id": "overnight", "markdown": "Indices rose."})
        ),
        script_tool_calls(("finalize", {})),
    ]
    runner, session, _ = _runner_with_fake(req, script)
    result = await runner.run(session=session)
    assert result.status == "completed"
    assert len(result.sections) >= 1
    assert any(s["section_id"] == "overnight" for s in result.sections)


@pytest.mark.asyncio
async def test_runner_offers_market_tools_when_eodhd_enabled():
    req = _req(EnabledConnectors(provider_ids=frozenset({"eodhd"}), web_search=False))
    script = [
        script_tool_calls(("write_section", {"section_id": "overnight", "markdown": "body."})),
        script_tool_calls(("finalize", {})),
    ]
    runner, session, fake = _runner_with_fake(req, script)
    result = await runner.run(session=session)
    assert result.status == "completed"
    offered = {t.name for t in fake.captured_requests[0].tools}
    assert {"get_quotes", "get_economic_calendar"} <= offered
    assert "get_earnings_calendar" not in offered


@pytest.mark.asyncio
async def test_runner_text_turn_without_finalize_fails():
    req = _req(EnabledConnectors(provider_ids=frozenset(), web_search=False))
    script = [script_text("All done.")]
    runner, session, _ = _runner_with_fake(req, script)
    result = await runner.run(session=session)
    assert result.status == "failed"
    assert "without calling any tool" in result.message


@pytest.mark.asyncio
async def test_runner_enters_dispatcher_context_for_morning_briefing():
    class FakeDispatcher:
        def __init__(self) -> None:
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

    req = _req(EnabledConnectors(provider_ids=frozenset(), web_search=False))
    dispatcher = FakeDispatcher()
    session = LLMSession.create(provider_kind="anthropic", model="claude-sonnet-4-6")
    fake = FakeLLMProvider(
        scripted_responses=[
            script_tool_calls(("write_section", {"section_id": "overnight", "markdown": "body."})),
            script_tool_calls(("finalize", {})),
        ]
    )
    session.attach_adapter(fake)
    runner = Runner(request=req, transports=_transports(), max_turns=20, dispatcher=dispatcher)
    result = await runner.run(session=session)
    assert result.status == "completed"
    assert dispatcher.events == ["enter", "exit"]
    assert dispatcher.department == "morning_briefing"


@pytest.mark.asyncio
async def test_runner_cancellation_yields_failed():
    req = _req(EnabledConnectors(provider_ids=frozenset(), web_search=False))
    script = [script_tool_calls(("finalize", {}))]
    runner, session, _ = _runner_with_fake(req, script)
    token = CancelToken()
    token.cancel()
    result = await runner.run(session=session, cancel_token=token)
    assert result.status == "failed"
    assert "cancelled" in result.message.lower()
