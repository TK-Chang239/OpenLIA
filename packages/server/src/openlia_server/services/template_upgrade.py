"""Override-wins template install / upgrade flow (Phase 11).

When a catalog install or `sync_template_specs` would update a row the
user has manually re-resolved (i.e. ``resolution_mode != 'catalog'``):

  - Preserve the override row as-is.
  - Stash the would-be-new spec in ``pending_default_change`` so the
    admin panel can surface a non-blocking notice.

`revert_to_default` swaps the override out for the pending spec and
clears the notice.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from openlia_server.db.models.connectors import RunnerCallableSpec


def apply_template_with_override_protection(
    session: Session,
    *,
    connector_id: str,
    department_id: str,
    need_id: str,
    template_spec: dict[str, Any],
    access_mode: str,
) -> RunnerCallableSpec:
    """Install/upgrade a catalog spec for ``(department_id, need_id)``.

    If the existing row is a user override, record the would-be-new
    spec in ``pending_default_change`` and leave the override intact.
    Otherwise insert / replace the row outright (catalog wins on
    catalog rows).
    """
    existing = (
        session.query(RunnerCallableSpec)
        .filter(
            RunnerCallableSpec.department_id == department_id,
            RunnerCallableSpec.need_id == need_id,
        )
        .one_or_none()
    )
    if existing is not None and existing.resolution_mode != "catalog":
        existing.pending_default_change = {
            "spec": template_spec,
            "access_mode": access_mode,
            "connector_id": connector_id,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        session.commit()
        return existing

    if existing is None:
        row = RunnerCallableSpec(
            id=str(uuid4()),
            department_id=department_id,
            need_id=need_id,
            connector_id=connector_id,
            access_mode=access_mode,
            spec=template_spec,
            resolution_mode="catalog",
            manually_overridden=False,
        )
        session.add(row)
        session.commit()
        return row

    existing.spec = template_spec
    existing.access_mode = access_mode
    existing.connector_id = connector_id
    existing.resolution_mode = "catalog"
    existing.pending_default_change = None
    session.commit()
    return existing


def revert_to_default(session: Session, *, department_id: str, need_id: str) -> RunnerCallableSpec:
    """Apply the row's ``pending_default_change`` and clear the notice."""
    row = (
        session.query(RunnerCallableSpec)
        .filter(
            RunnerCallableSpec.department_id == department_id,
            RunnerCallableSpec.need_id == need_id,
        )
        .one_or_none()
    )
    if row is None:
        raise KeyError(f"no spec for ({department_id!r}, {need_id!r})")
    pending = row.pending_default_change
    if not pending:
        return row
    row.spec = pending["spec"]
    row.access_mode = pending["access_mode"]
    row.connector_id = pending["connector_id"]
    row.resolution_mode = "catalog"
    row.manually_overridden = False
    row.pending_default_change = None
    session.commit()
    return row


__all__ = [
    "apply_template_with_override_protection",
    "revert_to_default",
]
