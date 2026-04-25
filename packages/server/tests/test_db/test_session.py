from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, mapped_column


def test_base_has_naming_convention() -> None:
    from openlia_server.db.base import Base

    assert set(Base.metadata.naming_convention.keys()) == {"ix", "uq", "ck", "fk", "pk"}


def test_timestamp_mixin_columns_present() -> None:
    from openlia_server.db.base import Base, TimestampMixin, UTCDateTime

    class _Demo(Base, TimestampMixin):
        __tablename__ = "_demo"
        id: Mapped[int] = mapped_column(primary_key=True)

    cols = {c.name: c for c in _Demo.__table__.columns}
    assert isinstance(cols["created_at"].type, UTCDateTime)
    assert isinstance(cols["updated_at"].type, UTCDateTime)


def test_configure_engine_requires_url() -> None:
    from openlia_server.db import session as session_mod

    with pytest.raises(RuntimeError):
        session_mod.get_engine()


def test_configure_engine_creates_sqlite_engine(db_url: str) -> None:
    from openlia_server.db import session as session_mod

    session_mod.configure_engine(db_url)
    try:
        engine: Engine = session_mod.get_engine()
        assert engine.url.drivername == "sqlite"
    finally:
        session_mod.dispose_engine()


def test_sqlite_pragmas_applied(engine: Engine) -> None:
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert conn.execute(text("PRAGMA synchronous")).scalar() == 1  # NORMAL = 1
        assert conn.execute(text("PRAGMA busy_timeout")).scalar() == 5000


def test_session_local_usable(engine: Engine) -> None:
    from openlia_server.db import session as session_mod

    with session_mod.SessionLocal() as s:
        assert s.execute(text("SELECT 1")).scalar() == 1


def test_dispose_engine_is_idempotent() -> None:
    from openlia_server.db import session as session_mod

    session_mod.dispose_engine()  # no-op when nothing configured
    session_mod.dispose_engine()


def test_get_db_session_commits_on_success(engine: Engine, create_tables) -> None:
    """Plan 1a P1-1a-08: the FastAPI dependency must commit the session on clean exit."""
    from openlia_server.db import session as session_mod
    from openlia_server.db.models.infrastructure import ConfigStore

    gen = session_mod.get_db_session()
    s = next(gen)
    s.add(ConfigStore(key="gds.commit", value="yes"))
    # Normal iterator exhaustion triggers the session.commit() branch.
    with pytest.raises(StopIteration):
        next(gen)

    with session_mod.SessionLocal() as reader:
        row = reader.get(ConfigStore, "gds.commit")
        assert row is not None
        assert row.value == "yes"


def test_get_db_session_rolls_back_on_error(engine: Engine, create_tables) -> None:
    """Plan 1a P1-1a-08: the FastAPI dependency must roll back on exception."""
    from openlia_server.db import session as session_mod
    from openlia_server.db.models.infrastructure import ConfigStore

    gen = session_mod.get_db_session()
    s = next(gen)
    s.add(ConfigStore(key="gds.rollback", value="should-not-persist"))

    with pytest.raises(RuntimeError, match="boom"):
        gen.throw(RuntimeError("boom"))

    with session_mod.SessionLocal() as reader:
        row = reader.get(ConfigStore, "gds.rollback")
        assert row is None
