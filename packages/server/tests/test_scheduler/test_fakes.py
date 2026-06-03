"""Only asserts that every fake can be instantiated and its basic
behavior — the full behavioral tests live alongside each executor /
service / route test file."""

from __future__ import annotations

import pytest
from _scheduler_fakes import (
    FakeEUPlanner,
    FakeReportRunner,
    FakeReportStore,
    FakeSleep,
)
from openlia.llm.runtime.events import ReportComplete, ReportStart
from openlia.llm.runtime.messages import ReportRequest


@pytest.mark.asyncio
async def test_fake_sleep_records_durations_without_waiting() -> None:
    fs = FakeSleep()
    await fs(30)
    await fs(120)
    assert fs.calls == [30, 120]


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


def test_fake_report_store_captures_saves() -> None:
    store = FakeReportStore(next_id="r_xyz")
    rid = store.save(session=None, user_id="u_1", department="morning_briefing", payload={"a": 1})
    assert rid == "r_xyz"
    assert store.saves[0]["department"] == "morning_briefing"


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
