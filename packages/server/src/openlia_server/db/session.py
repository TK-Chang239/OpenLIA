"""SQLAlchemy engine + session helpers.

Centralizes engine creation (`get_engine`), session factory (`SessionLocal`),
and the `get_db_session` FastAPI dependency that commits on clean exit and
rolls back on exception. Spec reference: `database-design.md` §2 "Session
lifecycle".
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def configure_engine(url: str, *, echo: bool = False) -> Engine:
    global _engine, _SessionFactory

    if _engine is not None:
        _engine.dispose()

    connect_args: dict = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}

    _engine = create_engine(url, echo=echo, future=True, connect_args=connect_args)
    _register_sqlite_pragmas(_engine)
    _SessionFactory = sessionmaker(
        bind=_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError(
            "Engine not configured. Call openlia_server.db.session.configure_engine(url) first."
        )
    return _engine


def SessionLocal() -> Session:
    if _SessionFactory is None:
        raise RuntimeError("Session factory not configured. Call configure_engine(url) first.")
    return _SessionFactory()


def get_db_session():  # type: ignore[return]
    """FastAPI dependency that yields a session, commits on success, rolls back on error."""

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def dispose_engine() -> None:
    global _engine, _SessionFactory

    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionFactory = None


def _register_sqlite_pragmas(engine: Engine) -> None:
    if engine.url.drivername != "sqlite":
        return

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
        finally:
            cursor.close()
