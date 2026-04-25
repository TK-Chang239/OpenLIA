"""Regression tests for REM-P1-001 must-change-password global enforcement.

Users with `must_change_password=true` must be blocked from every authenticated
product route (settings, jobs, notifications, admin) with HTTP 403 and body
`{"code": "must_change_password"}`. Only `/auth/session`, `/auth/change-password`,
`/auth/logout`, and `/auth/logout-all` remain accessible so the user can finish
the forced reset and sign out.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import COOKIE_NAME
from openlia_server.services.auth import sessions


def _attach_cookie(client: TestClient, db_session, user: User) -> None:
    created = sessions.create_session(db_session, user_id=user.id, persistent=True)
    client.cookies.set(COOKIE_NAME, created.raw_token)


@pytest.fixture
def forced_user_client(company_client: TestClient, db_session, make_user):
    user = make_user(email="forced@example.com", is_admin=False)
    user.must_change_password = True
    db_session.commit()
    _attach_cookie(company_client, db_session, user)
    return company_client, user


@pytest.fixture
def forced_admin_client(company_client: TestClient, db_session, make_user):
    admin = make_user(email="forced-admin@example.com", is_admin=True)
    admin.must_change_password = True
    db_session.commit()
    _attach_cookie(company_client, db_session, admin)
    return company_client, admin


def _assert_must_change(resp) -> None:
    assert resp.status_code == 403, resp.text
    body = resp.json()
    detail = body.get("detail", body)
    assert detail == {"code": "must_change_password"}, body


class TestForcedPasswordBlocksProductRoutes:
    def test_notifications_unread_blocked(self, forced_user_client):
        client, _ = forced_user_client
        _assert_must_change(client.get("/notifications/unread"))

    def test_notifications_read_blocked(self, forced_user_client):
        client, _ = forced_user_client
        _assert_must_change(client.post("/notifications/read", json={"notification_ids": []}))

    def test_jobs_history_blocked(self, forced_user_client):
        client, _ = forced_user_client
        _assert_must_change(client.get("/jobs/history"))

    def test_jobs_retry_blocked(self, forced_user_client):
        client, _ = forced_user_client
        _assert_must_change(client.post("/jobs/some-run-id/retry"))

    def test_settings_prefs_get_blocked(self, forced_user_client):
        client, _ = forced_user_client
        _assert_must_change(client.get("/settings/prefs"))

    def test_settings_prefs_patch_blocked(self, forced_user_client):
        client, _ = forced_user_client
        _assert_must_change(client.patch("/settings/prefs", json={"theme": "dark"}))

    def test_settings_email_patch_blocked(self, forced_user_client):
        client, _ = forced_user_client
        _assert_must_change(
            client.patch(
                "/settings/email",
                json={
                    "new_email": "new@example.com",
                    "current_password": "correct horse battery staple",
                },
            )
        )

    def test_settings_models_list_blocked(self, forced_user_client):
        client, _ = forced_user_client
        _assert_must_change(client.get("/settings/models/preferences"))

    def test_settings_models_put_blocked(self, forced_user_client):
        client, _ = forced_user_client
        _assert_must_change(
            client.put(
                "/settings/models/preferences/thinking",
                json={"model_id": "any-id"},
            )
        )


class TestForcedPasswordBlocksAdminRoutes:
    def test_settings_data_providers_list_blocked(self, forced_admin_client):
        client, _ = forced_admin_client
        _assert_must_change(client.get("/settings/data-providers"))

    def test_settings_llm_providers_list_blocked(self, forced_admin_client):
        client, _ = forced_admin_client
        _assert_must_change(client.get("/settings/admin/llm/providers"))

    def test_admin_invites_list_blocked(self, forced_admin_client):
        client, _ = forced_admin_client
        _assert_must_change(client.get("/admin/invites"))

    def test_admin_users_list_blocked(self, forced_admin_client):
        client, _ = forced_admin_client
        _assert_must_change(client.get("/admin/users"))

    def test_admin_password_reset_requests_blocked(self, forced_admin_client):
        client, _ = forced_admin_client
        _assert_must_change(client.get("/admin/password-reset-requests"))


class TestForcedPasswordAllowsExemptAuthRoutes:
    def test_session_returns_flag(self, forced_user_client):
        client, _ = forced_user_client
        resp = client.get("/auth/session")
        assert resp.status_code == 200
        body = resp.json()
        assert body["must_change_password"] is True

    def test_change_password_unblocks_routes(self, forced_admin_client, db_session):
        client, admin = forced_admin_client

        resp = client.get("/admin/invites")
        _assert_must_change(resp)

        resp = client.post(
            "/auth/change-password",
            json={
                "current_password": "correct horse battery staple",
                "new_password": "entirely-new-secure-pass-2026",
            },
        )
        assert resp.status_code == 200, resp.text

        db_session.refresh(admin)
        assert admin.must_change_password is False

        resp = client.get("/admin/invites")
        assert resp.status_code == 200

    def test_logout_allowed(self, forced_user_client):
        client, _ = forced_user_client
        resp = client.post("/auth/logout")
        assert resp.status_code == 204

    def test_logout_all_allowed(self, forced_user_client):
        client, _ = forced_user_client
        resp = client.post("/auth/logout-all")
        assert resp.status_code == 204
