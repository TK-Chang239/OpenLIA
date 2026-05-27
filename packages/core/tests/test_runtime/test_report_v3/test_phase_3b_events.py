"""Phase 3b-backend tests for the events module + emitter wiring.

Exercises:
  - EventBroker pub-sub fans events to subscribers and stops on finish
  - ListEmitter captures runner emits in order on a happy-path run
  - Runner emits run.started, tool.called, tool.completed,
    section.written, chart.emitted, run.completed in the right order
  - Cancel token causes the runner to exit cleanly with run.cancelled
  - Tool error path emits tool.completed with ok=False + error string
"""

from __future__ import annotations

import asyncio

import pytest
from openlia.llm.runtime.report_v2_3.schemas import ReportType
from openlia.llm.runtime.report_v2_3.templates.builtins import get_builtin
from openlia.llm.runtime.report_v3 import (
    BrokerEmitter,
    CancelToken,
    DataTransports,
    Event,
    EventBroker,
    Language,
    ListEmitter,
    LLMSession,
    NullEmitter,
    ReportLength,
    Runner,
    RunRequest,
    is_finish_sentinel,
)

from ._fakes import FakeLLMProvider, script_tool_calls

# ---------------------------------------------------------------------------
# Broker
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_broker_fans_events_to_subscriber_then_stops_on_finish():
    broker = EventBroker()
    received: list[Event] = []

    async def consume():
        async with broker.subscribe("run-1") as queue:
            while True:
                item = await queue.get()
                if is_finish_sentinel(item):
                    break
                received.append(item)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0)  # let consumer attach
    broker.publish("run-1", Event(type="run.started", payload={"a": 1}))
    broker.publish("run-1", Event(type="tool.called", payload={"b": 2}))
    broker.finish("run-1")
    await asyncio.wait_for(task, timeout=1.0)

    assert [e.type for e in received] == ["run.started", "tool.called"]
    assert received[0].payload == {"a": 1}


@pytest.mark.asyncio
async def test_broker_isolates_subscribers_by_report_id():
    broker = EventBroker()
    received_a: list[Event] = []
    received_b: list[Event] = []

    async def consume(report_id, sink):
        async with broker.subscribe(report_id) as queue:
            while True:
                item = await queue.get()
                if is_finish_sentinel(item):
                    break
                sink.append(item)

    task_a = asyncio.create_task(consume("a", received_a))
    task_b = asyncio.create_task(consume("b", received_b))
    await asyncio.sleep(0)

    broker.publish("a", Event(type="run.started", payload={"who": "a"}))
    broker.publish("b", Event(type="run.started", payload={"who": "b"}))
    broker.finish("a")
    broker.finish("b")
    await asyncio.wait_for(task_a, timeout=1.0)
    await asyncio.wait_for(task_b, timeout=1.0)

    assert [e.payload["who"] for e in received_a] == ["a"]
    assert [e.payload["who"] for e in received_b] == ["b"]


def test_broker_emitter_adapter_publishes_to_broker():
    broker = EventBroker()
    received: list[Event] = []

    async def consume():
        async with broker.subscribe("run-1") as queue:
            received.append(await queue.get())

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_consume_one_emit(loop, broker, received))
    finally:
        loop.close()

    assert len(received) == 1
    assert received[0].type == "test.event"
    assert received[0].payload == {"k": "v"}


async def _consume_one_emit(loop, broker, sink):
    async def consume():
        async with broker.subscribe("run-1") as queue:
            sink.append(await queue.get())

    task = loop.create_task(consume())
    await asyncio.sleep(0)
    emitter = BrokerEmitter(broker=broker, report_id="run-1")
    emitter.emit("test.event", {"k": "v"})
    await asyncio.wait_for(task, timeout=1.0)


# ---------------------------------------------------------------------------
# Emitters
# ---------------------------------------------------------------------------


def test_null_emitter_drops_silently():
    emitter = NullEmitter()
    # Should not raise; no side effects observable.
    emitter.emit("foo", {"bar": 1})


def test_list_emitter_captures_in_order():
    emitter = ListEmitter()
    emitter.emit("a", {"i": 1})
    emitter.emit("b", {"i": 2})
    assert [e.type for e in emitter.events] == ["a", "b"]
    assert emitter.events[0].payload == {"i": 1}


# ---------------------------------------------------------------------------
# Runner emits at the right points
# ---------------------------------------------------------------------------


def _fake_transports() -> DataTransports:
    return DataTransports(
        fundamentals=lambda ticker: {"ticker": ticker},
        prices=lambda ticker, from_date, to_date: [],
        news=lambda ticker, limit: [{"title": "x", "url": f"https://x.test/{ticker}"}],
    )


