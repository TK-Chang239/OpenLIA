"""GET /api/admin/guardrail-events with filtering."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from openlia_server.db.models.safety import LiaGuardrailEvent


def _seed(db_session, **overrides) -> None:
    base = {
        "id": str(uuid.uuid4()),
        "session_id": "s",
        "user_id": "u",
        "department_id": "equity_research",
        "event_type": "tripwire_flag",
        "category": "leaked_prompt",
        "action_taken": "replaced",
        "user_input_hash": "a" * 64,
        "response_excerpt": "x",
        "created_at": datetime.now(UTC),
    }
    base.update(overrides)
    db_session.add(LiaGuardrailEvent(**base))


def test_list_events_filters_category(db_session, personal_client) -> None:
    _seed(db_session, category="leaked_prompt")
    _seed(db_session, category="advice_phrasing", action_taken="warned")
    db_session.commit()

    r = personal_client.get("/api/admin/guardrail-events?since_days=7&category=leaked_prompt")
    assert r.status_code == 200
    rows = r.json()["items"]
    assert all(row["category"] == "leaked_prompt" for row in rows)


def test_list_events_filters_since(db_session, personal_client) -> None:
    _seed(db_session, created_at=datetime.now(UTC) - timedelta(days=30))
    _seed(db_session, created_at=datetime.now(UTC) - timedelta(days=2))
    db_session.commit()

    r = personal_client.get("/api/admin/guardrail-events?since_days=7")
    rows = r.json()["items"]
    assert len(rows) == 1
