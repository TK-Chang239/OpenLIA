"""POST/GET /departments/secretary/chat — SSE chat for the Secretary."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openlia.llm.runtime.events import (
    ChatDone,
    ChatStart,
    ChatToken,
    ChatToolCallResult,
    ChatToolCallStart,
)
from openlia.reports.schema import (
    Cover,
    PageFurniture,
    ReportSchema,
    Section,
    TextBlock,
)
from openlia_server.db import session as session_mod
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import ChatMessage
from openlia_server.services import chat_sessions as svc
from openlia_server.services.reports import create_report


class _ScriptedRunner:
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
        **kwargs,
    ):
        self.captured = {
            "department_id": department_id,
            "user_id": user_id,
            "messages": messages,
            "cancel_token": cancel_token,
            **kwargs,
        }
        for event in self._events:
            yield event


@pytest.fixture
def secretary_app(tmp_path, monkeypatch):
    from openlia_server.app import create_app

    monkeypatch.setenv("OPENLIA_MODE", "personal")
    db_url = f"sqlite:///{tmp_path}/sec.db"
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
        s.commit()
        sess = svc.create_session(s, user_id="local", department="secretary", title="t")
        session_id = sess.id

    app = create_app(db_session_factory=session_mod.SessionLocal)
    try:
        yield app, session_id
    finally:
        session_mod.dispose_engine()


@pytest.fixture
def company_app(tmp_path, monkeypatch):
    from openlia_server.app import create_app
    from openlia_server.services.auth import signup_policy

    monkeypatch.setenv("OPENLIA_MODE", "company")
    monkeypatch.setenv("OPENLIA_COOKIE_SECURE", "false")
    db_url = f"sqlite:///{tmp_path}/sec_co.db"
    monkeypatch.setenv("OPENLIA_DB_URL", db_url)
    session_mod.configure_engine(db_url)
    Base.metadata.create_all(session_mod.get_engine())

    with session_mod.SessionLocal() as s:
        signup_policy.seed_signup_policy(s, mode_flag="company")

    app = create_app(db_session_factory=session_mod.SessionLocal)
    try:
        yield app
    finally:
        session_mod.dispose_engine()


def _parse_frames(body: str) -> list[dict]:
    out: list[dict] = []
    for line in body.splitlines():
        if line.startswith("data: "):
            out.append(json.loads(line[len("data: ") :]))
    return out


def test_secretary_chat_streams_start_token_done(secretary_app):
    app, session_id = secretary_app
    runner = _ScriptedRunner(
        [
            ChatStart(message_id="m1"),
            ChatToken(message_id="m1", text="hi"),
            ChatToken(message_id="m1", text=" there"),
            ChatDone(message_id="m1", stop_reason="complete"),
        ]
    )
    app.state.chat_runner_factory = lambda: runner
    with TestClient(app) as client:
        r = client.post(
            "/departments/secretary/chat",
            json={"message": "hello", "session_id": session_id},
        )
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        frames = _parse_frames(r.text)
        types = [f["type"] for f in frames]
        assert types[0] == "chat.start"
        assert types.count("chat.token") == 2
        assert types[-1] == "chat.done"
    assert runner.captured["department_id"] == "secretary"
    assert runner.captured["user_id"] == "local"


def test_secretary_chat_emits_suggest_redirect_tool_call(secretary_app):
    app, session_id = secretary_app
    runner = _ScriptedRunner(
        [
            ChatStart(message_id="m1"),
            ChatToolCallStart(
                message_id="m1",
                call_id="c1",
                tool_name="suggest_redirect",
                args_preview='{"department":"equity_research"}',
            ),
            ChatToolCallResult(
                message_id="m1",
                call_id="c1",
                ok=True,
                summary="redirected",
                structured={
                    "department": "equity_research",
                    "reason": "deep dive",
                    "prefill": "AAPL",
                },
            ),
            ChatDone(message_id="m1", stop_reason="complete"),
        ]
    )
    app.state.chat_runner_factory = lambda: runner
    with TestClient(app) as client:
        r = client.post(
            "/departments/secretary/chat",
            json={"message": "research AAPL", "session_id": session_id},
        )
        assert r.status_code == 200
        frames = _parse_frames(r.text)
        results = [f for f in frames if f["type"] == "chat.tool_call.result"]
        assert len(results) == 1
        assert results[0]["structured"]["department"] == "equity_research"
        assert results[0]["structured"]["prefill"] == "AAPL"


def test_secretary_chat_threads_session_response_length_to_runner(secretary_app):
    """End-to-end: when the session row has ``response_length="concise"``,
    the secretary route reads it and forwards it through to the runner.
    Closes the integration gap between the service layer and the runtime."""
    app, session_id = secretary_app
    with session_mod.SessionLocal() as s:
        svc.set_session_response_length(
            s, session_id=session_id, user_id="local", response_length="concise"
        )

    runner = _ScriptedRunner(
        [ChatStart(message_id="m1"), ChatDone(message_id="m1", stop_reason="complete")]
    )
    app.state.chat_runner_factory = lambda: runner
    with TestClient(app) as client:
        r = client.post(
            "/departments/secretary/chat",
            json={"message": "hi", "session_id": session_id},
        )
        assert r.status_code == 200
    assert runner.captured.get("response_length") == "concise"


def test_secretary_chat_passes_none_response_length_when_unset(secretary_app):
    """Sessions without an explicit picker choice forward ``None`` so the
    runtime renders the system prompt without a length directive."""
    app, session_id = secretary_app
    runner = _ScriptedRunner(
        [ChatStart(message_id="m1"), ChatDone(message_id="m1", stop_reason="complete")]
    )
    app.state.chat_runner_factory = lambda: runner
    with TestClient(app) as client:
        r = client.post(
            "/departments/secretary/chat",
            json={"message": "hi", "session_id": session_id},
        )
        assert r.status_code == 200
    assert runner.captured.get("response_length") is None


def test_secretary_chat_requires_auth_in_company_mode(company_app):
    app = company_app
    runner = _ScriptedRunner(
        [ChatStart(message_id="m1"), ChatDone(message_id="m1", stop_reason="x")]
    )
    app.state.chat_runner_factory = lambda: runner
    with TestClient(app) as client:
        r = client.post("/departments/secretary/chat", json={"message": "hi"})
        assert r.status_code == 401


def test_secretary_chat_persists_session_messages(secretary_app):
    app, session_id = secretary_app
    runner = _ScriptedRunner(
        [
            ChatStart(message_id="m1"),
            ChatToken(message_id="m1", text="ack"),
            ChatDone(message_id="m1", stop_reason="complete"),
        ]
    )
    app.state.chat_runner_factory = lambda: runner
    with TestClient(app) as client:
        r = client.post(
            "/departments/secretary/chat",
            json={"message": "hello", "session_id": session_id},
        )
        assert r.status_code == 200
        # Drain stream so the persistence path runs.
        _ = r.text
    with session_mod.SessionLocal() as s:
        rows = (
            s.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
            .all()
        )
        roles = [r.role for r in rows]
        assert roles.count("user") == 1
        assert roles.count("assistant") == 1
        assistant = next(r for r in rows if r.role == "assistant")
        assert assistant.content == "ack"
        assert assistant.stopped_at is None


def test_secretary_chat_renames_default_titled_session_from_first_message(secretary_app):
    """A session created with the default "New chat" title gets auto-renamed
    to the first 48 chars of the user's first message via ``ensure_titled``."""
    from openlia_server.db.models.content import ChatSession as DbChatSession

    app, session_id = secretary_app
    # Reset the session title to the default that the frontend creates.
    with session_mod.SessionLocal() as s:
        row = s.get(DbChatSession, session_id)
        assert row is not None
        row.title = "New chat"
        s.commit()

    runner = _ScriptedRunner(
        [
            ChatStart(message_id="m1"),
            ChatToken(message_id="m1", text="ok"),
            ChatDone(message_id="m1", stop_reason="complete"),
        ]
    )
    app.state.chat_runner_factory = lambda: runner
    first_message = "What did Apple report for Q2 guidance and how does it compare to Q1?"
    with TestClient(app) as client:
        r = client.post(
            "/departments/secretary/chat",
            json={"message": first_message, "session_id": session_id},
        )
        assert r.status_code == 200
        _ = r.text
    with session_mod.SessionLocal() as s:
        row = s.get(DbChatSession, session_id)
        assert row is not None
        assert row.title != "New chat"
        # Spec: first 48 chars of the trimmed message.
        assert row.title == first_message[:48]


