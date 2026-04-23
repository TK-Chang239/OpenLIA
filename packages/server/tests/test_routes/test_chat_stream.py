"""POST /departments/secretary/chat — scripted happy-path SSE stream."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient
from openlia.llm.runtime.events import ChatDone, ChatStart, ChatToken

from openlia_server.db import session as session_mod
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User

import pytest


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
        yield TestClient(app), runner
    finally:
        session_mod.dispose_engine()


def _parse_sse_frames(body: str) -> list[dict]:
    frames: list[dict] = []
    for line in body.splitlines():
        if line.startswith("data: "):
            frames.append(json.loads(line[len("data: "):]))
    return frames


def test_scripted_chat_stream_emits_expected_frames(stream_client) -> None:
    client, runner = stream_client
    r = client.post(
        "/departments/secretary/chat",
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")

    frames = _parse_sse_frames(r.text)
    types = [f["type"] for f in frames]
    assert types[0] == "chat.start"
    assert types[-1] == "chat.done"
    assert types.count("chat.token") == 3

    assert runner.captured["department_id"] == "secretary"
    assert runner.captured["user_id"] == "local"
    assert [m.content for m in runner.captured["messages"]] == ["hello"]
