"""Only asserts that every fake can be instantiated and its basic
behavior — the full behavioral tests live alongside each executor /
service / route test file."""

from __future__ import annotations

import pytest
from _scheduler_fakes import (
    FakeEUPlanner,
    FakeMBBuilder,
    FakeMRBuilder,
    FakeMRCacheStore,
    FakeReportRunner,
    FakeReportStore,
    FakeSleep,
)
from openlia.llm.runtime.events import ReportComplete, ReportStart
from openlia.llm.runtime.messages import BatchItem, ReportRequest


@pytest.mark.asyncio
async def test_fake_sleep_records_durations_without_waiting() -> None:
    fs = FakeSleep()
    await fs(30)
    await fs(120)
    assert fs.calls == [30, 120]


def test_fake_mb_builder_returns_scripted_request() -> None:
    fb = FakeMBBuilder(request=ReportRequest(mode="mb", user_input="morning"))
    out = fb.build(session=None, user_id="u_1", schedule_id="s_1")
    assert out.mode == "mb"


def test_fake_eu_planner_returns_configured_targets() -> None:
    from openlia_server.scheduler.payloads import EUScanTarget

    targets = [
        EUScanTarget(
            ticker="AAPL",
            request=ReportRequest(mode="stock_update", user_input="aapl"),
        )
    ]
    fp = FakeEUPlanner(targets=targets)
    assert fp.plan(session=None, user_id="u_1", schedule_id="s_1", since=None) == targets


def test_fake_mr_builder_returns_batch_and_synth() -> None:
    from openlia.llm.runtime.messages import BatchResult

    fb = FakeMRBuilder(
        items=[BatchItem(id="i1", context={})],
        synth=ReportRequest(mode="mr_synth", user_input="t5"),
    )
    p = fb.build(session=None, user_id="u_1")
    assert p.items[0].id == "i1"
    assert p.t4_task == "t4"

    req = p.synthesize([BatchResult(id="i1", ok=True, data={"x": 1}, error=None)])
    assert req.mode == "mr_synth"
    assert fb.received_results[0][0].id == "i1"


def test_fake_report_store_captures_saves() -> None:
    store = FakeReportStore(next_id="r_xyz")
    rid = store.save(session=None, user_id="u_1", department="morning_briefing", payload={"a": 1})
    assert rid == "r_xyz"
    assert store.saves[0]["department"] == "morning_briefing"


def test_fake_mr_cache_store_captures_saves() -> None:
    store = FakeMRCacheStore(next_id="c_1")
    cid = store.save(session=None, user_id="u_1", payload={"risk": "low"})
    assert cid == "c_1"
    assert store.saves[0]["user_id"] == "u_1"


@pytest.mark.asyncio
async def test_fake_report_runner_streams_scripted_events_and_returns() -> None:
    rr = FakeReportRunner(
        events=[
            ReportStart(
                report_id="r_1",
                department="morning_briefing",
                mode="mb",
                section_titles=["s1"],
            ),
            ReportComplete(report_id="r_1", schema={"title": "t", "sections": []}),
        ]
    )

    collected: list = []
    async for ev in rr.run(
        department_id="morning_briefing",
        user_id="u_1",
        request=ReportRequest(mode="mb", user_input="x"),
        cancel_token=None,
    ):
        collected.append(ev)
    assert len(collected) == 2
    assert rr.calls[0]["department_id"] == "morning_briefing"