def _request() -> RunRequest:
    return RunRequest(
        subject="RKLB.US",
        template=get_builtin(ReportType.INITIATION),
        language=Language.EN,
        length=ReportLength.NORMAL,
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
    )


def _runner_with(responses) -> tuple[Runner, LLMSession]:
    session = LLMSession.create(provider_kind="anthropic", model="claude-sonnet-4-6")
    fake = FakeLLMProvider(scripted_responses=responses)
    session.attach_adapter(fake)
    return Runner(max_turns=20, transports_factory=_fake_transports), session


def _happy_script(req: RunRequest, with_chart: bool = False):
    section_ids = [s.id for s in req.template.sections]
    script = [script_tool_calls(("get_company_news", {"ticker": "RKLB.US"}))]
    if with_chart:
        script.append(
            script_tool_calls(
                (
                    "emit_chart",
                    {
                        "chart_id": "trend",
                        "chart_type": "line",
                        "title": "Trend",
                        "data": [{"x": "2024", "y": 1.0}, {"x": "2025", "y": 2.0}],
                        "source_ids": ["eodhd_1"],
                    },
                )
            )
        )
    for sid in section_ids:
        script.append(
            script_tool_calls(
                (
                    "write_section",
                    {"section_id": sid, "markdown": f"{sid} [^eodhd_1]."},
                )
            )
        )
    script.append(script_tool_calls(("finalize", {})))
    return script


@pytest.mark.asyncio
async def test_runner_emits_full_event_sequence_on_happy_path():
    req = _request()
    runner, session = _runner_with(_happy_script(req, with_chart=True))
    emitter = ListEmitter()
    result = await runner.run(req, session=session, emitter=emitter)
    assert result.status == "completed"

    types = [e.type for e in emitter.events]
    # First event is always run.started
    assert types[0] == "run.started"
    # tool.called and tool.completed should appear in pairs
    assert types.count("tool.called") == types.count("tool.completed")
    # At least one section.written and one chart.emitted
    assert "chart.emitted" in types
    assert "section.written" in types
    # Last event is the terminal one
    assert types[-1] == "run.completed"

    # Payload sanity check on run.started
    start_payload = emitter.events[0].payload
    assert start_payload["subject"] == "RKLB.US"
    assert start_payload["template_id"] == req.template.template_id

    # section.written carries the section_id and char_count
    section_events = [e for e in emitter.events if e.type == "section.written"]
    assert {e.payload["section_id"] for e in section_events} == {
        s.id for s in req.template.sections
    }
    assert all(e.payload["char_count"] is not None for e in section_events)


@pytest.mark.asyncio
async def test_runner_emits_run_cancelled_when_token_flipped_before_first_turn():
    req = _request()
    runner, session = _runner_with(_happy_script(req))
    emitter = ListEmitter()
    cancel_token = CancelToken()
    cancel_token.cancel()  # pre-cancel so the first turn check trips
    result = await runner.run(
        req, session=session, emitter=emitter, cancel_token=cancel_token
    )
    assert result.status == "failed"
    assert "cancelled" in result.message
    types = [e.type for e in emitter.events]
    assert types[0] == "run.started"
    assert types[-1] == "run.cancelled"


@pytest.mark.asyncio
async def test_runner_emits_tool_completed_with_ok_false_on_tool_error():
    """An emit_chart with an invalid source_id surfaces as ok=False."""
    req = _request()
    section_ids = [s.id for s in req.template.sections]
    script = [
        script_tool_calls(("get_company_news", {"ticker": "RKLB.US"})),
        script_tool_calls(
            (
                "emit_chart",
                {
                    "chart_id": "bad",
                    "chart_type": "line",
                    "title": "Bad",
                    "data": [{"x": "2024", "y": 1.0}],
                    "source_ids": ["web_999"],
                },
            )
        ),
    ]
    for sid in section_ids:
        script.append(
            script_tool_calls(
                ("write_section", {"section_id": sid, "markdown": f"{sid} [^eodhd_1]."})
            )
        )
    script.append(script_tool_calls(("finalize", {})))
    runner, session = _runner_with(script)
    emitter = ListEmitter()
    await runner.run(req, session=session, emitter=emitter)

    chart_completed = next(
        e
        for e in emitter.events
        if e.type == "tool.completed" and e.payload["tool_name"] == "emit_chart"
    )
    assert chart_completed.payload["ok"] is False
    assert chart_completed.payload["error"] is not None
