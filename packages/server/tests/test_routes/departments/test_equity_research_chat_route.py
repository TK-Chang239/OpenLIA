"""POST /departments/equity-research/chat — happy-path SSE."""

from __future__ import annotations

import json
from typing import Any

from openlia.llm.runtime.events import ChatDone, ChatStart, ChatToken
from openlia_server.db.models.content import ChatMessage as DbChatMessage
from openlia_server.services import chat_sessions as chat_sessions_svc


class _ScriptedChatRunner:
    def __init__(self, events: list[Any]) -> None:
        self._events = events
        self.last_kwargs: dict[str, Any] | None = None
        self.received_session_ids: list[str | None] = []

    async def run(
        self,
        *,
        department_id: str,
        user_id: str | None,
        messages,
        attachments=None,
        cancel_token=None,
        session_id: str | None = None,
        **_,
    ):
        self.last_kwargs = {
            "department_id": department_id,
            "user_id": user_id,
            "messages": messages,
            "session_id": session_id,
        }
        self.received_session_ids.append(session_id)
        for event in self._events:
            yield event


def _scripted_events() -> list[Any]:
    return [
        ChatStart(message_id="m1"),
        ChatToken(message_id="m1", text="AAPL guidance was in line."),
        ChatDone(message_id="m1", stop_reason="stop"),
    ]


def _consume_sse(iter_lines):
    events = []
    current = []
    for raw in iter_lines:
        line = raw.decode() if isinstance(raw, bytes) else raw
        if line == "":
            if current:
                events.append(json.loads("".join(current)))
                current = []
            continue
        if line.startswith("data:"):
            current.append(line[5:].lstrip())
    if current:
        events.append(json.loads("".join(current)))
    return events


def test_chat_route_streams_start_token_done(company_client, auth_user):
    company_client.app.state.chat_runner_factory = lambda: _ScriptedChatRunner(_scripted_events())
    r = company_client.post(
        "/departments/equity-research/chat",
        json={"message": "What did guidance look like?"},
        headers={"accept": "text/event-stream"},
    )
    assert r.status_code == 200
    events = _consume_sse(r.iter_lines())
    types = [e["type"] for e in events]
    assert types[0] == "chat.start"
    assert "chat.token" in types
    assert types[-1] == "chat.done"


def test_chat_route_requires_auth(company_client_anon):
    r = company_client_anon.post(
        "/departments/equity-research/chat",
        json={"message": "hi"},
    )
    assert r.status_code == 401


def test_chat_route_threads_session_id(company_client, auth_user, db_session):
    """P1-03 — session_id propagates from payload into ChatRunner.run."""
    runner = _ScriptedChatRunner(_scripted_events())
    company_client.app.state.chat_runner_factory = lambda: runner

    sess = chat_sessions_svc.create_session(
        db_session, user_id=auth_user.id, department="equity_research", title="t"
    )
    r = company_client.post(
        "/departments/equity-research/chat",
        json={"message": "ping", "session_id": sess.id},
    )
    assert r.status_code == 200
    assert runner.received_session_ids == [sess.id]


def test_chat_route_reuses_session_for_two_calls(company_client, auth_user, db_session):
    """P1-03 — two consecutive calls with the same session_id append to one
    session row, persisting both user + assistant messages."""
    company_client.app.state.chat_runner_factory = lambda: _ScriptedChatRunner(_scripted_events())

    sess = chat_sessions_svc.create_session(
        db_session, user_id=auth_user.id, department="equity_research", title="t"
    )
    for q in ["first?", "second?"]:
        r = company_client.post(
            "/departments/equity-research/chat",
            json={"message": q, "session_id": sess.id},
        )
        assert r.status_code == 200
        # Drain the SSE stream so the assistant message is persisted.
        list(r.iter_lines())

    rows = (
        db_session.query(DbChatMessage)
        .filter(DbChatMessage.session_id == sess.id)
        .order_by(DbChatMessage.created_at)
        .all()
    )
    roles = [r.role for r in rows]
    # 2x user + 2x assistant
    assert roles.count("user") == 2
    assert roles.count("assistant") == 2


def test_chat_route_rejects_unknown_session(company_client, auth_user):
    company_client.app.state.chat_runner_factory = lambda: _ScriptedChatRunner(_scripted_events())
    r = company_client.post(
        "/departments/equity-research/chat",
        json={"message": "hi", "session_id": "missing"},
    )
    assert r.status_code == 404
