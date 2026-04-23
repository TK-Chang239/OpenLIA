"""GET /reports/{id} — owner-scoped read."""

from __future__ import annotations

from fastapi.testclient import TestClient
from openlia_server.db.models.auth import User
from sqlalchemy.orm import Session


def _seed_user(db_session: Session, uid: str, email: str) -> User:
    u = User(
        id=uid,
        email=email,
        display_name=uid,
        password_hash=None,
        is_admin=False,
        is_disabled=False,
    )
    db_session.add(u)
    db_session.commit()
    return u


def _save_report(db_session: Session, owner_id: str) -> str:
    from openlia_server.services import reports as svc

    schema = {
        "title": "T",
        "sections": [{"heading": "H", "content": "C"}],
    }
    report = svc.save_report(
        db_session,
        user_id=owner_id,
        department="secretary",
        report_type="chat_summary",
        title="T",
        subject=None,
        content_markdown="# T",
        content_structured=schema,
        model_ref="gpt-4o",
    )
    db_session.commit()
    return report.id


def test_get_report_as_owner_returns_dto(personal_client: TestClient, db_session: Session) -> None:
    report_id = _save_report(db_session, owner_id="local")
    r = personal_client.get(f"/reports/{report_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == report_id
    assert body["department"] == "secretary"
    assert body["title"] == "T"
    assert body["content_structured"] == {
        "title": "T",
        "sections": [{"heading": "H", "content": "C"}],
    }
    assert body["model_ref"] == "gpt-4o"
    assert "created_at" in body
    assert "updated_at" in body
    assert "user_id" not in body


def test_get_report_as_non_owner_returns_404(
    company_client: TestClient, auth_user, db_session: Session
) -> None:
    other = _seed_user(db_session, uid="other-user", email="other@example.com")
    report_id = _save_report(db_session, owner_id=other.id)

    r = company_client.get(f"/reports/{report_id}")
    assert r.status_code == 404


def test_get_report_missing_id_returns_404(personal_client: TestClient) -> None:
    r = personal_client.get("/reports/does-not-exist")
    assert r.status_code == 404


def test_get_report_unauthenticated_returns_401(company_client_anon: TestClient) -> None:
    r = company_client_anon.get("/reports/whatever")
    assert r.status_code == 401
