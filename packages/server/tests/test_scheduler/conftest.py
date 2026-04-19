"""Expose this test directory on sys.path so sibling test modules can
`from _fakes import ...` without relying on a tests.* package (which
does not exist under --import-mode=importlib)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from collections.abc import Iterator

import pytest
from openlia_server.db.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(eng)
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)


@pytest.fixture
def db_session(session_factory) -> Iterator[Session]:
    s = session_factory()
    try:
        yield s
    finally:
        s.close()
