"""Tests for UserPrefsService.get_or_create + update."""

import uuid

import pytest
from openlia_server.db.models.auth import User
from openlia_server.services import user_prefs as svc
from sqlalchemy.orm import Session


def test_get_or_create_creates_defaults(create_tables, db_session: Session) -> None:
    user = User(id=str(uuid.uuid4()), email="a@b.com", password_hash="x", display_name="A")
    db_session.add(user)
    db_session.flush()

    prefs = svc.get_or_create(db_session, user_id=user.id)
    assert prefs.theme == "system"
    assert prefs.notify_email is False


def test_update_persists_partial(create_tables, db_session: Session) -> None:
    user = User(id=str(uuid.uuid4()), email="a@b.com", password_hash="x", display_name="A")
    db_session.add(user)
    db_session.flush()

    svc.get_or_create(db_session, user_id=user.id)
    svc.update(
        db_session,
        user_id=user.id,
        theme="dark",
        notify_email=True,
    )
    prefs = svc.get_or_create(db_session, user_id=user.id)
    assert prefs.theme == "dark"
    assert prefs.notify_email is True
    assert prefs.notify_inapp is True  # unchanged


def test_update_rejects_invalid_theme(create_tables, db_session: Session) -> None:
    user = User(id=str(uuid.uuid4()), email="a@b.com", password_hash="x", display_name="A")
    db_session.add(user)
    db_session.flush()
    svc.get_or_create(db_session, user_id=user.id)

    with pytest.raises(ValueError):
        svc.update(db_session, user_id=user.id, theme="psychedelic")
