"""Persistence layer for the OpenLIA server.

Re-exports Plan 1a public names: `Base`, `TimestampMixin`, the session
helpers, and `run_bootstrap` (backwards-compatible function alias for the
shipped `bootstrap()` entry point).

We deliberately do NOT re-export the `bootstrap` function under the name
`bootstrap` here, because doing so would shadow the same-named submodule
`openlia_server.db.bootstrap` for callers that write
`from openlia_server.db import bootstrap` and then access
`bootstrap.resolve_db_url()` (Alembic's `env.py` does exactly that). New
callers that want the function should use the deep import:

    from openlia_server.db.bootstrap import bootstrap

or call the alias:

    from openlia_server.db import run_bootstrap
"""

from openlia_server.db.base import Base, TimestampMixin
from openlia_server.db.bootstrap import bootstrap as run_bootstrap
from openlia_server.db.session import (
    SessionLocal,
    configure_engine,
    dispose_engine,
    get_engine,
)

__all__ = [
    "Base",
    "SessionLocal",
    "TimestampMixin",
    "configure_engine",
    "dispose_engine",
    "get_engine",
    "run_bootstrap",
]
