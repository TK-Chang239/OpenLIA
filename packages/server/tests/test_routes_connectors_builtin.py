"""Tests for POST /api/connectors/install-builtin."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.engine import Engine


@pytest.fixture
def client(engine: Engine, db_session_factory) -> Iterator[TestClient]:
    from openlia_server.db.models.auth import User
    from openlia_server.middleware.auth import LOCAL_USER_ID
    from openlia_server.routes.connectors import build_connectors_router

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):  # type: ignore[no-untyped-def]
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    with db_session_factory() as s:
        s.merge(
            User(
                id=LOCAL_USER_ID,
                email="local@openlia.local",
                display_name="Local",
                password_hash=None,
                is_admin=True,
                is_disabled=False,
                must_change_password=False,
            )
        )
        s.commit()

    app = FastAPI()
    app.include_router(
        build_connectors_router(db_session_factory=db_session_factory, mode="personal"),
        prefix="/api",
    )
    yield TestClient(app)


def test_install_builtin_unknown_template_returns_404(client: TestClient) -> None:
    res = client.post(
        "/api/connectors/install-builtin",
        json={"template_id": "does-not-exist", "api_key": "k"},
    )
    assert res.status_code == 404


def test_install_builtin_missing_api_key_returns_422(client: TestClient) -> None:
    res = client.post("/api/connectors/install-builtin", json={"template_id": "firecrawl"})
    assert res.status_code == 422


def test_install_builtin_returns_201_and_connector_row(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Happy path: install Firecrawl with stubbed canary."""
    from openlia_server.services import connectors_service

    async def _fake_validate(launch, secrets):  # type: ignore[no-redef]
        return connectors_service.ValidationOk(tools=[], python_callables=[])

    monkeypatch.setattr(connectors_service, "_validate_launch", _fake_validate)

    res = client.post(
        "/api/connectors/install-builtin",
        json={"template_id": "firecrawl", "api_key": "user-key"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["provider_id"] == "firecrawl"
    assert body["source"] == "built_in"
    assert body["status"] == "validated"
