"""POST /departments/equity-research/chat — happy-path SSE."""

from __future__ import annotations

import json
from typing import Any

from openlia.llm.runtime.events import ChatDone, ChatStart, ChatToken


class _ScriptedChatRunner:
    def __init__(self, events: list[Any]) -> None:
        self._events = events

    async def run(
        self,
        *,
        department_id: str,
        user_id: str | None,
        messages,
        attachments=None,
        cancel_token=None,
    ):
        for event in self._events:
            yield event


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
    company_client.app.state.chat_runner_factory = lambda: _ScriptedChatRunner(
        [
            ChatStart(message_id="m1"),
            ChatToken(message_id="m1", text="AAPL guidance was in line."),
            ChatDone(message_id="m1", stop_reason="stop"),
        ]
    )
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
