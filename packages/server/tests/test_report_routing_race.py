"""Two parallel report-generation requests against the same unbound
source chat must result in exactly one implicit-binding and one
redirect. The per-source-session lock serializes the binding decision."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import httpx
import pytest


@pytest.fixture
def seeded_unbound_chat_session(db_session):
    """A chat session with attached_report_id = NULL."""
    import uuid

    from openlia_server.db.models.content import ChatSession

    sess = ChatSession(
        id=str(uuid.uuid4()),
        user_id="local",
        department="equity_research",
        title="Unbound session",
    )
    db_session.add(sess)
    db_session.commit()
    return sess


@pytest.fixture
async def async_test_client(db_session, monkeypatch):
    """httpx.AsyncClient backed by ASGI transport in personal mode."""
    from openlia_server.app import create_app
    from openlia_server.db import session as session_mod
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
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_BACKGROUND_REPORTS_ENABLED", "1")
    app = create_app(db_session_factory=session_mod.SessionLocal)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def test_parallel_report_gen_serializes_binding(
    async_test_client: httpx.AsyncClient, seeded_unbound_chat_session
) -> None:
    source_id = seeded_unbound_chat_session.id
    body = {
        "source_session_id": source_id,
        "department_id": "equity_research",
        "mode": "stock_initiation",
        "user_input": "MSFT",
    }
    a_task = asyncio.create_task(async_test_client.post("/reports/generate", json=body))
    b_task = asyncio.create_task(async_test_client.post("/reports/generate", json=body))
    a_resp, b_resp = await asyncio.gather(a_task, b_task)
    a, b = a_resp.json(), b_resp.json()
    # Exactly one redirect=False (the one that bound the source),
    # exactly one redirect=True (the one that spawned a new thread).
    redirects = sorted([a["redirect"], b["redirect"]])
    assert redirects == [False, True]
    # Both report_ids are populated and distinct.
    assert a["report_id"] != b["report_id"]
    # Both session_ids — one matches source, the other is new.
    sids = {a["session_id"], b["session_id"]}
    assert source_id in sids
    assert len(sids) == 2
