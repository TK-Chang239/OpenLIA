"""Scheduler-facing service helpers.

``sweep_expired_reports`` is extracted from ``MaintenanceExecutor`` so it
can accept a ``bundle_dir`` argument and clean up on-disk bundle files when
reports are hard-deleted.  ``run_maintenance_once`` delegates the hard-delete
branch to this function.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from openlia_server.db.models.content import Report
from openlia_server.db.models.graph import GraphArtifactSummary

log = logging.getLogger(__name__)

UNSAVED_REPORT_RETENTION_DAYS_DEFAULT = 7


def sweep_expired_reports(
    *,
    session: Session,
    bundle_dir: Path | None = None,
) -> list[str]:
    """Hard-delete user-less orphan reports past the retention cutoff.

    Returns the list of deleted report IDs.  For each deleted report, also
    removes ``<bundle_dir>/<report_id>.json.gz`` when *bundle_dir* is given.
    """
    report_retention_days = int(
        os.environ.get(
            "OPENLIA_UNSAVED_REPORT_RETENTION_DAYS",
            UNSAVED_REPORT_RETENTION_DAYS_DEFAULT,
        )
    )
    report_cutoff = datetime.now(UTC) - timedelta(days=report_retention_days)

    orphan_ids: list[str] = list(
        session.execute(
            select(Report.id).where(
                Report.user_id.is_(None),
                Report.created_at < report_cutoff,
            )
        ).scalars()
    )

    if orphan_ids:
        session.execute(
            delete(GraphArtifactSummary).where(
                GraphArtifactSummary.artifact_kind == "report",
                GraphArtifactSummary.artifact_id.in_(orphan_ids),
            )
        )
        session.execute(delete(Report).where(Report.id.in_(orphan_ids)))

        if bundle_dir is not None:
            for report_id in orphan_ids:
                bundle_path = bundle_dir / f"{report_id}.json.gz"
                try:
                    bundle_path.unlink(missing_ok=True)
                except OSError:
                    log.warning("failed to delete bundle %s", bundle_path)

    return orphan_ids
