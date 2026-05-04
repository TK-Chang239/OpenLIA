"""End-to-end TCP-disconnect verification for chat streaming.

Manual follow-up #2 (planning/audits/2026-04-25-phase-fix-completion-report.md):
"actual TCP-level disconnect during a streaming chat (cancel button or
browser close) needs end-to-end verification that chat_messages.stopped_at
populates."

Existing tests cover:
  - test_chat_stream_cancellation.py: asyncio task cancel → token flip
  - test_chat_stream_cancel.py: fake is_disconnected() → token flip → stopped=True

This test closes the gap: a real uvicorn server, a raw asyncio TCP socket,
and an early socket close mid-stream. The disconnect-watcher must flip the
cancel token, and the persisted assistant row must carry `stopped_at`.

The test is skipped if uvicorn is unavailable or the loopback bind fails.
"""

from __future__ import annotations

import asyncio
import contextlib
import socket
import threading
import time
from datetime import UTC, datetime

import pytest
from openlia.llm.runtime.events import ChatStart, ChatToken
from openlia_server.db import session as session_mod
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import ChatMessage
from openlia_server.services import chat_sessions as svc

uvicorn = pytest.importorskip("uvicorn")


class _SlowRunner:
    async def run(self, *, department_id, user_id, messages, attachments=None, cancel_token=None, **_):
        yield ChatStart(message_id="m1")
        yield ChatToken(message_id="m1", text="partial-")
        if cancel_token is not None:
            await cancel_token.wait()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_tcp_disconnect_persists_stopped_at(tmp_path, monkeypatch) -> None:
    from openlia_server.app import create_app

    monkeypatch.setenv("OPENLIA_MODE", "personal")
    db_url = f"sqlite:///{tmp_path}/disc.db"
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
        session_row = svc.create_session(s, user_id="local", department="secretary", title="t")
        session_id = session_row.id

    app = create_app(db_session_factory=session_mod.SessionLocal)
    app.state.chat_runner_factory = _SlowRunner

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="off")
    server = uvicorn.Server(config)

    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()
    try:
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if getattr(server, "started", False):
                break
            time.sleep(0.05)
        assert server.started, "uvicorn failed to start within 5s"

        async def _drive() -> None:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            request = (
                f"GET /chat/sessions/{session_id}/stream?q=hello HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{port}\r\n"
                "Accept: text/event-stream\r\n"
                "Connection: keep-alive\r\n"
                "\r\n"
            ).encode()
            writer.write(request)
            await writer.drain()

            # Read until we see at least one SSE frame, then hang up.
            buf = b""
            while b"event: chat.token" not in buf:
                chunk = await asyncio.wait_for(reader.read(1024), timeout=5.0)
                if not chunk:
                    break
                buf += chunk
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

        asyncio.run(_drive())

        # The disconnect watcher polls every 250ms. Give a generous
        # window for the watcher → cancel-token → persist hop to land.
        rows: list[ChatMessage] = []
        deadline = time.monotonic() + 6.0
        while time.monotonic() < deadline:
            with session_mod.SessionLocal() as s:
                rows = (
                    s.query(ChatMessage)
                    .filter(
                        ChatMessage.session_id == session_id,
                        ChatMessage.role == "assistant",
                    )
                    .all()
                )
            if rows:
                break
            time.sleep(0.1)

        assert rows, "assistant row should be persisted after TCP disconnect"
        assert len(rows) == 1
        row = rows[0]
        assert row.stopped_at is not None, "stopped_at must be set on cancelled stream"
        assert row.content == "partial-"
    finally:
        server.should_exit = True
        server_thread.join(timeout=5.0)
        session_mod.dispose_engine()
