from __future__ import annotations

import pytest
from openlia_server.middleware.auth import COOKIE_NAME
from openlia_server.services.auth import sessions


@pytest.fixture
def admin_client(client, user_factory, db_session):
    user = user_factory()
    user.is_admin = True
    db_session.add(user)
    db_session.commit()
    created = sessions.create_session(db_session, user_id=user.id, persistent=False)
    client.cookies.set(COOKIE_NAME, created.raw_token)
    return client


@pytest.fixture
def client_authed(client, user_factory, login_as):
    user = user_factory()
    login_as(user)
    return client


def test_admin_lists_all_skills(admin_client):
    r = admin_client.get("/api/admin/skills")
    assert r.status_code == 200
    assert "items" in r.json()


def test_non_admin_blocked(client_authed):
    r = client_authed.get("/api/admin/skills")
    assert r.status_code == 403


def test_admin_audit_log_filter(admin_client):
    r = admin_client.get("/api/admin/skills/audit?since_days=7")
    assert r.status_code == 200
    assert isinstance(r.json()["items"], list)
