from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
from _scheduler_fakes import (
    FakeAPScheduler,
    FakeBatchRunner,
    FakeMRBuilder,
    FakeMRCacheStore,
    FakeReportRunner,
    FakeReportStore,
    StubEUScanPlanner,
)
from openlia.llm.runtime.messages import ReportRequest
from openlia.llm.runtime.report_mb import RunResult
from openlia.llm.runtime.report_mb.default_template import build_default_template
from openlia_server.db.models.auth import User
from openlia_server.db.models.report_mb import ReportMb, ReportMbTemplate
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
from openlia_server.services import mb_v2_run_service


@pytest.mark.asyncio
async def test_end_to_end_morning_briefing_fires_saves_and_notifies(
    session_factory,
    monkeypatch,
) -> None:
    # --- seed: user, mb_default template, a fully-bound schedule ---
    spec = build_default_template()
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
        now = datetime.now(UTC)
        s.add(
            ReportMbTemplate(
                id=spec.template_id,
                user_id=None,
                name=spec.name,
                is_builtin=True,
                template_spec_json=json.loads(spec.model_dump_json()),
                source_markdown=None,
                source_doc_blob=None,
                source_doc_mime=None,
                created_at=now,
                updated_at=now,
                deleted_at=None,
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
                template_id="mb_default",
                instructions_id=None,
                enabled_connectors={"provider_ids": [], "web_search": False},
                provider_kind="anthropic",
                model="claude-sonnet-4-6",
                language="en",
                length="normal",
                reasoning_effort=None,
                web_search=False,
                created_at=now,
                last_run_at=None,
            )
        )
        s.commit()

    # The MB executor runs the report_mb engine inline via mb_v2_run_service.
    # Stub run_to_completion so the engine call is faked but the executor's
    # request-build + persistence + last_run_at + notification path stays real.
    async def _fake_run_to_completion(db, *, user_id, request, **kwargs):
        report_id = str(uuid.uuid4())
        db.add(
            ReportMb(
                id=report_id,
                user_id=user_id,
                subject=request.subject,
                trigger_kind=kwargs.get("trigger_kind", "scheduled"),
                schedule_id=kwargs.get("schedule_id"),
                template_id=request.template.template_id,
                instructions_id=kwargs.get("instructions_id"),
                language=request.language.value,
                length=request.length.value,
                provider_kind=request.provider_kind,
                model=request.model,
                status="completed",
                error_message=None,
                created_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                cover_json=None,
                reasoning_effort=None,
            )
        )
        db.flush()
        result = RunResult(
            status="completed",
            subject=request.subject,
            template_id=request.template.template_id,
            message="",
            sections=[],
            charts=[],
            citations=[],
            cover=None,
        )
        return report_id, result

    monkeypatch.setattr(mb_v2_run_service, "run_to_completion", _fake_run_to_completion)

    # --- real executor graph, fake APScheduler + fake runners/builders ---
    fake_scheduler = FakeAPScheduler()
    svc = build_scheduler_service(
        session_factory=session_factory,
        settings=SchedulerSettings(enabled=True),
        scheduler=fake_scheduler,
        report_runner=FakeReportRunner(events=[]),
        batch_runner=FakeBatchRunner(results=[]),
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
        report_id = json.loads(run.result_summary)["report_id"]

        # A real report_mb row was produced, anchored to the schedule.
        report = s.get(ReportMb, report_id)
        assert report is not None
        assert report.status == "completed"
        assert report.schedule_id == "sch_mb"

        notifs = s.query(UserNotification).all()
        assert len(notifs) == 1
        assert notifs[0].type == "report_ready"
        assert notifs[0].department == "morning_briefing"

        sched = s.get(MbSchedule, "sch_mb")
        assert sched.last_run_at is not None

    await svc.shutdown()
    assert fake_scheduler.stopped is True
