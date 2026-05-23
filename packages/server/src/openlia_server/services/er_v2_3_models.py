"""Service layer for v2.3 equity-research per-user model assignments.

Mirrors ``er_v2_models`` but writes to its own table. The slot inventory
is ``LLM_V23_SLOTS`` (the seven LLM-using v2.3 slots).
"""

from __future__ import annotations

from datetime import UTC, datetime

from openlia.llm.runtime.report_v2_3.slots import LLM_V23_SLOTS, V23Slot
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from openlia_server.db.models.er_v2_3_models import ErV23ModelAssignment


def get_assignments(session: Session, *, user_id: str) -> dict[str, str]:
    """Return the user's saved slot → model_id mapping (sparse)."""
    rows = session.execute(
        select(ErV23ModelAssignment).where(ErV23ModelAssignment.user_id == user_id)
    ).scalars()
    return {row.slot: row.model_id for row in rows}


def set_assignments(session: Session, *, user_id: str, mapping: dict[str, str]) -> dict[str, str]:
    """Replace the user's per-slot assignments with ``mapping``.

    Any slot absent from ``mapping`` is deleted; any slot present is
    upserted. Unknown slot names are rejected.
    """
    known = {s.value for s in V23Slot}
    unknown = sorted(set(mapping.keys()) - known)
    if unknown:
        raise ValueError(f"unknown slot(s): {unknown}")

    session.execute(delete(ErV23ModelAssignment).where(ErV23ModelAssignment.user_id == user_id))
    now = datetime.now(UTC)
    for slot, model_id in mapping.items():
        session.add(
            ErV23ModelAssignment(user_id=user_id, slot=slot, model_id=model_id, updated_at=now)
        )
    session.flush()
    return get_assignments(session, user_id=user_id)


def missing_slots(assignments: dict[str, str]) -> list[str]:
    """Return the LLM-using slots that aren't yet assigned."""
    return sorted(s.value for s in LLM_V23_SLOTS if s.value not in assignments)
