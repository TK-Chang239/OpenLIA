"""Job history + manual retry endpoints."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import JobRun
from openlia_server.middleware.auth import build_require_auth
from openlia_server.scheduler.registry import JobStatus
from openlia_server.scheduler.services import jobs as jobs_service


class JobRunOut(BaseModel):
    id: str
    job_type: str
    status: str
    attempt: int
    started_at: str | None
    finished_at: str | None
    result_summary: str | None
    error_message: str | None


class JobsHistoryOut(BaseModel):
    runs: list[JobRunOut]
    total: int


class RetryAck(BaseModel):
    run_id: str
    retry_scheduled: bool


def _serialize_run(run: JobRun) -> JobRunOut:
    return JobRunOut(
        id=run.id,
        job_type=run.job_type,
        status=run.status,
        attempt=run.attempt,
        started_at=run.started_at.isoformat() if run.started_at else None,
        finished_at=run.completed_at.isoformat() if run.completed_at else None,
        result_summary=run.result_summary,
        error_message=run.error_message,
    )


def build_jobs_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
) -> APIRouter:
    """Factory for /jobs/*. Binds the real auth dependency for the given mode."""
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    router = APIRouter(prefix="/jobs", tags=["jobs"])

    @router.get("/history", response_model=JobsHistoryOut)
    def get_history(
        request: Request,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
        user: User = require_auth,
    ) -> JobsHistoryOut:
        svc = request.app.state.scheduler
        with svc.session_factory() as session:
            runs = jobs_service.list_for_user(
                session=session,
                user_id=user.id,
                limit=limit,
                offset=offset,
            )
            total = jobs_service.count_for_user(session=session, user_id=user.id)
        return JobsHistoryOut(
            runs=[_serialize_run(r) for r in runs],
            total=total,
        )

    @router.post("/{run_id}/retry", response_model=RetryAck, status_code=202)
    async def retry_run(
        run_id: str,
        request: Request,
        user: User = require_auth,
    ) -> RetryAck:
        svc = request.app.state.scheduler
        with svc.session_factory() as session:
            run = session.get(JobRun, run_id)
            if run is None or run.user_id != user.id:
                raise HTTPException(status_code=404, detail="run not found")
            if run.status not in (JobStatus.FAILED.value, JobStatus.CANCELLED.value):
                raise HTTPException(
                    status_code=422,
                    detail="only failed or cancelled runs can be retried",
                )
        await svc.run_retry(run_id=run_id)
        return RetryAck(run_id=run_id, retry_scheduled=True)

    return router
