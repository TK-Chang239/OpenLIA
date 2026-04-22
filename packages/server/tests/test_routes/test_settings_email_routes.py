"""Tests for PATCH /settings/email with password confirmation."""

from fastapi.testclient import TestClient


def test_patch_email_success(company_client: TestClient, auth_user, db_session) -> None:
    from openlia_server.db.models.auth import User

    resp = company_client.patch(
        "/settings/email",
        json={"new_email": "new@example.com", "current_password": "CorrectHorseBattery9!"},
    )
    assert resp.status_code == 200

    db_session.expire_all()
    fresh = db_session.get(User, auth_user.id)
    assert fresh.email == "new@example.com"


def test_patch_email_rejects_wrong_password(company_client: TestClient, auth_user) -> None:
    resp = company_client.patch(
        "/settings/email",
        json={"new_email": "new@example.com", "current_password": "nope"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "invalid_credentials"


def test_patch_email_rejects_duplicate(company_client: TestClient, auth_user, make_user) -> None:
    make_user(email="taken@example.com")
    resp = company_client.patch(
        "/settings/email",
        json={"new_email": "taken@example.com", "current_password": "CorrectHorseBattery9!"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "email_in_use"


def test_patch_email_rejects_invalid_format(company_client: TestClient, auth_user) -> None:
    resp = company_client.patch(
        "/settings/email",
        json={"new_email": "not-an-email", "current_password": "CorrectHorseBattery9!"},
    )
    assert resp.status_code == 422
