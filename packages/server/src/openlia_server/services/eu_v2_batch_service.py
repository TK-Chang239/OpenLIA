"""EU v2 batch dispatch: route scheduled runs through the provider Batch API.

Two layers:

  - ``run_batch_group`` drives a group of pre-built ``EuRunState``s (one
    ``(provider_kind, model)``) through a ``BatchOrchestrator``, persisting
    each run's outcome into the ``report_eu`` artifact tables and tracking
    the job in ``eu_v2_batch_job`` / ``eu_v2_batch_run``. Spawned as a
    background task so the dispatcher returns promptly.
  - ``dispatch_due_batches`` partitions a set of due schedule rows: the
    batch-eligible ones (user ``batch_enabled`` + a provider with a batch
    transport) are grouped, materialized into report rows + run states, and
    handed to ``run_batch_group``. It returns the ids it handled so the
    caller routes the rest through the existing sync path.

Restart resume is out of scope here (a server restart orphans an in-flight
batch job; ``mark_orphaned_batch_jobs_failed`` cleans those at startup).
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any

from openlia.llm.batch_factory import build_batch_transport
from openlia.llm.batch_transport import BatchTransport, supports_batch
from openlia.llm.runtime.batch_orchestrator import BatchOrchestrator
from openlia.llm.runtime.report_eu.run_state import EuRunState
from openlia.llm.types import ProviderCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.report_eu import EuV2BatchJob, EuV2BatchRun, ReportEu
from openlia_server.services import eu_v2_settings
from openlia_server.services.eu_v2_dispatch import mark_reported, select_due_rows
from openlia_server.services.eu_v2_run_service import (
    build_eu_dispatcher,
    build_run_request,
    insert_report_row,
    persist_result,
)
from openlia_server.services.eu_v2_wiring import build_eu_v2_transports, resolve_eodhd_api_key

log = logging.getLogger(__name__)

SessionFactory = Callable[[], DBSession]
SpawnFn = Callable[[Any], Any]

# Env-tunable poll cadence + wall-clock ceiling for a batch group.
_POLL_INTERVAL_S = float(os.environ.get("OPENLIA_BATCH_POLL_INTERVAL_SECONDS", "120"))
_MAX_WAIT_S = float(os.environ.get("OPENLIA_BATCH_MAX_WAIT_HOURS", "24")) * 3600

# Provider -> env vars holding the API key (mirrors report_eu session.py).
_ENV_VAR_BY_PROVIDER: dict[str, tuple[str, ...]] = {
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
}

# Strong refs to in-flight orchestrator tasks (asyncio holds only weak refs).
_BACKGROUND_TASKS: set[asyncio.Task] = set()


def is_batch_eligible(settings: eu_v2_settings.EuSettingsDTO) -> bool:
    """A user's scheduled runs go through batch when they opted in AND the
    selected provider has a wired batch transport."""
    return settings.batch_enabled and supports_batch(settings.provider_kind, settings.model)


def _resolve_credentials(provider_kind: str) -> ProviderCredentials:
    for env_var in _ENV_VAR_BY_PROVIDER.get(provider_kind, ()):
        api_key = os.environ.get(env_var)
        if api_key:
            return ProviderCredentials(api_key=api_key, base_url=None, env_var_name=env_var)
    return ProviderCredentials(api_key=None, base_url=None, env_var_name=None)


def run_batch_group(
    *,
    session_factory: SessionFactory,
    provider_kind: str,
    model: str,
    runs: list[tuple[str, EuRunState]],
    transport: BatchTransport,
    spawn: SpawnFn = asyncio.create_task,
    poll_interval_s: float | None = None,
    max_wait_s: float | None = None,
) -> str:
    """Persist a batch job + run rows, drive the orchestrator in the
    background, and return the new ``eu_v2_batch_job`` id.

    ``runs`` is ``[(report_id, state)]`` with the ``report_eu`` rows already
    inserted (status ``running``) and each ``state.custom_id == report_id``.
    """
    if not runs:
        raise ValueError("run_batch_group called with no runs")
    poll = _POLL_INTERVAL_S if poll_interval_s is None else poll_interval_s
    max_wait = _MAX_WAIT_S if max_wait_s is None else max_wait_s

    job_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    with session_factory() as db:
        db.add(
            EuV2BatchJob(
                id=job_id,
                provider_kind=provider_kind,
                model=model,
                status="submitted",
                turn_index=0,
                created_at=now,
                updated_at=now,
            )
        )
        for report_id, state in runs:
            db.add(
                EuV2BatchRun(
                    id=str(uuid.uuid4()),
                    batch_job_id=job_id,
                    report_id=report_id,
                    custom_id=state.custom_id,
                    status="active",
                    updated_at=now,
                )
            )
        db.commit()

    def _on_turn_persisted(batch_id: str, active: dict[str, Any]) -> None:
        del active
        with session_factory() as db:
            job = db.get(EuV2BatchJob, job_id)
            if job is not None:
                job.provider_batch_id = batch_id
                job.turn_index = (job.turn_index or 0) + 1
                job.status = "polling"
                job.updated_at = datetime.now(UTC)
                db.commit()

    def _on_run_complete(custom_id: str, result: Any) -> None:
        _persist_run_outcome(session_factory, report_id=custom_id, result=result)

    def _on_run_failed(custom_id: str, message: str) -> None:
        _fail_run(session_factory, report_id=custom_id, message=message)

    orchestrator = BatchOrchestrator(
        transport=transport,
        runs=[state for _, state in runs],
        poll_interval_s=poll,
        max_wait_s=max_wait,
        on_turn_persisted=_on_turn_persisted,
        on_run_complete=_on_run_complete,
        on_run_failed=_on_run_failed,
    )

    async def _drive() -> None:
        try:
            await orchestrator.run()
        except Exception:
            log.exception("EU v2 batch job %s crashed", job_id)
        finally:
            with session_factory() as db:
                job = db.get(EuV2BatchJob, job_id)
                if job is not None:
                    job.status = "completed"
                    job.updated_at = datetime.now(UTC)
                    db.commit()

    task = spawn(_drive())
    if isinstance(task, asyncio.Task):
        _BACKGROUND_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_TASKS.discard)
    return job_id


def dispatch_due_batches(
    *,
    session: DBSession,
    session_factory: SessionFactory,
    now: datetime,
    due_rows: Iterable[Any] | None = None,
    transport_factory: Callable[..., BatchTransport | None] = build_batch_transport,
    transports: Any = None,
    spawn: SpawnFn = asyncio.create_task,
) -> set[str]:
    """Dispatch every batch-eligible due schedule row; return handled row ids.

    Groups eligible rows by ``(provider_kind, model)``, materializes each
    into a ``report_eu`` row + ``EuRunState``, marks the schedule row
    reported, and hands each group to ``run_batch_group``. Rows whose user
    is not batch-eligible are left untouched for the sync path.
    """
    rows = list(due_rows) if due_rows is not None else list(select_due_rows(session, now=now))
    groups: dict[tuple[str, str], list[tuple[Any, Any]]] = {}
    for row in rows:
        settings = eu_v2_settings.get_settings(session, user_id=row.user_id)
        if not is_batch_eligible(settings):
            continue
        try:
            request = build_run_request(
                session,
                user_id=row.user_id,
                ticker=row.ticker,
                trigger_kind="scheduled",
                fiscal_period=None,
                report_date=row.fiscal_date,
                release_timing=row.release_timing,
                eps_estimate=row.eps_estimate,
                revenue_estimate=row.revenue_estimate,
            )
        except Exception:
            log.exception("EU v2 batch: failed to build request for schedule row %s", row.id)
            continue
        groups.setdefault((request.provider_kind, request.model), []).append((row, request))

    if not groups:
        return set()

    if transports is None:
        transports = build_eu_v2_transports(api_key=resolve_eodhd_api_key(session))
    if transports is None:
        log.warning("EU v2 batch: EODHD transports unavailable; deferring to the sync path")
        return set()

    handled: set[str] = set()
    for (provider_kind, model), entries in groups.items():
        transport = transport_factory(
            provider_kind=provider_kind,
            credentials=_resolve_credentials(provider_kind),
            model=model,
        )
        if transport is None:
            # supports_batch said yes but no transport built — leave for sync.
            continue
        runs: list[tuple[str, EuRunState]] = []
        for row, request in entries:
            report_id = insert_report_row(
                session, user_id=row.user_id, request=request, trigger_kind="scheduled"
            )
            dispatcher = build_eu_dispatcher(
                session, enabled_provider_ids=request.enabled_connectors.provider_ids
            )
            state = EuRunState.from_request(
                request,
                transports=transports,
                dispatcher=dispatcher,
                custom_id=report_id,
            )
            runs.append((report_id, state))
            mark_reported(session, row_id=row.id, report_id=report_id)
            handled.add(row.id)
        session.commit()
        run_batch_group(
            session_factory=session_factory,
            provider_kind=provider_kind,
            model=model,
            runs=runs,
            transport=transport,
            spawn=spawn,
        )
    return handled


def mark_orphaned_batch_jobs_failed(*, db: DBSession) -> int:
    """Flip non-terminal batch jobs (and their active runs / running reports)
    to failed. Call at startup: an in-flight batch from a prior process can't
    be resumed yet, so its reports must not hang in ``running`` forever."""
    now = datetime.now(UTC)
    jobs = list(
        db.execute(
            select(EuV2BatchJob).where(EuV2BatchJob.status.in_(("submitted", "polling")))
        ).scalars()
    )
    for job in jobs:
        job.status = "failed"
        job.updated_at = now
        runs = list(
            db.execute(
                select(EuV2BatchRun).where(EuV2BatchRun.batch_job_id == job.id)
            ).scalars()
        )
        for run in runs:
            if run.status != "active":
                continue
            run.status = "failed"
            run.updated_at = now
            report = db.get(ReportEu, run.report_id)
            if report is not None and report.status == "running":
                report.status = "failed"
                report.error_message = "batch interrupted by server restart"
                report.completed_at = now
    db.commit()
    return len(jobs)


def _persist_run_outcome(session_factory: SessionFactory, *, report_id: str, result: Any) -> None:
    with session_factory() as db:
        row = db.get(ReportEu, report_id)
        if row is None:
            log.warning("EU v2 batch outcome for missing report %s", report_id)
            return
        persist_result(db, report_id=report_id, result=result)
        row.status = result.status
        row.error_message = result.message or None
        row.completed_at = datetime.now(UTC)
        _mark_batch_run(db, report_id=report_id, status="completed")
        db.commit()


def _fail_run(session_factory: SessionFactory, *, report_id: str, message: str) -> None:
    with session_factory() as db:
        row = db.get(ReportEu, report_id)
        if row is None:
            log.warning("EU v2 batch failure for missing report %s", report_id)
            return
        row.status = "failed"
        row.error_message = message
        row.completed_at = datetime.now(UTC)
        _mark_batch_run(db, report_id=report_id, status="failed")
        db.commit()


def _mark_batch_run(db: DBSession, *, report_id: str, status: str) -> None:
    run = db.execute(
        select(EuV2BatchRun).where(EuV2BatchRun.report_id == report_id)
    ).scalars().first()
    if run is not None:
        run.status = status
        run.updated_at = datetime.now(UTC)


__all__ = [
    "dispatch_due_batches",
    "is_batch_eligible",
    "mark_orphaned_batch_jobs_failed",
    "run_batch_group",
]
