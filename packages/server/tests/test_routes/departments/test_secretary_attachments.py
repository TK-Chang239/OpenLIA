"""Phase 10 — Secretary route accepts multipart with attachments.

These tests POST ``multipart/form-data`` to ``/api/departments/secretary/chat``
and verify:
  - Valid files are persisted as ChatAttachment rows linked to the user message.
  - Files with disallowed mime / oversized fail with 4xx JSON before the SSE
    stream opens.
  - The runtime receives Attachment objects (verified via the captured
    runner factory).

The chat-runner is replaced with a fake to keep the tests deterministic and
to capture the inputs the runner actually received.
"""

from __future__ import annotations

import io
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

import pytest
from fastapi.testclient import TestClient
from openlia.llm.runtime.events import ChatDone, ChatStart, ChatToken, SseEvent
from openlia.llm.runtime.messages import Attachment as RuntimeAttachment
from openlia_server.db import session as session_mod
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import ChatAttachment, ChatMessage, ChatSession


class _FakeChatRunner:
    """Captures every ``run()`` call so the test can assert on attachments."""

    captured: ClassVar[list[dict[str, Any]]] = []

    @classmethod
    def reset(cls) -> None:
        cls.captured = []

    async def run(self, **kwargs: Any) -> AsyncIterator[SseEvent]:
        type(self).captured.append(kwargs)
        yield ChatStart(message_id="m_test")
        yield ChatToken(message_id="m_test", text="ok")
        yield ChatDone(message_id="m_test", stop_reason="complete")


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("OPENLIA_ATTACHMENTS_DIR", str(tmp_path / "attachments"))
    return tmp_path


@pytest.fixture
def app_and_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from openlia_server.app import create_app

    monkeypatch.setenv("OPENLIA_MODE", "personal")
    db_url = f"sqlite:///{tmp_path}/sec_att.db"
    monkeypatch.setenv("OPENLIA_DB_URL", db_url)
    session_mod.configure_engine(db_url)
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
        sess = ChatSession(id="s-att", user_id="local", department="secretary", title="t")
        s.add(sess)
        s.commit()

    app = create_app(db_session_factory=session_mod.SessionLocal)
    _FakeChatRunner.reset()
    app.state.chat_runner_factory = lambda: _FakeChatRunner()
    try:
        yield app, "s-att"
    finally:
        session_mod.dispose_engine()


@pytest.fixture
def client(app_and_session) -> TestClient:
    app, _ = app_and_session
    return TestClient(app)


@pytest.fixture
def session_id(app_and_session) -> str:
    return app_and_session[1]


def _multipart(
    message: str, files: list[tuple[str, bytes, str]] | None = None, session_id: str | None = None
) -> dict:
    payload: dict = {"data": {"message": message}}
    if session_id:
        payload["data"]["session_id"] = session_id
    if files:
        payload["files"] = [
            ("files", (name, io.BytesIO(content), mime)) for name, content, mime in files
        ]
    return payload


def test_multipart_with_text_file_persists_attachment_and_passes_to_runner(
    client: TestClient, session_id: str
) -> None:
    files = [("notes.txt", b"important context", "text/plain")]
    parts = _multipart("read this", files=files, session_id=session_id)

    resp = client.post(
        "/departments/secretary/chat",
        data=parts["data"],
        files=parts["files"],
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    # Drain the SSE stream so all server-side persistence completes.
    list(resp.iter_lines())

    with session_mod.SessionLocal() as s:
        msgs = s.query(ChatMessage).filter_by(session_id=session_id).all()
        user_msg = next(m for m in msgs if m.role == "user")
        atts = s.query(ChatAttachment).filter_by(message_id=user_msg.id).all()
        assert len(atts) == 1
        assert atts[0].filename == "notes.txt"
        assert atts[0].extracted_text == "important context"

    captured = _FakeChatRunner.captured
    assert captured
    runtime_atts = captured[-1].get("attachments") or ()
    assert len(runtime_atts) == 1
    assert isinstance(runtime_atts[0], RuntimeAttachment)
    assert runtime_atts[0].filename == "notes.txt"
    assert runtime_atts[0].extracted_text == "important context"


def test_multipart_disallowed_mime_returns_4xx_json_before_sse(
    client: TestClient, session_id: str
) -> None:
    files = [("evil.zip", b"PK\x03\x04...", "application/zip")]
    parts = _multipart("ok?", files=files, session_id=session_id)

    resp = client.post(
        "/departments/secretary/chat",
        data=parts["data"],
        files=parts["files"],
    )
    assert resp.status_code == 400
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    assert "errors" in body
    assert any(
        e["filename"] == "evil.zip" and e["reason"] == "type_not_allowed" for e in body["errors"]
    )


def test_multipart_without_files_still_works(client: TestClient, session_id: str) -> None:
    parts = _multipart("just text", session_id=session_id)
    resp = client.post(
        "/departments/secretary/chat",
        data=parts["data"],
    )
    assert resp.status_code == 200
    list(resp.iter_lines())


def test_existing_json_path_still_works(client: TestClient, session_id: str) -> None:
    """Backward-compat: callers sending application/json should still work."""
    resp = client.post(
        "/departments/secretary/chat",
        json={"message": "hi", "session_id": session_id},
    )
    assert resp.status_code == 200
    list(resp.iter_lines())
