"""Side-effect shim that imports every shipped ORM module.

Importing this module registers every model class on `Base.metadata` so
callers that need a complete schema (Alembic autogenerate, test-suite
`create_all`, CLI inspection tooling) can do so in one line:

    import openlia_server.db.models.register_all  # noqa: F401

Keep this file flat and side-effect-only. Do not re-export names from it;
callers should always import the owning submodule for type-level access.

Ordering is bottom-up along FK dependency chains so that any future tooling
that walks `__all__` in order (e.g. a diagnostic schema-dump) sees parents
before children.
"""

from __future__ import annotations

# Ordering: roots first (no FK dependencies), then dependents. `auth.User`
# and the `infrastructure` singletons are the parents of every downstream
# user-scoped table; registering them first keeps Alembic autogenerate's
# cross-reference emission deterministic. ruff's isort pass is disabled for
# this file in ruff.toml so the semantic order below is preserved.
from openlia_server.db.models import (  # noqa: F401
    auth,
    infrastructure,
    config,
    content,
    dashboard,
    departments,
    scheduler,
)
