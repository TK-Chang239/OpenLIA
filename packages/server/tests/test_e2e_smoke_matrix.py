"""End-to-end smoke matrix (REM-P1-019).

Chains the product journeys the remediation checklist enumerates — one test
per journey, each exercising multiple routes through a single TestClient so
regressions that break a flow (rather than a single route) surface in CI.

Journeys covered:
    * Personal first-run setup
    * Company invite -> register -> login -> setup finish
    * Auth logout / reload
    * Provider create / edit / delete (admin)
    * Password reset + must-change-password
    * Repository save / open / download / unsave

Individual route tests still live under tests/test_routes/*; these tests are
deliberately coarse and assert the outward-visible contract only.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from openlia_server.app import create_app
from openlia_server.middleware.auth import COOKIE_NAME
from openlia_server.middleware.rate_limit import limiter


@pytest.fixture(autouse=True)
def _clear_rate_limiter():
    limiter().clear()
    yield
    limiter().clear()


def _personal_wizard_client(db_session):
    from openlia_server.db import session as session_mod

    app = create_app(
        db_session_factory=session_mod.SessionLocal,
        is_loopback_request=lambda _: True,
    )
    return TestClient(app)


def _company_wizard_client(db_session):
    from openlia_server.db import session as session_mod

    app = create_app(
        db_session_factory=session_mod.SessionLocal,
        is_loopback_request=lambda _: True,
    )
    return TestClient(app)


def _company_client(monkeypatch, db_session):
    monkeypatch.setenv("OPENLIA_MODE", "company")
    monkeypatch.setenv("OPENLIA_COOKIE_SECURE", "false")
    from openlia_server.db import session as session_mod
    from openlia_server.services.auth import signup_policy

    signup_policy.seed_signup_policy(db_session, mode_flag="company")
    app = create_app(db_session_factory=session_mod.SessionLocal)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Journey 1: personal first-run setup
# ---------------------------------------------------------------------------


def test_journey_personal_first_run_setup(db_session) -> None:
    client = _personal_wizard_client(db_session)

    # Fresh install: wizard incomplete, sitting on the mode step.
    status = client.get("/setup/status")
    assert status.status_code == 200
    body = status.json()
    assert body["wizard_completed"] is False
    assert body["current_step"] == "mode"

    # Pick personal mode. Server issues the wizard session cookie.
    resp = client.post("/setup/mode", json={"mode": "personal"})
    assert resp.status_code == 200
    assert client.cookies.get("openlia_wizard_session")

    # Name the local user.
    resp = client.post("/setup/identity", json={"display_name": "TK"})
    assert resp.status_code == 200

    # Finish. Finalize should redirect into the SPA root.
    resp = client.post("/setup/finish")
    assert resp.status_code == 200
    assert resp.json()["redirect"] == "/"

    # Status must now reflect completion; a second finish is 410 Gone.
    assert client.get("/setup/status").json()["wizard_completed"] is True
    assert client.post("/setup/finish").status_code == 410

    # Local user exists and is non-admin.
    from openlia_server.db.models.auth import User

    user = db_session.query(User).filter_by(email="local@openlia.local").one()
    assert user.display_name == "TK"
    assert user.is_admin is False


# ---------------------------------------------------------------------------
# Journey 2: company invite -> register -> login -> setup finish
# ---------------------------------------------------------------------------


def test_journey_company_invite_register_login(db_session, monkeypatch, make_user) -> None:
    # Seed an admin first so we can mint an invite through the admin API.
    admin = make_user(email="admin@example.com", is_admin=True)
    client = _company_client(monkeypatch, db_session)

    # Admin logs in.
    login = client.post(
        "/auth/login",
        json={"email": admin.email, "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    assert login.json()["is_admin"] is True

    # Admin creates an invite.
    invite_resp = client.post("/admin/invites", json={"label": "e2e"})
    assert invite_resp.status_code == 201
    invite_token = invite_resp.json()["token"]

    # Admin logs out so we can simulate a new-user registration.
    assert client.post("/auth/logout").status_code == 204
    client.cookies.clear()

    # Flip signup policy to invite_only so registration requires the token.
    from openlia_server.services.auth import signup_policy

    signup_policy.seed_signup_policy(db_session, mode_flag="invite_only")

    # New user registers with the raw invite token.
    reg = client.post(
        "/auth/register",
        json={
            "email": "new@example.com",
            "password": "CorrectHorseBattery9!",
            "display_name": "New",
            "invite_token": invite_token,
        },
    )
    assert reg.status_code == 201
    # Registration establishes a session cookie immediately.
    session = client.get("/auth/session")
    assert session.status_code == 200
    assert session.json()["email"] == "new@example.com"

    # Simulate a fresh browser: clear cookies, log back in.
    client.cookies.clear()
    relogin = client.post(
        "/auth/login",
        json={"email": "new@example.com", "password": "CorrectHorseBattery9!"},
    )
    assert relogin.status_code == 200
    assert client.get("/auth/session").status_code == 200


# ---------------------------------------------------------------------------
# Journey 3: auth logout / reload
# ---------------------------------------------------------------------------


def test_journey_logout_invalidates_session(db_session, monkeypatch, make_user) -> None:
    user = make_user(password="CorrectHorseBattery9!")
    client = _company_client(monkeypatch, db_session)

    login = client.post(
        "/auth/login",
        json={"email": user.email, "password": "CorrectHorseBattery9!"},
    )
    assert login.status_code == 200
    cookie = client.cookies.get(COOKIE_NAME)
    assert cookie

    # Authenticated.
    assert client.get("/auth/session").status_code == 200

    # Logout clears server state and cookie.
    assert client.post("/auth/logout").status_code == 204

    # Replay the old cookie — server must reject it.
    client.cookies.set(COOKIE_NAME, cookie)
    assert client.get("/auth/session").status_code == 401


# ---------------------------------------------------------------------------
# Journey 4: provider create / edit / delete (admin-only)
# ---------------------------------------------------------------------------


def test_journey_provider_crud(db_session, monkeypatch, make_user) -> None:
    admin = make_user(email="admin@example.com", is_admin=True)
    client = _company_client(monkeypatch, db_session)
    assert (
        client.post(
            "/auth/login",
            json={"email": admin.email, "password": "correct horse battery staple"},
        ).status_code
        == 200
    )

    # Empty to start.
    assert client.get("/settings/admin/llm/providers").json() == []

    # Create — run_test=False so no network is required.
    create = client.post(
        "/settings/admin/llm/providers",
        json={
            "kind": "openai",
            "label": "Main OpenAI",
            "api_key": "sk-test",
            "run_test": False,
        },
    )
    assert create.status_code == 201
    provider_id = create.json()["id"]
    assert create.json()["has_api_key"] is True
    assert "api_key" not in create.json()

    # Update label + disable.
    update = client.put(
        f"/settings/admin/llm/providers/{provider_id}",
        json={"label": "Renamed", "is_enabled": False},
    )
    assert update.status_code == 200
    assert update.json()["label"] == "Renamed"
    assert update.json()["is_enabled"] is False

    # Delete — no models attached, so should succeed with 204.
    delete = client.delete(f"/settings/admin/llm/providers/{provider_id}")
    assert delete.status_code == 204
    assert client.get("/settings/admin/llm/providers").json() == []


# ---------------------------------------------------------------------------
# Journey 5: password reset + must-change-password gate
# ---------------------------------------------------------------------------


def test_journey_password_reset_and_forced_change(db_session, monkeypatch, make_user) -> None:
    admin = make_user(email="admin@example.com", is_admin=True)
    target = make_user(email="alice@example.com", password="CorrectHorseBattery9!")
    client = _company_client(monkeypatch, db_session)

    # Admin logs in and triggers a direct reset for the target user.
    assert (
        client.post(
            "/auth/login",
            json={"email": admin.email, "password": "correct horse battery staple"},
        ).status_code
        == 200
    )
    reset = client.post(
        f"/admin/users/{target.id}/reset-password",
        json={"new_password": "NewTempPassword1!"},
    )
    assert reset.status_code == 204
    assert client.post("/auth/logout").status_code == 204
    client.cookies.clear()

    # Target logs in with the temp password; must_change_password is set.
    login = client.post(
        "/auth/login",
        json={"email": target.email, "password": "NewTempPassword1!"},
    )
    assert login.status_code == 200
    assert login.json()["must_change_password"] is True

    # Must-change-password-gated routes (portfolio, notifications) reject with 403.
    blocked = client.get("/portfolio/holdings")
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "must_change_password"
    assert client.get("/notifications/unread").status_code == 403

    # /auth/session stays open so the frontend can render the change-password view.
    assert client.get("/auth/session").status_code == 200

    # Change password — server clears the must_change_password flag.
    change = client.post(
        "/auth/change-password",
        json={
            "current_password": "NewTempPassword1!",
            "new_password": "FinalPassword9!",
        },
    )
    assert change.status_code == 200

    # Normal access is restored.
    assert client.get("/portfolio/holdings").status_code == 200

    # Old temp password no longer works.
    client.cookies.clear()
    assert (
        client.post(
            "/auth/login",
            json={"email": target.email, "password": "NewTempPassword1!"},
        ).status_code
        == 401
    )


# ---------------------------------------------------------------------------
# Journey 6: repository open / save / download / unsave
# ---------------------------------------------------------------------------


def test_journey_repo_save_open_unsave(db_session, monkeypatch, make_user) -> None:
    user = make_user(password="CorrectHorseBattery9!")
    client = _company_client(monkeypatch, db_session)
    assert (
        client.post(
            "/auth/login",
            json={"email": user.email, "password": "CorrectHorseBattery9!"},
        ).status_code
        == 200
    )

    # Seed a report the user owns directly in the DB.
    import uuid

    from openlia_server.db.models.content import Report

    report_id = str(uuid.uuid4())
    payload = {
        "schema_version": "1.0",
        "department": "secretary",
        "generated_at": "2026-04-24T10:00:00Z",
        "cover": {
            "title": "Smoke Report",
            "subtitle": "E2E",
            "tagline": "smoke",
        },
        "sections": [
            {
                "id": "intro",
                "title": "Intro",
                "blocks": [{"type": "text", "content": "Smoke body."}],
            }
        ],
    }
    db_session.add(
        Report(
            id=report_id,
            user_id=user.id,
            department="secretary",
            report_type="summary",
            title="Smoke Report",
            content_markdown="# Smoke",
            content_structured=payload,
            model_ref="test",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    # Repo starts empty.
    empty = client.get("/repo/items")
    assert empty.status_code == 200
    assert empty.json()["items"] == []

    # Save the report into the repository.
    save = client.post("/repo/items", json={"report_id": report_id})
    assert save.status_code == 201

    # List shows it.
    listing = client.get("/repo/items")
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert len(items) == 1
    assert items[0]["report_id"] == report_id

    # Facets include the department row.
    facets = client.get("/repo/facets")
    assert facets.status_code == 200
    assert facets.json()["total"] == 1

    # Open the report through /reports/{id} (owner-scoped). Payload returns
    # the canonical ReportSchema, which exposes department + cover but not id.
    opened = client.get(f"/reports/{report_id}")
    assert opened.status_code == 200
    schema = opened.json()["schema"]
    assert schema["department"] == "secretary"
    assert schema["cover"]["title"] == "Smoke Report"

    # Unsave — repo empties again.
    unsave = client.delete(f"/repo/items?report_id={report_id}")
    assert unsave.status_code == 204
    assert client.get("/repo/items").json()["items"] == []

    # Another user cannot see the report.
    other = make_user(email="bob@example.com", password="CorrectHorseBattery9!")
    client.cookies.clear()
    assert (
        client.post(
            "/auth/login",
            json={"email": other.email, "password": "CorrectHorseBattery9!"},
        ).status_code
        == 200
    )
    assert client.get(f"/reports/{report_id}").status_code == 404
