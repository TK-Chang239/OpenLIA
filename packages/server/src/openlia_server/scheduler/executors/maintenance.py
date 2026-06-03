"""System maintenance job: nightly pruning sweep. DB-only, no LLM,
no notifications. Also exposes run_maintenance_once(session) so Plan 7
CLI can invoke the same sweep synchronously."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import ClassVar

from openlia.llm.runtime.cancellation import CancellationToken
from sqlalchemy import delete, exists, select, update
from sqlalchemy.orm import Session

from openlia_server.db.models.auth import PasswordResetRequest
from openlia_server.db.models.auth import Session as AuthSession
from openlia_server.db.models.content import RepoItem, Report
from openlia_server.db.models.dashboard import RsSnapshot
from openlia_server.db.models.pipeline_runs import PipelineRun
from openlia_server.db.models.safety import LiaGuardrailEvent
from openlia_server.db.models.scheduler import JobRun, UserNotification
from openlia_server.scheduler.executors.base import BaseExecutor, JobOutcome
from openlia_server.scheduler.registry import JobStatus, JobType
from openlia_server.services.reports import tombstone_report
from openlia_server.services.scheduler import sweep_expired_reports

SESSIONS_RETENTION_DAYS = 7
PASSWORD_RESET_RETENTION_DAYS = 90
RS_SNAPSHOT_RETENTION_DAYS = 90
NOTIFICATION_RETENTION_DAYS = 30
JOB_RUN_RETENTION_DAYS = 90
LIA_GUARDRAIL_LOG_RETENTION_DAYS_DEFAULT = 365
UNSAVED_REPORT_RETENTION_DAYS_DEFAULT = 7


def run_maintenance_once(session: Session) -> dict[str, int]:
    now = datetime.now(UTC)

    sessions_deleted = (
        session.execute(
            delete(AuthSession).where(
                AuthSession.expires_at < now - timedelta(days=SESSIONS_RETENTION_DAYS)
            )
        ).rowcount
        or 0
    )

    password_resets_expired = (
        session.execute(
            update(PasswordResetRequest)
            .where(
                PasswordResetRequest.status == "approved",
                PasswordResetRequest.expires_at < now,
            )
            .values(status="expired")
            .execution_options(synchronize_session="fetch")
        ).rowcount
        or 0
    )

    password_resets_deleted = (
        session.execute(
            delete(PasswordResetRequest).where(
                PasswordResetRequest.requested_at
                < now - timedelta(days=PASSWORD_RESET_RETENTION_DAYS)
            )
        ).rowcount
        or 0
    )

    rs_snapshots_deleted = (
        session.execute(
            delete(RsSnapshot).where(
                RsSnapshot.captured_at < now - timedelta(days=RS_SNAPSHOT_RETENTION_DAYS)
            )
        ).rowcount
        or 0
    )

    notifications_deleted = (
        session.execute(
            delete(UserNotification).where(
                UserNotification.created_at < now - timedelta(days=NOTIFICATION_RETENTION_DAYS)
            )
        ).rowcount
        or 0
    )

    job_runs_deleted = (
        session.execute(
            delete(JobRun).where(
                JobRun.status.in_([JobStatus.COMPLETED.value, JobStatus.CANCELLED.value]),
                JobRun.started_at < now - timedelta(days=JOB_RUN_RETENTION_DAYS),
            )
        ).rowcount
        or 0
    )

    guardrail_retention_days = int(
        os.environ.get(
            "LIA_GUARDRAIL_LOG_RETENTION_DAYS",
            LIA_GUARDRAIL_LOG_RETENTION_DAYS_DEFAULT,
        )
    )
    lia_guardrail_events_deleted = (
        session.execute(
            delete(LiaGuardrailEvent).where(
                LiaGuardrailEvent.created_at < now - timedelta(days=guardrail_retention_days)
            )
        ).rowcount
        or 0
    )

    # Unsaved-report retention: tombstone owned reports past the cutoff
    # with no repo_items pointer; hard-delete user-less orphans separately
    # (no chat history to anchor, no user to view).
    report_retention_days = int(
        os.environ.get(
            "OPENLIA_UNSAVED_REPORT_RETENTION_DAYS",
            UNSAVED_REPORT_RETENTION_DAYS_DEFAULT,
        )
    )
    report_cutoff = now - timedelta(days=report_retention_days)

    candidate_ids = list(
        session.execute(
            select(Report.id).where(
                Report.user_id.is_not(None),
                Report.expired_at.is_(None),
                Report.created_at < report_cutoff,
                ~exists().where(RepoItem.report_id == Report.id),
            )
        ).scalars()
    )
    reports_tombstoned = 0
    for rid in candidate_ids:
        if tombstone_report(session, report_id=rid):
            reports_tombstoned += 1

    bundle_dir_env = os.environ.get("OPENLIA_REPORT_BUNDLE_DIR")
    bundle_dir: Path | None = (
        Path(bundle_dir_env) if bundle_dir_env else Path.home() / ".openlia" / "report_bundles"
    )
    deleted_ids = sweep_expired_reports(session=session, bundle_dir=bundle_dir)
    reports_hard_deleted = len(deleted_ids)

    # v2.2 pipeline_runs retention: same shape as v1. Tombstone (set
    # expired_at) any COMPLETED/DEGRADED run past the cutoff that has
    # no repo_items bookmark and no soft-delete yet. The card flips to
    # the v1-shared tombstone state via the v2 ReportCard's expiredAt
    # prop on the next reload.
    v2_candidate_ids = list(
        session.execute(
            select(PipelineRun.id).where(
                PipelineRun.state.in_(("COMPLETED", "DEGRADED")),
                PipelineRun.expired_at.is_(None),
                PipelineRun.deleted_at.is_(None),
                PipelineRun.created_at < report_cutoff,
                ~exists().where(RepoItem.pipeline_run_id == PipelineRun.id),
            )
        ).scalars()
    )
    v2_runs_tombstoned = 0
    if v2_candidate_ids:
        session.execute(
            update(PipelineRun)
            .where(PipelineRun.id.in_(v2_candidate_ids))
            .values(expired_at=now, updated_at=now)
        )
        v2_runs_tombstoned = len(v2_candidate_ids)

    return {
        "sessions_deleted": int(sessions_deleted),
        "password_resets_expired": int(password_resets_expired),
        "password_resets_deleted": int(password_resets_deleted),
        "rs_snapshots_deleted": int(rs_snapshots_deleted),
        "notifications_deleted": int(notifications_deleted),
        "job_runs_deleted": int(job_runs_deleted),
        "lia_guardrail_events_deleted": int(lia_guardrail_events_deleted),
        "reports_tombstoned": int(reports_tombstoned),
        "reports_hard_deleted": int(reports_hard_deleted),
        "v2_runs_tombstoned": int(v2_runs_tombstoned),
    }


class MaintenanceExecutor(BaseExecutor):
    job_type: ClassVar[JobType] = JobType.SYSTEM_MAINTENANCE

    async def _do_work(
        self,
        *,
        user_id: str | None,
        schedule_id: str | None,
        run_id: str,
        cancel_token: CancellationToken | None,
    ) -> JobOutcome:
        session = self._session_factory()
        try:
            summary = run_maintenance_once(session)
            session.commit()
        finally:
            session.close()
        return JobOutcome(result_summary=summary, notifications=[])
