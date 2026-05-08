from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from _scheduler_fakes import (
    FakeAPScheduler,
    FakeBatchRunner,
    FakeMBBuilder,
    FakeMRBuilder,
    FakeMRCacheStore,
    FakeReportRunner,
    FakeReportStore,
    StubEUScanPlanner,
)
from openlia.llm.runtime.events import ReportComplete, ReportStart
from openlia.llm.runtime.messages import ReportRequest
from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import (
    JobRun,
    MbSchedule,
    UserNotification,
)
from openlia_server.scheduler.registry import (
    JobStatus,
    JobType,
    job_key,
)
from openlia_server.scheduler.settings import SchedulerSettings
from openlia_server.scheduler.wiring import build_scheduler_service


@pytest.mark.asyncio
async def test_end_to_end_morning_briefing_fires_saves_and_notifies(
    session_factory,
) -> None:
    # --- seed ---
    with session_factory() as s:
        s.add(
            User(
                id="u_1",
                email="u@e.com",
                display_name="u",
                password_hash="h",
                is_admin=False,
                is_disabled=False,
            )
        )
        s.add(
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
        s.commit()

    # --- real executor graph, fake APScheduler + fake runners/builders ---
    fake_scheduler = FakeAPScheduler()
    svc = build_scheduler_service(
        session_factory=session_factory,
        settings=SchedulerSettings(enabled=True),
        scheduler=fake_scheduler,
        report_runner=FakeReportRunner(
            events=[
                ReportStart(
                    report_id="r_1",
                    department="morning_briefing",
                    mode="mb",
                    section_titles=["Overnight"],
                ),
                ReportComplete(
                    report_id="r_1",
                    schema={"title": "Briefing", "sections": []},
                ),
            ]
        ),
        batch_runner=FakeBatchRunner(results=[]),
        mb_builder=FakeMBBuilder(request=ReportRequest(mode="morning_briefing", user_input="go")),
        eu_planner=StubEUScanPlanner(),
        mr_builder=FakeMRBuilder(
            items=[], synth=ReportRequest(mode="mr_synthesis", user_input="x")
        ),
        report_store=FakeReportStore(next_id="rep_final"),
        mr_cache_store=FakeMRCacheStore(),
    )
    await svc.start()

    # Confirm the schedule was rehydrated.
    key = job_key(JobType.MB_BRIEFING, "u_1", "sch_mb")
    assert key in fake_scheduler.jobs

    # --- fire the scheduled callback ---
    await fake_scheduler.fire(key)

    # --- asserts ---
    with session_factory() as s:
        runs = s.query(JobRun).all()
        assert len(runs) == 1
        run = runs[0]
        assert run.status == JobStatus.COMPLETED.value
        assert run.user_id == "u_1"
        assert run.job_type == JobType.MB_BRIEFING.value
        assert json.loads(run.result_summary) == {"report_id": "rep_final"}

        notifs = s.query(UserNotification).all()
        assert len(notifs) == 1
        assert notifs[0].type == "report_ready"
        assert notifs[0].department == "morning_briefing"

        sched = s.get(MbSchedule, "sch_mb")
        assert sched.last_run_at is not None

    await svc.shutdown()
    assert fake_scheduler.stopped is True
