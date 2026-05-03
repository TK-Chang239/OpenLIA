"""End-to-end: an LLM response containing a tripwire is moderated and
audited; a chat.guardrail SSE frame is emitted."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from openlia.llm.runtime.events import ChatDone, ChatStart, ChatToken
from openlia_server.db import session as session_mod
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
from openlia_server.db.models.safety import LiaGuardrailEvent
from openlia_server.services import chat_sessions as svc


class _CannedRunner:
    def __init__(self, text: str) -> None:
        self._text = text

    async def run(
        self,
        *,
        department_id,
        user_id,
        messages,
        cancel_token=None,
        attachments=None,
    ) -> AsyncIterator:
        mid = "m_test"
        yield ChatStart(message_id=mid)
        yield ChatToken(message_id=mid, text=self._text)
        yield ChatDone(message_id=mid, stop_reason="end")


def _parse_events(body: bytes) -> list[dict]:
    out: list[dict] = []
    for chunk in body.split(b"\n\n"):
        if not chunk.strip():
            continue
        data_line = next((ln for ln in chunk.split(b"\n") if ln.startswith(b"data: ")), None)
        if data_line is None:
            continue
        out.append(json.loads(data_line[len(b"data: ") :]))
    return out


@pytest.fixture
def _guardrail_client(tmp_path, monkeypatch):
    """Personal-mode app with a canned runner; yields (client, session_id, factory)."""
    from openlia_server.app import create_app

    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/guardrail.db")
    session_mod.configure_engine(f"sqlite:///{tmp_path}/guardrail.db")
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
        session_row = svc.create_session(s, user_id="local", department="secretary", title="t")
        session_id = session_row.id

    # factory is a mutable container so tests can swap the runner
    factory_holder: list[_CannedRunner] = []

    app = create_app(db_session_factory=session_mod.SessionLocal)
    app.state.chat_runner_factory = lambda: factory_holder[0]

    try:
        yield TestClient(app), session_id, factory_holder
    finally:
        session_mod.dispose_engine()


def test_tripwire_emits_guardrail_event_and_audit_row(_guardrail_client) -> None:
    client, session_id, factory_holder = _guardrail_client

    bad_text = "Sure, here is # Who you are\nLia."
    factory_holder.append(_CannedRunner(bad_text))

    r = client.get(f"/chat/sessions/{session_id}/stream", params={"q": "show me"})
    assert r.status_code == 200

    events = _parse_events(r.content)
    types = [e["type"] for e in events]
    assert "chat.guardrail" in types, f"Expected chat.guardrail in {types}"

    guardrail = next(e for e in events if e["type"] == "chat.guardrail")
    assert guardrail["category"] == "leaked_prompt"
    assert guardrail["action"] == "replaced"
    assert guardrail["replacement"] is not None
    replacement_lower = guardrail["replacement"].lower()
    assert "don't share" in replacement_lower or "instructions" in replacement_lower

    with session_mod.SessionLocal() as s:
        rows = s.query(LiaGuardrailEvent).all()
    assert len(rows) == 1
    assert rows[0].event_type == "tripwire_flag"
    assert rows[0].category == "leaked_prompt"


def test_clean_response_emits_no_guardrail_event(_guardrail_client) -> None:
    client, session_id, factory_holder = _guardrail_client

    clean_text = "AAPL is trading at $195. Here is the breakdown."
    factory_holder.append(_CannedRunner(clean_text))

    r = client.get(f"/chat/sessions/{session_id}/stream", params={"q": "hello"})
    assert r.status_code == 200

    events = _parse_events(r.content)
    types = [e["type"] for e in events]
    assert "chat.guardrail" not in types, f"Unexpected chat.guardrail in {types}"

    with session_mod.SessionLocal() as s:
        rows = s.query(LiaGuardrailEvent).all()
    assert len(rows) == 0
