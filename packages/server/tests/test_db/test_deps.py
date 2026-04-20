"""Tests for db/deps.py — session_dependency helper."""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from openlia_server.db.deps import make_session_dependency
from sqlalchemy.orm import Session


class _RecordingSession:
    """Stand-in session that tracks commit/rollback/close calls."""

    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


def test_make_session_dependency_commits_and_closes_on_success():
    produced: list[_RecordingSession] = []

    def factory() -> _RecordingSession:
        s = _RecordingSession()
        produced.append(s)
        return s

    dep = make_session_dependency(factory)
    gen = dep()
    session = next(gen)
    assert session is produced[0]
    assert session.committed is False

    with pytest.raises(StopIteration):
        next(gen)
    assert session.committed is True
    assert session.rolled_back is False
    assert session.closed is True


def test_make_session_dependency_rolls_back_and_closes_on_exception():
    produced: list[_RecordingSession] = []

    def factory() -> _RecordingSession:
        s = _RecordingSession()
        produced.append(s)
        return s

    dep = make_session_dependency(factory)
    gen = dep()
    session = next(gen)

    with pytest.raises(RuntimeError, match="boom"):
        gen.throw(RuntimeError("boom"))

    assert session.committed is False
    assert session.rolled_back is True
    assert session.closed is True


def test_session_dependency_integrates_with_fastapi_handler(db_session: Session):
    """Handler receives a live session; close runs after response returns."""
    from openlia_server.db import session as session_mod

    closed_sessions: list[Session] = []

    original_close = Session.close

    def _track_close(self) -> None:  # type: ignore[no-untyped-def]
        closed_sessions.append(self)
        original_close(self)

    dep = make_session_dependency(session_mod.SessionLocal)

    app = FastAPI()

    @app.get("/probe")
    def probe(db: Session = Depends(dep)):
        return {"alive": db.is_active}

    @app.get("/boom")
    def boom(db: Session = Depends(dep)):
        raise HTTPException(status_code=500, detail="boom")

    Session.close = _track_close  # type: ignore[method-assign]
    try:
        client = TestClient(app, raise_server_exceptions=False)
        ok = client.get("/probe")
        assert ok.status_code == 200
        fail = client.get("/boom")
        assert fail.status_code == 500
    finally:
        Session.close = original_close  # type: ignore[method-assign]

    assert len(closed_sessions) >= 2
