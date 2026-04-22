"""Root test conftest — makes db fixtures with tables available to all sub-packages."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

# 32 zero bytes encoded as base64 — valid key for all crypto operations in tests
_TEST_SECRET_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


@pytest.fixture(autouse=True)
def _secret_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    from openlia_server.db.crypto import _reset_cached_key

    monkeypatch.setenv("OPENLIA_SECRET_KEY", _TEST_SECRET_KEY)
    _reset_cached_key()
    yield
    _reset_cached_key()


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def db_url(db_path: Path) -> str:
    return f"sqlite:///{db_path}"


@pytest.fixture
def engine(db_url: str) -> Iterator[Engine]:
    import openlia_server.db.models  # noqa: F401 — register all models
    from openlia_server.db import session as session_mod
    from openlia_server.db.base import Base

    session_mod.configure_engine(db_url)
    eng = session_mod.get_engine()
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    session_mod.dispose_engine()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    from openlia_server.db import session as session_mod

    with session_mod.SessionLocal() as s:
        yield s


@pytest.fixture
def create_tables(engine: Engine) -> Iterator[None]:
    import openlia_server.db.models  # noqa: F401 — register all models
    from openlia_server.db.base import Base

    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def db_session_factory(engine: Engine):
    from openlia_server.db import session as session_mod

    return session_mod.SessionLocal


@pytest.fixture
def make_user(db_session):
    from openlia_server.db.models.auth import User
    from openlia_server.services.auth import passwords

    def _make(
        email: str = "alice@example.com",
        password: str | None = "correct horse battery staple",
        is_admin: bool = False,
        is_disabled: bool = False,
    ) -> User:
        user = User(
            id=f"user-{email}",
            email=email,
            display_name=email.split("@")[0],
            password_hash=passwords.hash_password(password) if password else None,
            is_admin=is_admin,
            is_disabled=is_disabled,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(user)
        db_session.commit()
        return user

    return _make
