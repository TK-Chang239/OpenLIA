"""Tests for the rewired MBBriefingExecutor (MB rework Phase 3).

The executor now runs the report_mb engine inline via
``mb_v2_run_service.run_to_completion``. These tests inject a fake run service
that records the ``build_run_request`` config it received and writes a real
``report_mb`` row (so the executor's persistence + last_run_at + notification
wiring is exercised against the real DB without touching an LLM provider).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest
from _scheduler_fakes import FakeSleep
from openlia.llm.runtime.report_mb import (
    BriefingContext,
    EnabledConnectors,
    Language,
    ReportLength,
    RunRequest,
    RunResult,
)
from openlia.llm.runtime.report_mb.default_template import build_default_template
from openlia_server.db.models.auth import User
from openlia_server.db.models.report_mb import ReportMb
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
            template_id="mb_default",
            instructions_id=None,
            enabled_connectors={"provider_ids": ["eodhd"], "web_search": True},
            provider_kind="anthropic",
            model="claude-sonnet-4-6",
            language="en",
            length="normal",
            reasoning_effort="high",
            web_search=True,
            created_at=datetime.now(UTC),
            last_run_at=None,
        )
    )
    session.commit()


def _make_request() -> RunRequest:
    return RunRequest(
        subject="Pre-Market - 2026-06-02",
        template=build_default_template(),
        language=Language.EN,
        length=ReportLength.NORMAL,
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        reasoning_effort=None,
        enabled_connectors=EnabledConnectors(),
        briefing_context=BriefingContext(run_date="2026-06-02", schedule_label="Pre-Market"),
        instructions=None,
    )


@dataclass
class FakeRunService:
    """Stub of mb_v2_run_service: records build_run_request kwargs, writes a
    real report_mb row in run_to_completion, returns (report_id, RunResult)."""

    request: RunRequest
    status: str = "completed"
    build_calls: list[dict[str, Any]] = field(default_factory=list)
    run_calls: list[dict[str, Any]] = field(default_factory=list)

    def build_run_request(self, db, **kwargs) -> RunRequest:
        self.build_calls.append(kwargs)
        return self.request

    async def run_to_completion(
        self,
        db,
        *,
        user_id: str,
        request: RunRequest,
        trigger_kind: str = "scheduled",
        schedule_id: str | None = None,
        instructions_id: str | None = None,
        cancel_token: Any = None,
    ) -> tuple[str, RunResult]:
        self.run_calls.append(
            {
                "user_id": user_id,
                "trigger_kind": trigger_kind,
                "schedule_id": schedule_id,
                "instructions_id": instructions_id,
                "cancel_token": cancel_token,
            }
        )
        report_id = str(uuid.uuid4())
        db.add(
            ReportMb(
                id=report_id,
                user_id=user_id,
                subject=request.subject,
                trigger_kind=trigger_kind,
                schedule_id=schedule_id,
                template_id=request.template.template_id,
                instructions_id=instructions_id,
                language=request.language.value,
                length=request.length.value,
                provider_kind=request.provider_kind,
                model=request.model,
                status=self.status,
                error_message=None,
                created_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                cover_json=None,
                reasoning_effort=None,
            )
        )
        db.flush()
        result = RunResult(
            status=self.status,
            subject=request.subject,
            template_id=request.template.template_id,
            message="",
            sections=[],
            charts=[],
            citations=[],
            cover=None,
        )
        return report_id, result


@pytest.mark.asyncio
async def test_mb_executor_produces_report_sets_last_run_and_notifies(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed(s)

    run_service = FakeRunService(request=_make_request())
    ex = MBBriefingExecutor(
        session_factory=session_factory,
        run_service=run_service,
        sleep=FakeSleep(),
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="sch_mb")

    with session_factory() as s:
        job = s.get(JobRun, run_id)
        assert job.status == JobStatus.COMPLETED.value
        import json

        report_id = json.loads(job.result_summary)["report_id"]

        # A real report_mb row was produced, anchored to the firing schedule.
        report = s.get(ReportMb, report_id)
        assert report is not None
        assert report.status == "completed"
        assert report.trigger_kind == "scheduled"
        assert report.schedule_id == "sch_mb"

        # last_run_at stamped on the schedule.
        sched = s.get(MbSchedule, "sch_mb")
        assert sched.last_run_at is not None

        # One REPORT_READY notification carrying the schedule label.
        notifs = s.query(UserNotification).all()
        assert len(notifs) == 1
        assert notifs[0].type == "report_ready"
        assert notifs[0].department == "morning_briefing"
        assert "Pre-Market" in notifs[0].message

    # The executor fed the schedule's bound config into build_run_request.
    assert len(run_service.build_calls) == 1
    cfg = run_service.build_calls[0]
    assert cfg["template_id"] == "mb_default"
    assert cfg["provider_kind"] == "anthropic"
    assert cfg["model"] == "claude-sonnet-4-6"
    assert cfg["reasoning_effort"] == "high"
    assert cfg["enabled_connectors"] == {"provider_ids": ["eodhd"], "web_search": True}
    assert cfg["schedule_label"] == "Pre-Market"
    assert cfg["time_label"] == "07:00"
    assert cfg["timezone"] == "UTC"
    assert run_service.run_calls[0]["schedule_id"] == "sch_mb"


def test_cancel_bridge_reflects_source_token() -> None:
    from openlia.llm.runtime.cancellation import CancellationToken
    from openlia_server.scheduler.executors.mb import _CancelBridge

    source = CancellationToken()
    bridge = _CancelBridge(source)
    # ``cancelled`` is a property (the engine polls it without calling),
    # delegating to the scheduler token's ``is_cancelled`` property.
    assert bridge.cancelled is False
    source.cancel()
    assert bridge.cancelled is True


@pytest.mark.asyncio
async def test_mb_executor_forwards_cancellation_to_engine(session_factory) -> None:
    from openlia.llm.runtime.cancellation import CancellationToken

    with session_factory() as s:
        _seed(s)

    run_service = FakeRunService(request=_make_request())
    ex = MBBriefingExecutor(
        session_factory=session_factory,
        run_service=run_service,
        sleep=FakeSleep(),
    )
    token = CancellationToken()
    await ex.execute(user_id="u_1", schedule_id="sch_mb", cancel_token=token)

    # The executor bridged its scheduler CancellationToken into a report_mb
    # CancelToken and forwarded it to the engine run (so graceful-shutdown
    # cancels actually reach the LLM loop).
    forwarded = run_service.run_calls[0]["cancel_token"]
    assert forwarded is not None
    assert forwarded.cancelled is False
    token.cancel()
    assert forwarded.cancelled is True


@pytest.mark.asyncio
async def test_mb_executor_uses_time_label_when_no_schedule_label(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed(s)
        sched = s.get(MbSchedule, "sch_mb")
        sched.label = None
        s.commit()

    run_service = FakeRunService(request=_make_request())
    ex = MBBriefingExecutor(
        session_factory=session_factory,
        run_service=run_service,
        sleep=FakeSleep(),
    )
    await ex.execute(user_id="u_1", schedule_id="sch_mb")

    with session_factory() as s:
        notifs = s.query(UserNotification).all()
        assert len(notifs) == 1
        assert "07:00" in notifs[0].message
