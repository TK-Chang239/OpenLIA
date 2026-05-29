"""Route tests for v3 instruction profiles + the freeform-run guard.

Covers the HTTP surface added for instructions-only runs:
  - POST/GET/DELETE /instructions (multipart upload, owner-scoped list,
    soft delete) and unsupported-type rejection
  - POST /runs with the ``freeform`` template sentinel rejects a run
    that carries no instruction profile (400) before any engine call
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from openlia_server.db import session as session_mod
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User

_BASE = "/api/departments/equity-research/v3"


@pytest.fixture
def v3_client(tmp_path, monkeypatch):
    """TestClient + temp SQLite + an authenticated local user, with the
    v3 engine flag enabled so the routes respond (not 503)."""
    import openlia_server.db.models.register_all  # noqa: F401
    from openlia_server.app import create_app

    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/v3.db")
    monkeypatch.setenv("REPORT_ENGINE_VERSION", "v3")
    session_mod.configure_engine(f"sqlite:///{tmp_path}/v3.db")
    Base.metadata.create_all(session_mod.get_engine())

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

    app = create_app(db_session_factory=session_mod.SessionLocal)
    try:
        yield TestClient(app)
    finally:
        session_mod.dispose_engine()


def _upload(client: TestClient, *, name: str, text: bytes) -> dict:
    resp = client.post(
        f"{_BASE}/instructions",
        data={"name": name},
        files={"file": ("framework.md", text, "text/markdown")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_upload_list_delete_roundtrip(v3_client):
    body = _upload(v3_client, name="Winner framework", text=b"Industry before company.")
    assert body["name"] == "Winner framework"
    assert body["is_builtin"] is False
    instr_id = body["id"]

    listed = v3_client.get(f"{_BASE}/instructions")
    assert listed.status_code == 200
    assert [r["id"] for r in listed.json()] == [instr_id]

    deleted = v3_client.delete(f"{_BASE}/instructions/{instr_id}")
    assert deleted.status_code == 204
    assert v3_client.get(f"{_BASE}/instructions").json() == []


def test_upload_rejects_unsupported_type(v3_client):
    resp = v3_client.post(
        f"{_BASE}/instructions",
        data={"name": "bad"},
        files={"file": ("x.exe", b"MZ\x90\x00", "application/octet-stream")},
    )
    assert resp.status_code == 400
    assert "errors" in resp.json()["detail"]


def test_delete_unknown_instructions_404(v3_client):
    resp = v3_client.delete(f"{_BASE}/instructions/nope")
    assert resp.status_code == 404


def test_freeform_run_without_instructions_rejected(v3_client):
    resp = v3_client.post(
        f"{_BASE}/runs",
        json={
            "subject": "RKLB.US",
            "template_id": "freeform",
            "provider_kind": "anthropic",
            "model": "claude-sonnet-4-6",
        },
    )
    assert resp.status_code == 400
    assert "instruction profile" in resp.json()["detail"]
