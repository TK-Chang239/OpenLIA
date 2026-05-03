"""Append-only writer + filtering reader for `lia_guardrail_events`."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from openlia.safety.output_moderation import ActionTier, ModerationMatch
from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.safety import LiaGuardrailEvent


def record_tripwire_match(
    db: Session,
    *,
    session_id: str,
    user_id: str | None,
    department_id: str,
    match: ModerationMatch,
    user_input_hash: str,
    response_excerpt: str,
    model_ref: str | None,
) -> LiaGuardrailEvent:
    row = LiaGuardrailEvent(
        id=str(uuid.uuid4()),
        session_id=session_id,
        user_id=user_id,
        department_id=department_id,
        event_type="tripwire_flag",
        category=match.category,
        action_taken=str(match.action),
        user_input_hash=user_input_hash,
        response_excerpt=response_excerpt[:500],
        tripwire_pattern=match.pattern,
        model_ref=model_ref,
    )
    db.add(row)
    return row


def record_persona_refusal(
    db: Session,
    *,
    session_id: str,
    user_id: str | None,
    department_id: str,
    clause_id: str,
    user_input_hash: str,
    response_excerpt: str,
    model_ref: str | None,
) -> LiaGuardrailEvent:
    row = LiaGuardrailEvent(
        id=str(uuid.uuid4()),
        session_id=session_id,
        user_id=user_id,
        department_id=department_id,
        event_type="persona_refusal",
        category=clause_id,
        action_taken=str(ActionTier.LOG),
        user_input_hash=user_input_hash,
        response_excerpt=response_excerpt[:500],
        tripwire_pattern=None,
        model_ref=model_ref,
    )
    db.add(row)
    return row


def list_events(
    db: Session,
    *,
    since_days: int = 7,
    category: str | None = None,
    department_id: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[LiaGuardrailEvent]:
    cutoff = datetime.now(UTC) - timedelta(days=since_days)
    stmt = select(LiaGuardrailEvent).where(LiaGuardrailEvent.created_at >= cutoff)
    if category:
        stmt = stmt.where(LiaGuardrailEvent.category == category)
    if department_id:
        stmt = stmt.where(LiaGuardrailEvent.department_id == department_id)
    stmt = stmt.order_by(LiaGuardrailEvent.created_at.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())


def wipe_all(db: Session) -> int:
    """Personal-mode 'Wipe guardrail logs' button. Returns rows deleted."""
    rowcount = db.query(LiaGuardrailEvent).delete()
    return int(rowcount or 0)
