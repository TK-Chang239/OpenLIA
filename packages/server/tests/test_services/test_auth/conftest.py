"""Shared fixtures for services.auth tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from openlia_server.db.models.auth import User
from openlia_server.services.auth import passwords


@pytest.fixture
def make_user(db_session):
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
