"""Tests for /setup/* routes."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Task 4: GET /setup/status
# ---------------------------------------------------------------------------


def test_status_fresh_install(wizard_personal_client: TestClient) -> None:
    resp = wizard_personal_client.get("/setup/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "personal"
    assert body["wizard_completed"] is False
    assert body["current_step"] == "mode"
    assert body["completed_steps"] == []
    assert body["env_overrides"] == {}


def test_status_after_completion_still_returns_200(
    wizard_personal_client: TestClient, db_session
) -> None:
    from openlia_server.db.models.infrastructure import ConfigStore

    db_session.add(ConfigStore(key="wizard.completed", value="true"))
    db_session.add(ConfigStore(key="wizard.mode", value="personal"))
    db_session.commit()

    resp = wizard_personal_client.get("/setup/status")
    assert resp.status_code == 200
    assert resp.json()["wizard_completed"] is True


# ---------------------------------------------------------------------------
# Task 5: POST /setup/mode
# ---------------------------------------------------------------------------


def test_post_mode_persists_and_issues_cookie(wizard_personal_client: TestClient) -> None:
    resp = wizard_personal_client.post("/setup/mode", json={"mode": "company"})
    assert resp.status_code == 200
    assert resp.json()["mode"] == "company"
    assert "openlia_wizard_session" in resp.cookies

    status = wizard_personal_client.get("/setup/status").json()
    assert status["mode"] == "company"
    assert "mode" in status["completed_steps"]


def test_post_mode_rejected_when_env_override_set(
    wizard_personal_client: TestClient, monkeypatch
) -> None:
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    resp = wizard_personal_client.post("/setup/mode", json={"mode": "company"})
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "env_locked"


def test_post_mode_rejects_invalid_value(wizard_personal_client: TestClient) -> None:
    resp = wizard_personal_client.post("/setup/mode", json={"mode": "banana"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Task 6: Session cookie + takeover
# ---------------------------------------------------------------------------


def test_second_browser_without_takeover_rejected(wizard_personal_client: TestClient) -> None:
    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    cookie = wizard_personal_client.cookies.get("openlia_wizard_session")
    assert cookie

    wizard_personal_client.cookies.clear()
    resp = wizard_personal_client.post("/setup/identity", json={"display_name": "Hacker"})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "wizard_session_active"


def test_takeover_rotates_token(wizard_personal_client: TestClient) -> None:
    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    first = wizard_personal_client.cookies.get("openlia_wizard_session")

    wizard_personal_client.cookies.clear()
    resp = wizard_personal_client.post("/setup/takeover")
    assert resp.status_code == 200
    second = wizard_personal_client.cookies.get("openlia_wizard_session")
    assert second and second != first


# ---------------------------------------------------------------------------
# Task 7: POST /setup/identity (personal)
# ---------------------------------------------------------------------------


def test_post_identity_creates_local_user(wizard_personal_client: TestClient, db_session) -> None:
    from openlia_server.db.models.auth import User

    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    resp = wizard_personal_client.post("/setup/identity", json={"display_name": "TK"})
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "TK"

    user = db_session.query(User).filter_by(email="local@openlia.local").one()
    assert user.display_name == "TK"
    assert user.is_admin is False


def test_post_identity_is_idempotent_on_display_name(
    wizard_personal_client: TestClient, db_session
) -> None:
    from openlia_server.db.models.auth import User

    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    wizard_personal_client.post("/setup/identity", json={"display_name": "A"})
    wizard_personal_client.post("/setup/identity", json={"display_name": "B"})

    rows = db_session.query(User).filter_by(email="local@openlia.local").all()
    assert len(rows) == 1
    assert rows[0].display_name == "B"


# ---------------------------------------------------------------------------
# Task 8: POST /setup/admin (company)
# ---------------------------------------------------------------------------


def test_post_admin_creates_first_admin(wizard_company_client: TestClient, db_session) -> None:
    from openlia_server.db.models.auth import User

    wizard_company_client.post("/setup/mode", json={"mode": "company"})
    resp = wizard_company_client.post(
        "/setup/admin",
        json={"email": "boss@example.com", "password": "CorrectHorseBattery9!", "display_name": "Boss"},
    )
    assert resp.status_code == 200

    user = db_session.query(User).filter_by(email="boss@example.com").one()
    assert user.is_admin is True
    assert user.password_hash.startswith("$argon2")


def test_post_admin_rejects_second_admin(wizard_company_client: TestClient) -> None:
    wizard_company_client.post("/setup/mode", json={"mode": "company"})
    wizard_company_client.post(
        "/setup/admin",
        json={"email": "first@example.com", "password": "CorrectHorseBattery9!", "display_name": "A"},
    )
    resp = wizard_company_client.post(
        "/setup/admin",
        json={"email": "second@example.com", "password": "CorrectHorseBattery9!", "display_name": "B"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "admin_exists"


def test_post_admin_rejects_short_password(wizard_company_client: TestClient) -> None:
    wizard_company_client.post("/setup/mode", json={"mode": "company"})
    resp = wizard_company_client.post(
        "/setup/admin",
        json={"email": "weak@example.com", "password": "short", "display_name": "W"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Task 11: POST /setup/access_control (company only)
# ---------------------------------------------------------------------------


def test_access_control_writes_policy_and_bind_config(
    wizard_company_client: TestClient, db_session
) -> None:
    from openlia_server.db.models.auth import SignupPolicy
    from openlia_server.db.models.infrastructure import ConfigStore

    wizard_company_client.post("/setup/mode", json={"mode": "company"})
    resp = wizard_company_client.post(
        "/setup/access_control",
        json={
            "signup_policy": "invite_only",
            "allowed_domains": "example.com,acme.com",
            "bind_host": "0.0.0.0",
            "bind_port": 8000,
        },
    )
    assert resp.status_code == 200

    policy = db_session.get(SignupPolicy, 1)
    assert policy is not None
    assert policy.mode == "invite_only"
    assert "example.com" in policy.allowed_email_domains

    host = db_session.get(ConfigStore, "server.bind_host")
    port = db_session.get(ConfigStore, "server.bind_port")
    assert host.value == "0.0.0.0"
    assert port.value == "8000"


def test_access_control_rejects_personal_mode(wizard_personal_client: TestClient) -> None:
    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    resp = wizard_personal_client.post(
        "/setup/access_control",
        json={"signup_policy": "invite_only", "bind_host": "127.0.0.1", "bind_port": 8000},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "wrong_mode"


# ---------------------------------------------------------------------------
# Task 14: /setup/review/* routes
# ---------------------------------------------------------------------------


def test_review_run_kicks_off_task_and_poll_returns_state(
    wizard_personal_client: TestClient, monkeypatch
) -> None:
    from openlia_server.ai_review import store as store_mod

    fresh_store = store_mod.ReviewStore()
    monkeypatch.setattr(store_mod, "DEFAULT_STORE", fresh_store)

    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    resp = wizard_personal_client.post("/setup/review/run")
    assert resp.status_code == 200
    review_id = resp.json()["review_id"]

    poll = wizard_personal_client.get(f"/setup/review/{review_id}")
    assert poll.status_code == 200
    assert poll.json()["state"] in ("running", "complete", "failed")


def test_review_poll_unknown_id_returns_404(wizard_personal_client: TestClient) -> None:
    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    resp = wizard_personal_client.get("/setup/review/nope")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Task 15: POST /setup/finish
# ---------------------------------------------------------------------------


def test_finish_writes_completed_and_returns_redirect(
    wizard_personal_client: TestClient, db_session
) -> None:
    from openlia_server.db.models.infrastructure import ConfigStore, WizardState

    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    resp = wizard_personal_client.post("/setup/finish")
    assert resp.status_code == 200
    assert resp.json()["redirect"] == "/"

    completed = db_session.get(ConfigStore, "wizard.completed")
    assert completed is not None
    assert completed.value == "true"
    state = db_session.get(WizardState, 1)
    assert state.active_session_token is None


def test_finish_returns_410_once_done(wizard_personal_client: TestClient) -> None:
    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})
    wizard_personal_client.post("/setup/finish")
    resp = wizard_personal_client.post("/setup/finish")
    assert resp.status_code == 410


def test_finish_company_mode_redirects_to_login(wizard_company_client: TestClient) -> None:
    wizard_company_client.post("/setup/mode", json={"mode": "company"})
    resp = wizard_company_client.post("/setup/finish")
    assert resp.json()["redirect"] == "/login"
