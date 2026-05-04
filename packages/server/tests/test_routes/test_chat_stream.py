"""GET /chat/sessions/{id}/stream — scripted happy-path SSE stream."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openlia.llm.runtime.events import ChatDone, ChatStart, ChatToken
from openlia_server.db import session as session_mod
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
from openlia_server.services import chat_sessions as svc


class _ScriptedChatRunner:
    """Minimal stub matching `ChatRunner.run(...)` async-iterator contract."""

    def __init__(self, events: list[Any]) -> None:
        self._events = events
        self.captured: dict[str, Any] = {}

    async def run(
        self,
        *,
        department_id: str,
        user_id: str | None,
        messages,
        attachments=None,
        cancel_token=None,
        **_,
    ):
        self.captured = {
            "department_id": department_id,
            "user_id": user_id,
            "messages": messages,
            "cancel_token": cancel_token,
        }
        for event in self._events:
            yield event


@pytest.fixture
def stream_client(tmp_path, monkeypatch):
    from openlia_server.app import create_app

    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/stream.db")
    session_mod.configure_engine(f"sqlite:///{tmp_path}/stream.db")
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

    runner = _ScriptedChatRunner(
        events=[
            ChatStart(message_id="m1"),
            ChatToken(message_id="m1", text="hi"),
            ChatToken(message_id="m1", text=" "),
            ChatToken(message_id="m1", text="there"),
            ChatDone(message_id="m1", stop_reason="stop"),
        ]
    )

    app = create_app(db_session_factory=session_mod.SessionLocal)
    app.state.chat_runner_factory = lambda: runner

    try:
        yield TestClient(app), runner, session_id
    finally:
        session_mod.dispose_engine()


def _parse_sse_frames(body: str) -> list[dict]:
    frames: list[dict] = []
    event_name: str | None = None
    for line in body.splitlines():
        if line.startswith("event: "):
            event_name = line[len("event: ") :]
        elif line.startswith("data: "):
            payload = json.loads(line[len("data: ") :])
            assert event_name == payload["type"], "named event must match payload type"
            frames.append(payload)
            event_name = None
    return frames


def test_scripted_chat_stream_emits_named_event_frames(stream_client) -> None:
    client, runner, session_id = stream_client
    r = client.get(f"/chat/sessions/{session_id}/stream", params={"q": "hello"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")

    # Every frame must be prefixed with a matching `event: <type>` line.
    assert "event: chat.start" in r.text
    assert "event: chat.token" in r.text
    assert "event: chat.done" in r.text

    frames = _parse_sse_frames(r.text)
    types = [f["type"] for f in frames]
    assert types[0] == "chat.start"
    assert types[-1] == "chat.done"
    assert types.count("chat.token") == 3

    assert runner.captured["department_id"] == "secretary"
    assert runner.captured["user_id"] == "local"
    # The runner sees the persisted conversation history (the just-added user message).
    assert runner.captured["messages"][-1].content == "hello"


def test_stream_persists_user_and_assistant_messages(stream_client) -> None:
    client, _runner, session_id = stream_client
    r = client.get(f"/chat/sessions/{session_id}/stream", params={"q": "hello"})
    assert r.status_code == 200

    with session_mod.SessionLocal() as s:
        rows = svc.list_messages(s, session_id=session_id, user_id="local")

    roles = [r.role for r in rows]
    contents = [r.content for r in rows]
    assert roles == ["user", "assistant"]
    assert contents[0] == "hello"
    assert contents[1] == "hi there"


def test_stream_returns_404_for_missing_session(stream_client) -> None:
    client, _runner, _session_id = stream_client
    r = client.get("/chat/sessions/missing/stream", params={"q": "x"})
    assert r.status_code == 404
