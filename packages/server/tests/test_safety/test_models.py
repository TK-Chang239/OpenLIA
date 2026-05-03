"""Smoke tests for the safety ORM models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from openlia_server.db.models.safety import (
    LiaGuardrailEvent,
    UserDisclaimerAcceptance,
)


def test_lia_guardrail_event_round_trip(db_session) -> None:
    row = LiaGuardrailEvent(
        id=str(uuid.uuid4()),
        session_id="sess-1",
        user_id="user-1",
        department_id="equity_research",
        event_type="tripwire_flag",
        category="leaked_prompt",
        action_taken="replaced",
        user_input_hash="a" * 64,
        response_excerpt="some text",
        tripwire_pattern="# Who you are",
        model_ref="anthropic/claude-opus-4-7",
    )
    db_session.add(row)
    db_session.commit()

    fetched = db_session.query(LiaGuardrailEvent).filter_by(session_id="sess-1").one()
    assert fetched.category == "leaked_prompt"
    assert fetched.action_taken == "replaced"
    assert fetched.created_at is not None


def test_user_disclaimer_acceptance_round_trip(db_session) -> None:
    row = UserDisclaimerAcceptance(
        user_id="user-1",
        disclaimer_version="1.0.0",
        accepted_at=datetime.now(UTC),
    )
    db_session.add(row)
    db_session.commit()

    fetched = db_session.query(UserDisclaimerAcceptance).filter_by(user_id="user-1").one()
    assert fetched.disclaimer_version == "1.0.0"