def test_secretary_chat_cancellation_persists_stopped_at(secretary_app):
    """When the runner's cancellation token is tripped, the persisted
    assistant message gets `stopped_at` populated. We exercise the
    persistence path directly (the same code the route invokes) so
    TestClient's lack of mid-stream abort doesn't gate the assertion.
    """
    _app, session_id = secretary_app
    from openlia_server.routes.departments.secretary import _persist_assistant

    _persist_assistant(
        db_session_factory=session_mod.SessionLocal,
        session_id=session_id,
        content="partial",
        tool_calls=None,
        stopped=True,
    )
    with session_mod.SessionLocal() as s:
        assistant = (
            s.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id, ChatMessage.role == "assistant")
            .one()
        )
        assert assistant.stopped_at is not None
        assert assistant.content == "partial"


def test_secretary_chat_save_report_to_repo_tool(secretary_app):
    app, session_id = secretary_app
    # Seed a report owned by 'local'.
    with session_mod.SessionLocal() as s:
        rid = create_report(
            s,
            user_id="local",
            department="secretary",
            mode="background",
            schema=ReportSchema(
                schema_version="2.0",
                department="secretary",
                generated_at=datetime(2026, 4, 24, tzinfo=UTC),
                page_furniture=PageFurniture(
                    header={"left": "L", "right": "R"},
                    footer={"left": "L", "center": "C", "right": "R"},
                    disclaimer="d",
                ),
                cover=Cover(title="T", subtitle="S", tagline="x"),
                sections=[
                    Section(
                        id="a",
                        title="A",
                        blocks=[TextBlock(type="text", content="a")],
                    )
                ],
            ),
        )
        s.commit()

    runner = _ScriptedRunner(
        [
            ChatStart(message_id="m1"),
            ChatToolCallStart(
                message_id="m1",
                call_id="c1",
                tool_name="save_report_to_repo",
                args_preview="{}",
            ),
            ChatToolCallResult(
                message_id="m1",
                call_id="c1",
                ok=True,
                summary="saved",
                structured={"arguments": {"report_id": rid}},
            ),
            ChatDone(message_id="m1", stop_reason="complete"),
        ]
    )
    app.state.chat_runner_factory = lambda: runner
    with TestClient(app) as client:
        r = client.post(
            "/departments/secretary/chat",
            json={"message": "save it", "session_id": session_id},
        )
        assert r.status_code == 200
        frames = _parse_frames(r.text)
        results = [f for f in frames if f["type"] == "chat.tool_call.result"]
        assert len(results) == 1
        assert results[0]["ok"] is True
        assert "repo_item_id" in (results[0]["structured"] or {})
        repo_item_id = results[0]["structured"]["repo_item_id"]
        assert isinstance(repo_item_id, str) and repo_item_id

    # Verify the row exists in repo_items.
    from openlia_server.db.models.content import RepoItem

    with session_mod.SessionLocal() as s:
        row = s.query(RepoItem).filter(RepoItem.id == repo_item_id).one()
        assert row.user_id == "local"
        assert row.report_id == rid
