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

    async def _fake_validate(launch, secrets, *, tool_overrides=None):  # type: ignore[no-redef]
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


def test_install_builtin_second_call_returns_409_with_existing_id(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from openlia_server.services import connectors_service

    async def _fake_validate(launch, secrets, *, tool_overrides=None):
        return connectors_service.ValidationOk(tools=[], python_callables=[])

    monkeypatch.setattr(connectors_service, "_validate_launch", _fake_validate)

    first = client.post(
        "/api/connectors/install-builtin",
        json={"template_id": "firecrawl", "api_key": "user-key"},
    )
    assert first.status_code == 201
    existing_id = first.json()["id"]

    second = client.post(
        "/api/connectors/install-builtin",
        json={"template_id": "firecrawl", "api_key": "different-key"},
    )
    assert second.status_code == 409
    detail = second.json()["detail"]
    assert detail["existing_id"] == existing_id
    assert detail["provider_id"] == "firecrawl"
    assert detail["source"] == "built_in"


def test_get_builtin_templates_returns_six_entries(client: TestClient) -> None:
    res = client.get("/api/connectors/builtins")
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body, list)
    template_ids = {t["template_id"] for t in body}
    assert template_ids == {"eodhd", "fmp", "newsapi_ai", "mediastack", "firecrawl", "x"}


def test_get_builtin_templates_card_shape(client: TestClient) -> None:
    res = client.get("/api/connectors/builtins")
    body = res.json()
    for t in body:
        assert {
            "template_id",
            "display_name",
            "category",
            "api_key_env_var",
            "covered_need_ids",
        }.issubset(t.keys())
        # Internal recipe details are NOT exposed:
        assert "available_modes" not in t
        assert "runner_specs" not in t
