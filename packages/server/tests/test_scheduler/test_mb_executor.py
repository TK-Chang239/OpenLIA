from __future__ import annotations

from datetime import UTC, datetime

import pytest
from _fakes import FakeMBBuilder, FakeReportRunner, FakeReportStore, FakeSleep
from openlia.llm.runtime.events import (
    ReportComplete,
    ReportError,
    ReportStart,
)
from openlia.llm.runtime.messages import ReportRequest
from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import JobRun, MbSchedule, UserNotification
from openlia_server.scheduler.executors.mb import MBBriefingExecutor
from openlia_server.scheduler.registry import JobStatus
from sqlalchemy.orm import Session


def _seed(session: Session) -> None:
    session.add(
        User(
            id="u_1",
            email="u@e.com",
            display_name="u",
            password_hash="h",
            is_admin=False,
            is_disabled=False,
        )
    )
    session.add(
        MbSchedule(
            id="sch_mb",
            user_id="u_1",
            time="07:00",
            timezone="UTC",
            days_of_week='["mon","tue","wed","thu","fri"]',
            label="Pre-Market",
            is_enabled=True,
            created_at=datetime.now(UTC),
            last_run_at=None,
        )
    )
    session.commit()


def _events_for_success(report_id: str = "r_1") -> list:
    return [
        ReportStart(
            report_id=report_id,
            department="morning_briefing",
            mode="mb",
            section_titles=["Overnight"],
        ),
        ReportComplete(
            report_id=report_id,
            schema={
                "title": "Briefing",
                "sections": [{"id": "s1", "body": "x"}],
            },
        ),
    ]


@pytest.mark.asyncio
async def test_mb_happy_path_saves_report_and_updates_last_run(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed(s)

    builder = FakeMBBuilder(request=ReportRequest(mode="morning_briefing", user_input="go"))
    runner = FakeReportRunner(events=_events_for_success())
    store = FakeReportStore(next_id="r_final")

    ex = MBBriefingExecutor(
        session_factory=session_factory,
        sleep=FakeSleep(),
        mb_builder=builder,
        report_runner=runner,
        report_store=store,
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="sch_mb")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.COMPLETED.value
        import json

        assert json.loads(row.result_summary) == {"report_id": "r_final"}
        sched = s.get(MbSchedule, "sch_mb")
        assert sched.last_run_at is not None
        notifs = s.query(UserNotification).all()
        assert len(notifs) == 1
        assert notifs[0].type == "report_ready"
        assert notifs[0].department == "morning_briefing"
        assert "Pre-Market" in notifs[0].message

    assert runner.calls[0]["department_id"] == "morning_briefing"
    assert store.saves[0]["department"] == "morning_briefing"


@pytest.mark.asyncio
async def test_mb_report_error_with_transient_class_triggers_retry(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed(s)

    builder = FakeMBBuilder(request=ReportRequest(mode="morning_briefing", user_input="go"))

    class TwoPhaseRunner:
        def __init__(self) -> None:
            self.phase = 0

        async def run(self, **_):
            self.phase += 1
            if self.phase == 1:
                yield ReportStart(
                    report_id="r_a",
                    department="morning_briefing",
                    mode="mb",
                    section_titles=[],
                )
                yield ReportError(
                    report_id="r_a",
                    error_class="RateLimitError",
                    message="429",
                )
                return
            for ev in _events_for_success("r_b"):
                yield ev

    sleep = FakeSleep()
    ex = MBBriefingExecutor(
        session_factory=session_factory,
        sleep=sleep,
        mb_builder=builder,
        report_runner=TwoPhaseRunner(),
        report_store=FakeReportStore(next_id="r_final"),
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="sch_mb")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.COMPLETED.value
        assert row.attempt == 2
    assert sleep.calls == [30]


@pytest.mark.asyncio
async def test_mb_report_error_non_transient_fails_without_retry(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed(s)

    runner = FakeReportRunner(
        events=[
            ReportStart(
                report_id="r_1",
                department="morning_briefing",
                mode="mb",
                section_titles=[],
            ),
            ReportError(
                report_id="r_1",
                error_class="TierNotConfiguredError",
                message="thinking",
            ),
        ]
    )
    sleep = FakeSleep()
    ex = MBBriefingExecutor(
        session_factory=session_factory,
        sleep=sleep,
        mb_builder=FakeMBBuilder(request=ReportRequest(mode="morning_briefing", user_input="go")),
        report_runner=runner,
        report_store=FakeReportStore(),
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="sch_mb")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.FAILED.value
        assert "TierNotConfigured" in row.error_message
        notifs = s.query(UserNotification).all()
        assert notifs[0].type == "job_failed"
    assert sleep.calls == []


@pytest.mark.asyncio
async def test_mb_runner_returns_no_terminal_event_is_non_transient_failure(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed(s)

    runner = FakeReportRunner(
        events=[
            ReportStart(
                report_id="r_1",
                department="morning_briefing",
                mode="mb",
                section_titles=[],
            ),
        ]
    )
    ex = MBBriefingExecutor(
        session_factory=session_factory,
        sleep=FakeSleep(),
        mb_builder=FakeMBBuilder(request=ReportRequest(mode="morning_briefing", user_input="go")),
        report_runner=runner,
        report_store=FakeReportStore(),
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="sch_mb")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.FAILED.value
        assert "ReportComplete" in row.error_message
