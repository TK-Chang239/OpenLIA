"""Verify user_prefs row defaults, FK to users, and one-to-one constraint."""

from __future__ import annotations

import uuid

import pytest
from openlia_server.db.models.auth import User
from openlia_server.db.models.config import UserPrefs
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def test_user_prefs_defaults(create_tables, db_session: Session) -> None:
    user = User(
        id=str(uuid.uuid4()),
        email="a@b.com",
        password_hash="x",
        display_name="A",
    )
    db_session.add(user)
    db_session.flush()
    prefs = UserPrefs(user_id=user.id)
    db_session.add(prefs)
    db_session.commit()

    db_session.refresh(prefs)
    assert prefs.theme == "system"
    assert prefs.notify_inapp is True
    assert prefs.notify_email is False
    assert prefs.display_language == "en"
    assert prefs.response_language == "en"
    assert prefs.report_language == "en"


def test_user_prefs_one_per_user(create_tables, db_session: Session) -> None:
    user = User(
        id=str(uuid.uuid4()),
        email="a@b.com",
        password_hash="x",
        display_name="A",
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserPrefs(user_id=user.id))
    db_session.add(UserPrefs(user_id=user.id))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_user_prefs_theme_check(create_tables, db_session: Session) -> None:
    user = User(
        id=str(uuid.uuid4()),
        email="a@b.com",
        password_hash="x",
        display_name="A",
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserPrefs(user_id=user.id, theme="chartreuse"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_user_prefs_cascade_on_user_delete(create_tables, db_session: Session) -> None:
    user = User(
        id=str(uuid.uuid4()),
        email="a@b.com",
        password_hash="x",
        display_name="A",
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserPrefs(user_id=user.id))
    db_session.commit()

    db_session.delete(user)
    db_session.commit()
    assert db_session.query(UserPrefs).count() == 0
