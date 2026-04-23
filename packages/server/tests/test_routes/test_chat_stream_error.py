"""A stub runner that raises must produce exactly one terminal chat.error frame."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from openlia.llm.exceptions import TierNotConfiguredError

from openlia_server.db import session as session_mod
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User


class _RaisingChatRunner:
    async def run(self, *, department_id, user_id, messages, attachments=None, cancel_token=None):
        raise TierNotConfiguredError("everyday")
        yield  # unreachable; makes this an async generator


@pytest.fixture
def stream_client(tmp_path, monkeypatch):
    from openlia_server.app import create_app

    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/e.db")
    session_mod.configure_engine(f"sqlite:///{tmp_path}/e.db")
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

    app = create_app(db_session_factory=session_mod.SessionLocal)
    app.state.chat_runner_factory = _RaisingChatRunner
    try:
        yield TestClient(app)
    finally:
        session_mod.dispose_engine()


def test_raising_runner_emits_single_terminal_error_frame(stream_client: TestClient) -> None:
    r = stream_client.post(
        "/departments/secretary/chat",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert r.status_code == 200
    frames = [
        json.loads(line[len("data: "):])
        for line in r.text.splitlines()
        if line.startswith("data: ")
    ]
    assert len(frames) == 1
    assert frames[0]["type"] == "chat.error"
    assert frames[0]["error_class"] == "TierNotConfiguredError"


def test_unauthenticated_chat_stream_returns_401(tmp_path, monkeypatch) -> None:
    from openlia_server.app import create_app

    monkeypatch.setenv("OPENLIA_MODE", "company")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/u.db")
    monkeypatch.setenv("OPENLIA_COOKIE_SECURE", "false")
    session_mod.configure_engine(f"sqlite:///{tmp_path}/u.db")
    Base.metadata.create_all(session_mod.get_engine())

    from openlia_server.services.auth import signup_policy

    with session_mod.SessionLocal() as s:
        signup_policy.seed_signup_policy(s, mode_flag="company")
        s.commit()

    app = create_app(db_session_factory=session_mod.SessionLocal)
    app.state.chat_runner_factory = _RaisingChatRunner
    client = TestClient(app)
    try:
        r = client.post(
            "/departments/secretary/chat",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 401
    finally:
        session_mod.dispose_engine()
