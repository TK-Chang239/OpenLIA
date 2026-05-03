"""The nightly maintenance sweep prunes old lia_guardrail_events rows."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from openlia_server.db.models.safety import LiaGuardrailEvent
from openlia_server.scheduler.executors.maintenance import run_maintenance_once


def _make_event(db_session, *, days_ago: int) -> None:
    db_session.add(
        LiaGuardrailEvent(
            id=str(uuid.uuid4()),
            created_at=datetime.now(UTC) - timedelta(days=days_ago),
            session_id="s",
            department_id="d",
            event_type="tripwire_flag",
            category="leaked_prompt",
            action_taken="replaced",
            user_input_hash="a" * 64,
            response_excerpt="x",
        )
    )


def test_old_events_pruned(db_session, monkeypatch) -> None:
    monkeypatch.setenv("LIA_GUARDRAIL_LOG_RETENTION_DAYS", "30")
    _make_event(db_session, days_ago=10)
    _make_event(db_session, days_ago=45)
    db_session.commit()

    summary = run_maintenance_once(db_session)
    db_session.commit()

    assert summary["lia_guardrail_events_deleted"] == 1
    remaining = db_session.query(LiaGuardrailEvent).all()
    assert len(remaining) == 1
