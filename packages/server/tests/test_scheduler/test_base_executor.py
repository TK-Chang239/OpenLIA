from __future__ import annotations

import asyncio
from typing import ClassVar

import pytest
from _scheduler_fakes import FakeSleep
from openlia.llm.exceptions import (
    AuthError,
    ModelNotConfiguredError,
    RateLimitError,
)
from openlia.llm.runtime.cancellation import CancellationToken
from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import JobRun, UserNotification
from openlia_server.scheduler.executors.base import (
    BaseExecutor,
    JobOutcome,
    NotificationSpec,
)
from openlia_server.scheduler.registry import (
    JobStatus,
    JobType,
    NotificationType,
)
from sqlalchemy.orm import Session


class _ScriptedExecutor(BaseExecutor):
    job_type: ClassVar[JobType] = JobType.MB_BRIEFING

    def __init__(self, *, script, **kw):
        super().__init__(**kw)
        self._script = list(script)
        self.calls: list[dict] = []

    async def _do_work(self, *, user_id, schedule_id, run_id, cancel_token):
        self.calls.append({"user_id": user_id, "schedule_id": schedule_id, "run_id": run_id})
        step = self._script.pop(0)
        if isinstance(step, BaseException):
            raise step
        return step


def _make_user(session: Session, uid: str = "u_1") -> None:
    session.add(
        User(
            id=uid,
            email=f"{uid}@e.com",
            display_name=f"u-{uid}",
            password_hash="h",
            is_admin=False,
            is_disabled=False,
        )
    )
    session.commit()


def _success() -> JobOutcome:
    return JobOutcome(
        result_summary={"report_id": "r_1"},
        notifications=[
            NotificationSpec(
                type=NotificationType.REPORT_READY,
                department="morning_briefing",
                message="ok",
            )
        ],
    )


@pytest.mark.asyncio
async def test_successful_first_try_writes_completed_row_and_notification(
    session_factory,
) -> None:
    with session_factory() as s:
        _make_user(s)
    sleep = FakeSleep()
    ex = _ScriptedExecutor(
        script=[_success()],
        session_factory=session_factory,
        sleep=sleep,
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="s_1")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.COMPLETED.value
        assert row.attempt == 1
        assert row.result_summary == '{"report_id": "r_1"}'
        notifs = s.query(UserNotification).all()
        assert len(notifs) == 1
        assert notifs[0].type == "report_ready"
        assert notifs[0].job_run_id == run_id
    assert sleep.calls == []


@pytest.mark.asyncio
async def test_transient_then_success_bumps_attempt_and_backs_off(
    session_factory,
) -> None:
    with session_factory() as s:
        _make_user(s)
    sleep = FakeSleep()
    ex = _ScriptedExecutor(
        script=[
            RateLimitError("429"),
            RateLimitError("429 again"),
            _success(),
        ],
        session_factory=session_factory,
        sleep=sleep,
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="s_1")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.COMPLETED.value
        assert row.attempt == 3
    assert sleep.calls == [30, 120]


@pytest.mark.asyncio
async def test_non_transient_error_fails_immediately_without_retry(
    session_factory,
) -> None:
    with session_factory() as s:
        _make_user(s)
    sleep = FakeSleep()
    ex = _ScriptedExecutor(
        script=[AuthError("bad key")],
        session_factory=session_factory,
        sleep=sleep,
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="s_1")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.FAILED.value
        assert "AuthError" in row.error_message
        notifs = s.query(UserNotification).all()
        assert len(notifs) == 1
        assert notifs[0].type == "job_failed"
        assert notifs[0].department == "morning_briefing"
    assert sleep.calls == []


@pytest.mark.asyncio
async def test_model_not_configured_fails_and_inserts_job_failed_notification(
    session_factory,
) -> None:
    with session_factory() as s:
        _make_user(s)
    ex = _ScriptedExecutor(
        script=[ModelNotConfiguredError(slot_kind="department", slot_id="secretary")],
        session_factory=session_factory,
        sleep=FakeSleep(),
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="s_1")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.FAILED.value
        notifs = s.query(UserNotification).all()
        assert notifs[0].type == "job_failed"
        assert "ModelNotConfigured" in notifs[0].message


@pytest.mark.asyncio
async def test_transient_failure_exhausts_retries_then_fails(
    session_factory,
) -> None:
    with session_factory() as s:
        _make_user(s)
    sleep = FakeSleep()
    ex = _ScriptedExecutor(
        script=[RateLimitError(str(i)) for i in range(4)],
        session_factory=session_factory,
        sleep=sleep,
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="s_1")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.FAILED.value
        assert row.attempt == 4
    assert sleep.calls == [30, 120, 480]


@pytest.mark.asyncio
async def test_cancel_before_start_short_circuits(session_factory) -> None:
    with session_factory() as s:
        _make_user(s)
    tok = CancellationToken()
    tok.cancel()
    ex = _ScriptedExecutor(
        script=[_success()],
        session_factory=session_factory,
        sleep=FakeSleep(),
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="s_1", cancel_token=tok)

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.CANCELLED.value
        assert ex.calls == []


@pytest.mark.asyncio
async def test_maintenance_style_skips_notifications_when_user_id_is_none(
    session_factory,
) -> None:
    ex = _ScriptedExecutor(
        script=[JobOutcome(result_summary={"pruned_sessions": 2}, notifications=[])],
        session_factory=session_factory,
        sleep=FakeSleep(),
    )
    ex.job_type = JobType.SYSTEM_MAINTENANCE  # type: ignore[misc]
    run_id = await ex.execute(user_id=None, schedule_id=None)

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.COMPLETED.value
        assert row.user_id is None
        assert s.query(UserNotification).count() == 0


@pytest.mark.asyncio
async def test_cancelled_error_raised_by_work_records_cancelled_and_reraises(
    session_factory,
) -> None:
    with session_factory() as s:
        _make_user(s)
    ex = _ScriptedExecutor(
        script=[asyncio.CancelledError()],
        session_factory=session_factory,
        sleep=FakeSleep(),
    )
    with pytest.raises(asyncio.CancelledError):
        await ex.execute(user_id="u_1", schedule_id="s_1")

    with session_factory() as s:
        row = s.query(JobRun).one()
        assert row.status == JobStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_retry_honors_cancel_token_between_attempts(session_factory) -> None:
    with session_factory() as s:
        _make_user(s)
    tok = CancellationToken()
    sleep_calls: list[float] = []

    async def cancelling_sleep(_: float) -> None:
        sleep_calls.append(_)
        tok.cancel()

    ex = _ScriptedExecutor(
        script=[RateLimitError("1"), _success()],
        session_factory=session_factory,
        sleep=cancelling_sleep,
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="s_1", cancel_token=tok)

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.CANCELLED.value
    assert sleep_calls == [30]


@pytest.mark.asyncio
async def test_retry_of_sets_pointer(session_factory) -> None:
    with session_factory() as s:
        _make_user(s)
    ex_first = _ScriptedExecutor(
        script=[AuthError("bad key")],
        session_factory=session_factory,
        sleep=FakeSleep(),
    )
    failed_id = await ex_first.execute(user_id="u_1", schedule_id="s_1")

    ex_retry = _ScriptedExecutor(
        script=[_success()],
        session_factory=session_factory,
        sleep=FakeSleep(),
    )
    retry_id = await ex_retry.execute(user_id="u_1", schedule_id="s_1", retry_of=failed_id)

    with session_factory() as s:
        retry_row = s.get(JobRun, retry_id)
        assert retry_row.retry_of == failed_id
        assert retry_row.status == JobStatus.COMPLETED.value
