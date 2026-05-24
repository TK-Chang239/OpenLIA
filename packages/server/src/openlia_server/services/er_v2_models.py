"""Service layer for v2.2 equity-research per-user model assignments."""

from __future__ import annotations

from datetime import UTC, datetime

from openlia.llm.runtime.report_v2.slots import REQUIRED_V2_SLOTS, V2Slot
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from openlia_server.db.models.er_v2_models import ErV2ModelAssignment


def get_assignments(session: Session, *, user_id: str) -> dict[str, str]:
    """Return the user's saved slot → model_id mapping (sparse)."""
    rows = session.execute(
        select(ErV2ModelAssignment).where(ErV2ModelAssignment.user_id == user_id)
    ).scalars()
    return {row.slot: row.model_id for row in rows}


def set_assignments(
    session: Session, *, user_id: str, mapping: dict[str, str]
) -> dict[str, str]:
    """Replace the user's per-slot assignments with `mapping`.

    Any slot absent from `mapping` is deleted; any slot present is upserted.
    Unknown slot names are rejected.
    """
    known = {s.value for s in V2Slot}
    unknown = sorted(set(mapping.keys()) - known)
    if unknown:
        raise ValueError(f"unknown slot(s): {unknown}")

    session.execute(
        delete(ErV2ModelAssignment).where(ErV2ModelAssignment.user_id == user_id)
    )
    now = datetime.now(UTC)
    for slot, model_id in mapping.items():
        session.add(
            ErV2ModelAssignment(
                user_id=user_id, slot=slot, model_id=model_id, updated_at=now
            )
        )
    session.flush()
    return get_assignments(session, user_id=user_id)


def missing_slots(assignments: dict[str, str]) -> list[str]:
    """Return the slots required by the pipeline that aren't assigned."""
    return sorted(s.value for s in REQUIRED_V2_SLOTS if s.value not in assignments)
