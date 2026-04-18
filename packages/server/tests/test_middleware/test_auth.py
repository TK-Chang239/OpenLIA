"""Tests for middleware.auth — require_auth, personal-mode shim."""

from __future__ import annotations

from datetime import UTC

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openlia_server.middleware.auth import COOKIE_NAME, build_require_auth
from openlia_server.services.auth import sessions


@pytest.fixture
def app_factory(db_session):
    def _make(mode: str) -> FastAPI:
        app = FastAPI()
        require_auth = build_require_auth(db_session_factory=lambda: db_session, mode=mode)

        @app.get("/whoami")
        def whoami(user=require_auth):  # type: ignore[assignment]
            return {"id": user.id, "email": user.email, "is_admin": user.is_admin}

        return app

    return _make


class TestCompanyMode:
    def test_401_without_cookie(self, app_factory):
        client = TestClient(app_factory("company"))
        resp = client.get("/whoami")
        assert resp.status_code == 401

    def test_401_with_invalid_cookie(self, app_factory):
        client = TestClient(app_factory("company"))
        client.cookies.set(COOKIE_NAME, "not-a-token")
        resp = client.get("/whoami")
        assert resp.status_code == 401

    def test_200_with_valid_session(self, app_factory, db_session, make_user):
        user = make_user()
        created = sessions.create_session(db_session, user_id=user.id, persistent=True)

        client = TestClient(app_factory("company"))
        client.cookies.set(COOKIE_NAME, created.raw_token)
        resp = client.get("/whoami")
        assert resp.status_code == 200
        assert resp.json()["id"] == user.id


class TestPersonalMode:
    def test_no_cookie_still_resolves_to_local_user(self, app_factory, db_session):
        from datetime import datetime

        from openlia_server.db.models.auth import User

        user = User(
            id="local",
            email="local@openlia.local",
            display_name="Local",
            is_admin=True,
            is_disabled=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(user)
        db_session.commit()

        client = TestClient(app_factory("personal"))
        resp = client.get("/whoami")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "local@openlia.local"
        assert data["is_admin"] is True

    def test_sessions_table_not_consulted(self, app_factory, db_session):
        from datetime import datetime

        from openlia_server.db.models.auth import User

        user = User(
            id="local",
            email="local@openlia.local",
            display_name="Local",
            is_admin=True,
            is_disabled=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(user)
        db_session.commit()
        client = TestClient(app_factory("personal"))
        resp = client.get("/whoami")
        assert resp.status_code == 200
