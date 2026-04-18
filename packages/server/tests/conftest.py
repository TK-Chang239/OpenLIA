"""Root test conftest — makes db fixtures with tables available to all sub-packages."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def db_url(db_path: Path) -> str:
    return f"sqlite:///{db_path}"


@pytest.fixture
def engine(db_url: str) -> Iterator[Engine]:
    from openlia_server.db import session as session_mod
    import openlia_server.db.models  # noqa: F401 — register all models
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
