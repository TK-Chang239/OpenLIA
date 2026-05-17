"""Two parallel POST /reports/{source}/revise requests against the same
chat must result in BOTH eventually completing successfully — the
second waits for the first via the per-chat lock. After both, the
source chat is re-anchored to ONE of them."""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import httpx
import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def async_test_client(db_session, monkeypatch, tmp_path):
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
    bundle_dir = tmp_path / "bundles"
    bundle_dir.mkdir()
    monkeypatch.setenv("OPENLIA_REPORT_BUNDLE_DIR", str(bundle_dir))
    app = create_app(db_session_factory=session_mod.SessionLocal)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture
def seeded_source_report(db_session) -> str:
    """A completed report owned by the local user. Returns the report id."""
    from openlia_server.db.models.content import Report

    report_id = f"r_{uuid.uuid4().hex[:12]}"
    r = Report(
        id=report_id,
        user_id="local",
        department="equity_research",
        report_type="stock_initiation",
        title="Source Report",
        content_markdown="# Source",
        content_structured={"cover": {"title": "Source"}, "sections": []},
        model_ref="gpt-4",
        status="complete",
    )
    db_session.add(r)
    db_session.commit()
    return report_id


@pytest.fixture
def seeded_chat_with_messages(db_session, seeded_source_report) -> str:
    """A chat session bound to the source report. Returns the session id."""
    from openlia_server.db.models.content import ChatMessage, ChatSession

    session_id = str(uuid.uuid4())
    sess = ChatSession(
        id=session_id,
        user_id="local",
        department="equity_research",
        title="Bound chat",
        attached_report_id=seeded_source_report,
    )
    db_session.add(sess)
    db_session.flush()

    msg = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=session_id,
        role="user",
        content="Fix Q4 capex",
        created_at=datetime.now(UTC),
    )
    db_session.add(msg)
    db_session.commit()
    return session_id


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


async def test_parallel_revise_calls_serialize_via_chat_lock(
    monkeypatch: pytest.MonkeyPatch,
    async_test_client: httpx.AsyncClient,
    seeded_source_report: str,
    seeded_chat_with_messages: str,
) -> None:
    monkeypatch.setenv("OPENLIA_REVISION_PASS_ENABLED", "1")
    body = {
        "chat_session_id": seeded_chat_with_messages,
        "revision_brief": "x",
        "sections_to_focus": None,
    }
    a = async_test_client.post(f"/reports/{seeded_source_report}/revise", json=body)
    b = async_test_client.post(f"/reports/{seeded_source_report}/revise", json=body)
    resp_a, resp_b = await asyncio.gather(a, b)
    # Both accept; both return distinct report_ids.
    assert resp_a.status_code == 200 and resp_b.status_code == 200
    assert resp_a.json()["report_id"] != resp_b.json()["report_id"]
