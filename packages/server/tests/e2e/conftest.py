"""Shared e2e fixtures.

Every e2e test in this package spins up the full app via `create_app`,
which bypasses the production bootstrap path. The connector router is
gated by `require_active_admin`, which in personal mode resolves to the
synthetic `local` user — that user must therefore exist in the DB before
any /api/connectors/* call. This autouse fixture seeds it.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _seed_local_admin(db_session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.middleware.auth import LOCAL_USER_ID

    db_session.merge(
        User(
            id=LOCAL_USER_ID,
            email="local@openlia.local",
            display_name="Local",
            password_hash=None,
            is_admin=True,
            is_disabled=False,
            must_change_password=False,
        )
    )
    db_session.commit()
