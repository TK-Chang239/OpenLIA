"""Slice 7 — POST /admin/graph/extract-now route tests.

Admin-only force-run of graph extraction for a target user. Lets dev
iterate without waiting for the nightly 03:00 schedule.

Tests inject a fake ``extract_fn_factory`` so no live LLM is needed.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openlia_server.db.models.content import ChatMessage, ChatSession
from openlia_server.db.models.graph import GraphExtractionRun
from openlia_server.middleware.auth import COOKIE_NAME
from openlia_server.routes.admin_graph import build_admin_graph_router
from openlia_server.services.auth import sessions

# ---------- helpers ----------


def _seed_session(
    db_session,
    *,
    user_id: str,
    session_id: str | None = None,
    updated_at: datetime | None = None,
    message_content: str = "I'm long NVDA",
) -> ChatSession:
    sid = session_id or f"s-{uuid.uuid4()}"
    row = ChatSession(
        id=sid,
        user_id=user_id,
        department="secretary",
        title="chat",
    )
    db_session.add(row)
    db_session.flush()
    if updated_at is not None:
        # TimestampMixin auto-fills updated_at; override after flush.
        row.updated_at = updated_at
    db_session.add(
        ChatMessage(
            id=f"{sid}-m1",
            session_id=sid,
            role="user",
            content=message_content,
            created_at=datetime.now(UTC),
        )
    )
    db_session.commit()
    return row


def _fake_extract_fn_factory(
    candidates_by_session: dict[str, list[dict[str, Any]]],
) -> Callable[[Any, str], tuple[Callable, str]]:
    """Build a factory returning a fixed extract_fn keyed off message content."""

    def _factory(db, user_id: str):
        # extract_fn receives list[ChatMessage]; we key by the first message
        # content so different sessions can return different candidates.
        def _extract(messages):
            if not messages:
                return []
            key = messages[0].content
            return candidates_by_session.get(key, [])

        return _extract, "fake-quick-model"

    return _factory


def _raising_extract_fn_factory(message: str) -> Callable[[Any, str], tuple[Callable, str]]:
    def _factory(db, user_id: str):
        def _extract(messages):
            raise RuntimeError(message)

        return _extract, "fake-quick-model"

    return _factory


def _build_client(
    db_session,
    monkeypatch,
    extract_fn_factory: Callable[[Any, str], tuple[Callable, str]],
) -> TestClient:
    """Build a minimal FastAPI app mounting only the admin_graph router.

    Going through ``create_app`` would mount the production router with
    the default LLM-resolving factory, and the test override would lose
    the routing race. Mounting our router in isolation keeps the test
    surface focused on the slice under test.
    """
    monkeypatch.setenv("OPENLIA_MODE", "company")
    monkeypatch.setenv("OPENLIA_COOKIE_SECURE", "false")
    from fastapi import FastAPI
    from openlia_server.db import session as session_mod
    from openlia_server.services.auth import signup_policy

    signup_policy.seed_signup_policy(db_session, mode_flag="company")
    app = FastAPI()
    app.include_router(
        build_admin_graph_router(
            db_session_factory=session_mod.SessionLocal,
            mode="company",
            extract_fn_factory=extract_fn_factory,
        )
    )
    return TestClient(app)


def _admin_client(client: TestClient, db_session, make_user) -> tuple[TestClient, Any]:
    admin = make_user(email=f"admin-{uuid.uuid4()}@example.com", is_admin=True)
    created = sessions.create_session(db_session, user_id=admin.id, persistent=True)
    client.cookies.set(COOKIE_NAME, created.raw_token)
    return client, admin


_PROPOSAL = {
    "kind": "user_construct",
    "payload": {
        "construct_kind": "position",
        "statement": "Long NVDA on services-margin thesis",
        "entity_kind": "ticker",
        "entity_value": "NVDA",
        "source_excerpt": "I'm long NVDA",
    },
}


# ---------- tests ----------


def test_admin_force_extract_persists_proposals_and_returns_audit_row(
    db_session, monkeypatch, make_user
):
    target = make_user(email=f"target-{uuid.uuid4()}@example.com")
    _seed_session(db_session, user_id=target.id, message_content="I'm long NVDA")

    factory = _fake_extract_fn_factory({"I'm long NVDA": [_PROPOSAL]})
    client = _build_client(db_session, monkeypatch, factory)
    client, _ = _admin_client(client, db_session, make_user)

    resp = client.post(f"/admin/graph/extract-now?user_id={target.id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["proposals_inserted"] == 1
    assert body["sessions_processed"] == 1
    assert body["error"] is None
    assert body["run_id"]

    # Audit row landed on the same id.
    db_session.expire_all()
    run = db_session.get(GraphExtractionRun, body["run_id"])
    assert run is not None
    assert run.user_id == target.id
    assert run.proposals_inserted == 1
    assert run.sessions_processed == 1
    assert run.error is None
    assert run.finished_at is not None


def test_admin_force_extract_skips_sessions_below_watermark(db_session, monkeypatch, make_user):
    target = make_user(email=f"target-{uuid.uuid4()}@example.com")

    # Successful prior run that establishes a watermark.
    prior = GraphExtractionRun(
        id=str(uuid.uuid4()),
        user_id=target.id,
        started_at=datetime.now(UTC) - timedelta(hours=2),
        finished_at=datetime.now(UTC) - timedelta(hours=2),
        model_id="m",
        proposals_inserted=0,
        sessions_processed=0,
        error=None,
    )
    db_session.add(prior)

    # Stale session (older than watermark).
    _seed_session(
        db_session,
        user_id=target.id,
        session_id="old",
        updated_at=datetime.now(UTC) - timedelta(hours=5),
        message_content="stale",
    )
    # Fresh session (newer than watermark).
    _seed_session(
        db_session,
        user_id=target.id,
        session_id="new",
        updated_at=datetime.now(UTC),
        message_content="fresh",
    )
    db_session.commit()

    factory = _fake_extract_fn_factory({"stale": [_PROPOSAL], "fresh": [_PROPOSAL]})
    client = _build_client(db_session, monkeypatch, factory)
    client, _ = _admin_client(client, db_session, make_user)

    resp = client.post(f"/admin/graph/extract-now?user_id={target.id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["sessions_processed"] == 1
    assert body["proposals_inserted"] == 1


def test_admin_force_extract_non_admin_returns_403(db_session, monkeypatch, make_user):
    target = make_user(email=f"target-{uuid.uuid4()}@example.com")

    factory = _fake_extract_fn_factory({})
    client = _build_client(db_session, monkeypatch, factory)

    plain = make_user(email=f"plain-{uuid.uuid4()}@example.com")
    created = sessions.create_session(db_session, user_id=plain.id, persistent=True)
    client.cookies.set(COOKIE_NAME, created.raw_token)

    resp = client.post(f"/admin/graph/extract-now?user_id={target.id}")
    assert resp.status_code == 403


def test_admin_force_extract_unknown_user_returns_404(db_session, monkeypatch, make_user):
    factory = _fake_extract_fn_factory({})
    client = _build_client(db_session, monkeypatch, factory)
    client, _ = _admin_client(client, db_session, make_user)

    resp = client.post("/admin/graph/extract-now?user_id=does-not-exist")
    assert resp.status_code == 404


def test_admin_force_extract_records_error_and_returns_500(db_session, monkeypatch, make_user):
    target = make_user(email=f"target-{uuid.uuid4()}@example.com")
    _seed_session(db_session, user_id=target.id, message_content="boom")

    factory = _raising_extract_fn_factory("LLM exploded")
    client = _build_client(db_session, monkeypatch, factory)
    client, _ = _admin_client(client, db_session, make_user)

    resp = client.post(f"/admin/graph/extract-now?user_id={target.id}")
    assert resp.status_code == 500
    body = resp.json()
    # The error message must surface in the audit row, not just the response.
    detail = body["detail"]
    run_id = detail["run_id"]

    db_session.expire_all()
    run = db_session.get(GraphExtractionRun, run_id)
    assert run is not None
    assert run.error is not None
    assert "LLM exploded" in run.error
    assert run.finished_at is not None


@pytest.fixture(autouse=True)
def _strip_openlia_db_url(monkeypatch):
    # Keep tests on the per-test SQLite (see root conftest engine fixture).
    monkeypatch.delenv("OPENLIA_DB_URL", raising=False)
