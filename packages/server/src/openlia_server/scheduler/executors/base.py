"""Common job lifecycle: open a job_runs row, run the subclass's _do_work
with retry-and-backoff, close the row, insert notifications."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, ClassVar

from openlia.llm.exceptions import LLMProviderError, is_transient
from openlia.llm.runtime.cancellation import CancellationToken
from sqlalchemy.orm import Session

from openlia_server.scheduler.registry import (
    JobType,
    NotificationType,
    department_for_job_type,
)
from openlia_server.scheduler.services import jobs as jobs_svc
from openlia_server.scheduler.services import notifications as notif_svc

DEFAULT_BACKOFF_SECONDS: tuple[int, ...] = (30, 120, 480)


@dataclass(frozen=True)
class NotificationSpec:
    type: NotificationType
    department: str
    message: str


@dataclass(frozen=True)
class JobOutcome:
    result_summary: dict[str, Any]
    notifications: list[NotificationSpec]


SessionFactory = Callable[[], Session]
AsyncSleep = Callable[[float], Awaitable[None]]


class BaseExecutor:
    """Abstract job executor. Subclasses set `job_type` and implement
    `_do_work`. Safe to instantiate directly only in tests."""

    job_type: ClassVar[JobType]

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        sleep: AsyncSleep | None = None,
        backoff_seconds: tuple[int, ...] = DEFAULT_BACKOFF_SECONDS,
    ) -> None:
        self._session_factory = session_factory
        self._sleep = sleep if sleep is not None else asyncio.sleep
        self._backoff_seconds = backoff_seconds

    async def execute(
        self,
        *,
        user_id: str | None,
        schedule_id: str | None,
        cancel_token: CancellationToken | None = None,
        retry_of: str | None = None,
        run_id: str | None = None,
    ) -> str:
        # If the caller pre-allocated a job_runs row (e.g. an HTTP route that
        # needs a real id to return synchronously), reuse it; otherwise open
        # a fresh one. Either way the executor owns transition to terminal
        # states (completed/failed/cancelled).
        if run_id is None:
            run_id = self._start_run(user_id=user_id, schedule_id=schedule_id, retry_of=retry_of)

        if cancel_token is not None and cancel_token.is_cancelled:
            self._cancel(run_id, "Cancelled before execution")
            return run_id

        attempts_remaining = len(self._backoff_seconds)
        last_error_msg: str | None = None

        for attempt_index in range(attempts_remaining + 1):
            try:
                outcome = await self._do_work(
                    user_id=user_id,
                    schedule_id=schedule_id,
                    run_id=run_id,
                    cancel_token=cancel_token,
                )
            except asyncio.CancelledError:
                self._cancel(run_id, "Job cancelled")
                raise
            except LLMProviderError as exc:
                last_error_msg = f"{type(exc).__name__}: {exc!s}"
                if is_transient(exc) and attempt_index < attempts_remaining:
                    self._bump_attempt(run_id, last_error_msg)
                    await self._sleep(self._backoff_seconds[attempt_index])
                    if cancel_token is not None and cancel_token.is_cancelled:
                        self._cancel(run_id, "Cancelled between retries")
                        return run_id
                    continue
                break
            except Exception as exc:
                last_error_msg = f"{type(exc).__name__}: {exc!s}"
                break
            else:
                self._complete(run_id=run_id, user_id=user_id, outcome=outcome)
                return run_id

        assert last_error_msg is not None
        self._fail(run_id=run_id, user_id=user_id, error_message=last_error_msg)
        return run_id

    async def _do_work(
        self,
        *,
        user_id: str | None,
        schedule_id: str | None,
        run_id: str,
        cancel_token: CancellationToken | None,
    ) -> JobOutcome:
        raise NotImplementedError

    def _start_run(
        self, *, user_id: str | None, schedule_id: str | None, retry_of: str | None
    ) -> str:
        with self._session_factory() as session:
            run_id = jobs_svc.start_run(
                session,
                user_id=user_id,
                job_type=self.job_type,
                schedule_id=schedule_id,
                retry_of=retry_of,
            )
            session.commit()
            return run_id

    def _bump_attempt(self, run_id: str, error_message: str) -> None:
        with self._session_factory() as session:
            jobs_svc.bump_attempt(session, run_id, error_message=error_message)
            session.commit()

    def _cancel(self, run_id: str, error_message: str) -> None:
        with self._session_factory() as session:
            jobs_svc.mark_cancelled(session, run_id, error_message=error_message)
            session.commit()

    def _complete(self, *, run_id: str, user_id: str | None, outcome: JobOutcome) -> None:
        with self._session_factory() as session:
            jobs_svc.mark_completed(
                session,
                run_id,
                result_summary=json.dumps(outcome.result_summary),
            )
            if user_id is not None:
                for n in outcome.notifications:
                    notif_svc.insert(
                        session,
                        user_id=user_id,
                        type=n.type,
                        department=n.department,
                        message=n.message,
                        job_run_id=run_id,
                    )
            session.commit()

    def _fail(self, *, run_id: str, user_id: str | None, error_message: str) -> None:
        with self._session_factory() as session:
            jobs_svc.mark_failed(session, run_id, error_message=error_message)
            if user_id is not None:
                notif_svc.insert(
                    session,
                    user_id=user_id,
                    type=NotificationType.JOB_FAILED,
                    department=department_for_job_type(self.job_type),
                    message=error_message,
                    job_run_id=run_id,
                )
            session.commit()
