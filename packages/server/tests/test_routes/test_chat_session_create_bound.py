"""Creating a chat session with attached_report_id stores the column
on the session row (in addition to the existing seed-message behavior
from _attach_report_as_context)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


@pytest.fixture
def seeded_report(db_session: Session, report_factory):
    return report_factory(user_id="local")


def test_create_session_with_attached_report_id_sets_column(
    personal_client: TestClient, seeded_report
) -> None:
    resp = personal_client.post(
        "/chat/sessions",
        json={
            "department": "equity_research",
            "title": "Bound session",
            "attached_report_id": seeded_report.id,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    session_id = body["id"]
    # Verify via the get endpoint that the column round-trips.
    get_resp = personal_client.get(f"/chat/sessions/{session_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["attached_report_id"] == seeded_report.id


def test_create_session_without_attached_report_id_leaves_column_null(
    personal_client: TestClient,
) -> None:
    resp = personal_client.post(
        "/chat/sessions",
        json={"department": "equity_research", "title": "Unbound session"},
    )
    assert resp.status_code == 201
    session_id = resp.json()["id"]
    get_resp = personal_client.get(f"/chat/sessions/{session_id}")
    assert get_resp.status_code == 200
    assert get_resp.json().get("attached_report_id") is None
