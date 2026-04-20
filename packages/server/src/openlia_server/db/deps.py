"""Shared FastAPI dependencies for database sessions.

Route handlers used to call `db_session_factory()` directly and never close the
returned session. That leaks connections in production. Use
`make_session_dependency(factory)` to produce a FastAPI dependency that yields
a session and closes it on both success and error paths.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

from sqlalchemy.orm import Session as DBSession


def make_session_dependency(
    factory: Callable[[], DBSession],
) -> Callable[[], Iterator[DBSession]]:
    """Bind `factory` into a generator dependency that commits and closes.

    On successful handler return the session commits any pending writes. On
    exception it rolls back. Either way the session closes so the connection
    returns to the pool.
    """

    def session_dependency() -> Iterator[DBSession]:
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return session_dependency
