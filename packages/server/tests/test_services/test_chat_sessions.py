"""Unit tests for chat_sessions service."""

from __future__ import annotations

import uuid

import pytest
from openlia_server.db.models.content import ChatMessage
from openlia_server.services import chat_sessions as svc

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(db_session, email: str):
    """Thin wrapper — delegate to root make_user factory."""
    from datetime import UTC, datetime

    from openlia_server.db.models.auth import User

    u = User(
        id=f"user-{email}",
        email=email,
        display_name=email.split("@")[0],
        is_admin=False,
        is_disabled=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(u)
    db_session.commit()
    return u


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_session_returns_row(db_session):
    u = _make_user(db_session, "a@example.com")
    row = svc.create_session(db_session, user_id=u.id, department="secretary", title="hi")
    assert row.id is not None
    assert row.user_id == u.id
    assert row.department == "secretary"
    assert row.is_pinned is False
    assert row.is_archived is False


def test_list_sessions_excludes_other_users(db_session):
    a = _make_user(db_session, "list-a@example.com")
    b = _make_user(db_session, "list-b@example.com")
    svc.create_session(db_session, user_id=a.id, department="secretary", title="A")
    svc.create_session(db_session, user_id=b.id, department="secretary", title="B")
    rows = svc.list_sessions(db_session, user_id=a.id)
    assert len(rows) == 1
    assert rows[0].title == "A"


def test_rename_session_updates_title(db_session):
    u = _make_user(db_session, "rename@example.com")
    s = svc.create_session(db_session, user_id=u.id, department="secretary", title="x")
    svc.rename_session(db_session, session_id=s.id, user_id=u.id, new_title="renamed")
    db_session.refresh(s)
    assert s.title == "renamed"


def test_rename_session_rejects_other_users(db_session):
    a = _make_user(db_session, "rename-a@example.com")
    b = _make_user(db_session, "rename-b@example.com")
    s = svc.create_session(db_session, user_id=a.id, department="secretary", title="x")
    with pytest.raises(PermissionError):
        svc.rename_session(db_session, session_id=s.id, user_id=b.id, new_title="y")


def test_pin_toggle(db_session):
    u = _make_user(db_session, "pin@example.com")
    s = svc.create_session(db_session, user_id=u.id, department="secretary", title="x")
    svc.set_pinned(db_session, session_id=s.id, user_id=u.id, pinned=True)
    db_session.refresh(s)
    assert s.is_pinned is True


def test_archive_sets_flag(db_session):
    u = _make_user(db_session, "archive@example.com")
    s = svc.create_session(db_session, user_id=u.id, department="secretary", title="x")
    svc.archive_session(db_session, session_id=s.id, user_id=u.id)
    db_session.refresh(s)
    assert s.is_archived is True


def test_archive_hides_from_default_list(db_session):
    u = _make_user(db_session, "arc-list@example.com")
    s = svc.create_session(db_session, user_id=u.id, department="secretary", title="x")
    svc.archive_session(db_session, session_id=s.id, user_id=u.id)
    assert svc.list_sessions(db_session, user_id=u.id) == []
    assert len(svc.list_sessions(db_session, user_id=u.id, include_archived=True)) == 1


def test_unarchive_restores_session(db_session):
    u = _make_user(db_session, "unarchive@example.com")
    s = svc.create_session(db_session, user_id=u.id, department="secretary", title="x")
    svc.archive_session(db_session, session_id=s.id, user_id=u.id)
    svc.unarchive_session(db_session, session_id=s.id, user_id=u.id)
    db_session.refresh(s)
    assert s.is_archived is False


def test_delete_cascades_messages(db_session):
    u = _make_user(db_session, "del@example.com")
    s = svc.create_session(db_session, user_id=u.id, department="secretary", title="x")
    db_session.add(ChatMessage(id=str(uuid.uuid4()), session_id=s.id, role="user", content="hi"))
    db_session.commit()
    svc.delete_session(db_session, session_id=s.id, user_id=u.id)
    assert db_session.query(ChatMessage).filter_by(session_id=s.id).count() == 0


def test_list_messages_scopes_to_session_owner(db_session):
    a = _make_user(db_session, "msg-a@example.com")
    b = _make_user(db_session, "msg-b@example.com")
    s = svc.create_session(db_session, user_id=a.id, department="secretary", title="x")
    db_session.add(ChatMessage(id=str(uuid.uuid4()), session_id=s.id, role="user", content="hi"))
    db_session.commit()
    rows = svc.list_messages(db_session, session_id=s.id, user_id=a.id)
    assert len(rows) == 1
    with pytest.raises(PermissionError):
        svc.list_messages(db_session, session_id=s.id, user_id=b.id)


def test_get_session_not_found_raises(db_session):
    u = _make_user(db_session, "notfound@example.com")
    with pytest.raises(LookupError):
        svc.get_session(db_session, session_id="nonexistent", user_id=u.id)


def test_ensure_titled_replaces_default(db_session):
    u = _make_user(db_session, "auto-title@example.com")
    s = svc.create_session(db_session, user_id=u.id, department="secretary", title="New chat")
    svc.ensure_titled(db_session, session_id=s.id, first_user_text="What moved markets today?")
    db_session.refresh(s)
    assert s.title == "What moved markets today?"


def test_ensure_titled_truncates_to_48(db_session):
    u = _make_user(db_session, "auto-title-long@example.com")
    s = svc.create_session(db_session, user_id=u.id, department="secretary", title="New chat")
    long = "x" * 200
    svc.ensure_titled(db_session, session_id=s.id, first_user_text=long)
    db_session.refresh(s)
    assert s.title == "x" * 48


def test_ensure_titled_no_op_when_title_already_set(db_session):
    u = _make_user(db_session, "auto-title-set@example.com")
    s = svc.create_session(db_session, user_id=u.id, department="secretary", title="Already named")
    svc.ensure_titled(db_session, session_id=s.id, first_user_text="should not replace")
    db_session.refresh(s)
    assert s.title == "Already named"


def test_list_sessions_filters_by_department(db_session):
    u = _make_user(db_session, "dep-filter@example.com")
    svc.create_session(db_session, user_id=u.id, department="secretary", title="S")
    svc.create_session(db_session, user_id=u.id, department="morning_briefing", title="M")
    rows = svc.list_sessions(db_session, user_id=u.id, department="secretary")
    assert {r.title for r in rows} == {"S"}


def test_list_sessions_q_filter_lowercases(db_session):
    u = _make_user(db_session, "q-filter@example.com")
    svc.create_session(db_session, user_id=u.id, department="secretary", title="Alpha Bravo")
    svc.create_session(db_session, user_id=u.id, department="secretary", title="Charlie")
    rows = svc.list_sessions(db_session, user_id=u.id, q="alpha")
    assert {r.title for r in rows} == {"Alpha Bravo"}
