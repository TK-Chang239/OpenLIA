"""Route tests for the Earnings Update v2 instruction-profile endpoints.

Reuses the app-construction pattern from
``test_earnings_update_v2_routes.py``: a real ``create_app`` with a temp
SQLite DB + an authenticated local user (personal mode), the EU v2 router
mounted, and the broker / cancel registry wired onto ``app.state``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from openlia.llm.runtime.report_eu import EventBroker
from openlia.llm.runtime.report_eu.default_template import build_default_template
from openlia_server.db import session as session_mod
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
from openlia_server.db.models.report_eu import ReportEuTemplate

_BASE = "/api/departments/earnings-update/v2"


def _seed_local_user() -> None:
    with session_mod.SessionLocal() as s:
        s.add(
            User(
                id="local",
                email="local@openlia.local",
                display_name="Local",
                is_admin=True,
                is_disabled=False,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        s.commit()


def _seed_eu_default() -> None:
    spec = build_default_template()
    now = datetime.now(UTC)
    with session_mod.SessionLocal() as s:
        s.add(
            ReportEuTemplate(
                id=spec.template_id,
                user_id=None,
                name=spec.name,
                is_builtin=True,
                template_spec_json=json.loads(spec.model_dump_json()),
                source_markdown=None,
                source_doc_blob=None,
                source_doc_mime=None,
                created_at=now,
                updated_at=now,
                deleted_at=None,
            )
        )
        s.commit()


def _build_app(tmp_path, monkeypatch, *, enabled: bool):
    import openlia_server.db.models.register_all  # noqa: F401
    from openlia_server.app import create_app
    from openlia_server.routes.departments.earnings_update_v2 import (
        build_earnings_update_v2_router,
    )

    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/eu_v2.db")
    if enabled:
        monkeypatch.setenv("EARNINGS_ENGINE_VERSION", "v2")
    else:
        monkeypatch.delenv("EARNINGS_ENGINE_VERSION", raising=False)
    session_mod.configure_engine(f"sqlite:///{tmp_path}/eu_v2.db")
    Base.metadata.create_all(session_mod.get_engine())

    _seed_local_user()
    _seed_eu_default()

    app = create_app(db_session_factory=session_mod.SessionLocal)
    app.include_router(
        build_earnings_update_v2_router(
            db_session_factory=session_mod.SessionLocal, mode="personal"
        )
    )
    app.state.eu_v2_event_broker = EventBroker()
    app.state.eu_v2_cancel_registry = {}
    return app


@pytest.fixture
def client_eu_v2(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch, enabled=True)
    try:
        yield TestClient(app)
    finally:
        session_mod.dispose_engine()


@pytest.fixture
def client_eu_v2_disabled(tmp_path, monkeypatch):
    app = _build_app(tmp_path, monkeypatch, enabled=False)
    try:
        yield TestClient(app)
    finally:
        session_mod.dispose_engine()


def test_instructions_crud_roundtrip(client_eu_v2):
    # POST multipart: name + a text/plain file.
    r = client_eu_v2.post(
        f"{_BASE}/instructions",
        data={"name": "FCF bias"},
        files={"file": ("methodology.txt", b"Favor FCF.", "text/plain")},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    instructions_id = body["id"]
    assert body["name"] == "FCF bias"
    assert body["is_builtin"] is False

    # GET list contains it.
    r = client_eu_v2.get(f"{_BASE}/instructions")
    assert r.status_code == 200
    assert instructions_id in [row["id"] for row in r.json()]

    # PUT /settings with instructions_id round-trips.
    r = client_eu_v2.put(
        f"{_BASE}/settings",
        json={
            "provider_kind": "anthropic",
            "model": "claude-sonnet-4-6",
            "template_id": "eu_default",
            "language": "en",
            "length": "normal",
            "reasoning_effort": "high",
            "enabled_provider_ids": ["eodhd"],
            "web_search_enabled": False,
            "instructions_id": instructions_id,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["instructions_id"] == instructions_id

    r = client_eu_v2.get(f"{_BASE}/settings")
    assert r.status_code == 200
    assert r.json()["instructions_id"] == instructions_id

    # DELETE -> 204.
    r = client_eu_v2.delete(f"{_BASE}/instructions/{instructions_id}")
    assert r.status_code == 204


def test_instructions_503_when_disabled(client_eu_v2_disabled):
    r = client_eu_v2_disabled.get(f"{_BASE}/instructions")
    assert r.status_code == 503
