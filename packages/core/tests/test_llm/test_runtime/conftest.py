"""Ensure `_fakes.py` (sibling module with shared helper classes) is importable.

Pytest runs with --import-mode=importlib and no package __init__.py files,
so sibling test files cannot import each other by package path. This
conftest puts the current directory on sys.path so `from _fakes import X`
works inside every test module in this folder.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

_THIS_DIR = Path(__file__).parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))


# ---------------------------------------------------------------------------
# DB fixtures — needed by tests that touch openlia_server models directly
# (e.g. test_revision_runner_e2e.py seeds Report / ChatSession rows).
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def db_url(db_path: Path) -> str:
    return f"sqlite:///{db_path}"


@pytest.fixture
def engine(db_url: str, monkeypatch: pytest.MonkeyPatch):
    import openlia_server.db.models.register_all  # noqa: F401
    from openlia_server.db import session as session_mod
    from openlia_server.db.base import Base

    monkeypatch.delenv("OPENLIA_DB_URL", raising=False)
    session_mod.configure_engine(db_url)
    eng = session_mod.get_engine()
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    session_mod.dispose_engine()


@pytest.fixture
def db_session_factory(engine):
    from openlia_server.db import session as session_mod

    return session_mod.SessionLocal


@pytest.fixture
def test_user(db_session_factory):
    """Seed and return a minimal User row for FK constraints."""
    from openlia_server.db.models.auth import User

    now = datetime.now(UTC)
    user = User(
        id="u_1",
        email="test@example.com",
        display_name="Test User",
        password_hash=None,
        is_admin=False,
        is_disabled=False,
        created_at=now,
        updated_at=now,
    )
    with db_session_factory() as session:
        session.add(user)
        session.commit()
        session.refresh(user)
    return user
