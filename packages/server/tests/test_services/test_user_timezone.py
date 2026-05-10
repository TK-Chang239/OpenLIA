"""Slice 1 — user timezone subsystem MVP.

Adds ``timezone`` + ``timezone_source`` to ``user_prefs``. Auto-detected
browser TZ overrides the stored value unless the user has manually
overridden via Settings — once manual, browser drift is ignored.
"""

from __future__ import annotations

import uuid

from openlia_server.db.models.auth import User
from openlia_server.services import user_prefs as svc
from sqlalchemy.orm import Session


def _user(db: Session) -> User:
    u = User(id=str(uuid.uuid4()), email="a@b.com", password_hash="x", display_name="A")
    db.add(u)
    db.flush()
    return u


def test_default_timezone_is_utc_with_auto_source(create_tables, db_session: Session) -> None:
    """A user who has never set a timezone gets UTC by default, with
    ``source='auto'`` so the first browser-detected TZ silently wins."""
    u = _user(db_session)
    prefs = svc.get_or_create(db_session, user_id=u.id)
    assert prefs.timezone == "UTC"
    assert prefs.timezone_source == "auto"


def test_auto_set_persists_and_keeps_source_auto(create_tables, db_session: Session) -> None:
    """Browser-detected TZ on login flows through ``set_timezone(source='auto')``."""
    u = _user(db_session)
    svc.set_timezone(db_session, user_id=u.id, timezone="America/Los_Angeles", source="auto")
    prefs = svc.get_or_create(db_session, user_id=u.id)
    assert prefs.timezone == "America/Los_Angeles"
    assert prefs.timezone_source == "auto"


def test_manual_set_locks_out_subsequent_auto_updates(
    create_tables, db_session: Session
) -> None:
    """Once the user picks a TZ in Settings, browser drift must not
    silently overwrite it."""
    u = _user(db_session)
    svc.set_timezone(db_session, user_id=u.id, timezone="Asia/Taipei", source="manual")
    # User travels; browser sends a different TZ on next login.
    svc.set_timezone(db_session, user_id=u.id, timezone="America/Los_Angeles", source="auto")
    prefs = svc.get_or_create(db_session, user_id=u.id)
    assert prefs.timezone == "Asia/Taipei"
    assert prefs.timezone_source == "manual"


def test_rejects_invalid_iana_zone(create_tables, db_session: Session) -> None:
    """Bogus tz string surfaces as ValueError, not a silent persist."""
    import pytest

    u = _user(db_session)
    with pytest.raises(ValueError):
        svc.set_timezone(db_session, user_id=u.id, timezone="Pacific/Atlantis", source="auto")
