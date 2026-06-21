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


def test_create_session_inherits_disabled_lists_from_last_session_in_dept(db_session):
    """Per-dept inheritance: a fresh session starts with the same toggles
    as the user's most recently updated session in the same department."""
    u = _make_user(db_session, "inh@example.com")
    older = svc.create_session(db_session, user_id=u.id, department="secretary", title="old")
    svc.set_session_disabled_lists(
        db_session,
        session_id=older.id,
        user_id=u.id,
        disabled_connector_ids=["c-x"],
        disabled_skill_ids=["s-y"],
    )
    new_row = svc.create_session(db_session, user_id=u.id, department="secretary", title="new")
    assert new_row.disabled_connector_ids == ["c-x"]
    assert new_row.disabled_skill_ids == ["s-y"]


def test_create_session_inheritance_is_per_department(db_session):
    """Different desks have different defaults — inheritance never crosses
    department boundaries."""
    u = _make_user(db_session, "inh2@example.com")
    secretary_old = svc.create_session(
        db_session, user_id=u.id, department="secretary", title="sec"
    )
    svc.set_session_disabled_lists(
        db_session,
        session_id=secretary_old.id,
        user_id=u.id,
        disabled_connector_ids=["c-eodhd"],
        disabled_skill_ids=None,
    )
    eq_new = svc.create_session(db_session, user_id=u.id, department="equity_research", title="eq")
    assert eq_new.disabled_connector_ids == []


def test_create_session_falls_back_to_empty_lists_when_no_prior_session(db_session):
    u = _make_user(db_session, "inh3@example.com")
    row = svc.create_session(db_session, user_id=u.id, department="secretary", title="t")
    assert row.disabled_connector_ids == []
    assert row.disabled_skill_ids == []
    assert row.response_length is None


def test_create_session_inherits_response_length_from_last_session(db_session):
    """The composer response-length picker carries to the next session in
    the same department."""
    u = _make_user(db_session, "rl-inh@example.com")
    older = svc.create_session(db_session, user_id=u.id, department="secretary", title="old")
    svc.set_session_response_length(
        db_session,
        session_id=older.id,
        user_id=u.id,
        response_length="concise",
    )
    new_row = svc.create_session(db_session, user_id=u.id, department="secretary", title="new")
    assert new_row.response_length == "concise"


def test_set_session_response_length_normal_clears_to_null(db_session):
    """``"normal"`` is stored as ``NULL`` so the runtime treats it as
    "no directive" without an extra branch."""
    u = _make_user(db_session, "rl-norm@example.com")
    row = svc.create_session(db_session, user_id=u.id, department="secretary", title="t")
    svc.set_session_response_length(
        db_session, session_id=row.id, user_id=u.id, response_length="detailed"
    )
    svc.set_session_response_length(
        db_session, session_id=row.id, user_id=u.id, response_length="normal"
    )
    db_session.refresh(row)
    assert row.response_length is None


def test_set_session_response_length_rejects_unknown_value(db_session):
    u = _make_user(db_session, "rl-bad@example.com")
    row = svc.create_session(db_session, user_id=u.id, department="secretary", title="t")
    with pytest.raises(ValueError):
        svc.set_session_response_length(
            db_session, session_id=row.id, user_id=u.id, response_length="huge"
        )


def test_set_session_response_length_rejects_other_users(db_session):
    u1 = _make_user(db_session, "rl-owner@example.com")
    u2 = _make_user(db_session, "rl-intruder@example.com")
    row = svc.create_session(db_session, user_id=u1.id, department="secretary", title="t")
    with pytest.raises(PermissionError):
        svc.set_session_response_length(
            db_session, session_id=row.id, user_id=u2.id, response_length="concise"
        )


def test_set_session_disabled_lists_persists_both(db_session):
    u = _make_user(db_session, "dl@example.com")
    row = svc.create_session(db_session, user_id=u.id, department="secretary", title="t")
    svc.set_session_disabled_lists(
        db_session,
        session_id=row.id,
        user_id=u.id,
        disabled_connector_ids=["c-1", "c-2"],
        disabled_skill_ids=["s-a"],
    )
    db_session.refresh(row)
    assert row.disabled_connector_ids == ["c-1", "c-2"]
    assert row.disabled_skill_ids == ["s-a"]


def test_set_session_disabled_lists_partial_update_ignores_none(db_session):
    """Passing `None` for one list leaves it untouched (PATCH semantics)."""
    u = _make_user(db_session, "dl2@example.com")
    row = svc.create_session(db_session, user_id=u.id, department="secretary", title="t")
    svc.set_session_disabled_lists(
        db_session,
        session_id=row.id,
        user_id=u.id,
        disabled_connector_ids=["c-1"],
        disabled_skill_ids=None,
    )
    svc.set_session_disabled_lists(
        db_session,
        session_id=row.id,
        user_id=u.id,
        disabled_connector_ids=None,
        disabled_skill_ids=["s-x"],
    )
    db_session.refresh(row)
    assert row.disabled_connector_ids == ["c-1"]
    assert row.disabled_skill_ids == ["s-x"]


def test_set_session_disabled_lists_rejects_other_users(db_session):
    u1 = _make_user(db_session, "owner@example.com")
    u2 = _make_user(db_session, "intruder@example.com")
    row = svc.create_session(db_session, user_id=u1.id, department="secretary", title="t")
    with pytest.raises(PermissionError):
        svc.set_session_disabled_lists(
            db_session,
            session_id=row.id,
            user_id=u2.id,
            disabled_connector_ids=["c-1"],
            disabled_skill_ids=None,
        )


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
    svc.ensure_titled(
        db_session, session_id=s.id, user_id=u.id, first_user_text="What moved markets today?"
    )
    db_session.refresh(s)
    assert s.title == "What moved markets today?"


def test_ensure_titled_truncates_to_48(db_session):
    u = _make_user(db_session, "auto-title-long@example.com")
    s = svc.create_session(db_session, user_id=u.id, department="secretary", title="New chat")
    long = "x" * 200
    svc.ensure_titled(db_session, session_id=s.id, user_id=u.id, first_user_text=long)
    db_session.refresh(s)
    assert s.title == "x" * 48


def test_ensure_titled_no_op_when_title_already_set(db_session):
    u = _make_user(db_session, "auto-title-set@example.com")
    s = svc.create_session(db_session, user_id=u.id, department="secretary", title="Already named")
    svc.ensure_titled(
        db_session, session_id=s.id, user_id=u.id, first_user_text="should not replace"
    )
    db_session.refresh(s)
    assert s.title == "Already named"


def test_ensure_titled_ignores_other_users_session(db_session):
    owner = _make_user(db_session, "auto-title-owner@example.com")
    other = _make_user(db_session, "auto-title-other@example.com")
    s = svc.create_session(db_session, user_id=owner.id, department="secretary", title="New chat")
    # A different user must not be able to retitle the owner's session.
    svc.ensure_titled(db_session, session_id=s.id, user_id=other.id, first_user_text="hijacked")
    db_session.refresh(s)
    assert s.title == "New chat"


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


def test_get_or_create_default_session_creates_when_none_exists(db_session):
    u = _make_user(db_session, "default-new@example.com")
    row = svc.get_or_create_default_session(db_session, user_id=u.id, department="secretary")
    assert row.user_id == u.id
    assert row.department == "secretary"
    assert row.title == "New chat"
    assert row.is_archived is False


def test_get_or_create_default_session_reuses_existing(db_session):
    u = _make_user(db_session, "default-reuse@example.com")
    existing = svc.create_session(
        db_session, user_id=u.id, department="secretary", title="Already there"
    )
    row = svc.get_or_create_default_session(db_session, user_id=u.id, department="secretary")
    assert row.id == existing.id
    assert row.title == "Already there"


def test_get_or_create_default_session_picks_oldest_non_archived(db_session):
    """Multiple sessions: pick the oldest unarchived one for stable identity."""
    from datetime import UTC, datetime, timedelta

    u = _make_user(db_session, "default-oldest@example.com")
    older = svc.create_session(db_session, user_id=u.id, department="secretary", title="older")
    newer = svc.create_session(db_session, user_id=u.id, department="secretary", title="newer")
    # SQLite func.now() is second-resolution, so back-to-back inserts collide.
    # Pin explicit timestamps so the "oldest" comparison is deterministic.
    base = datetime.now(UTC)
    older.created_at = base - timedelta(minutes=1)
    newer.created_at = base
    db_session.commit()

    row = svc.get_or_create_default_session(db_session, user_id=u.id, department="secretary")
    assert row.id == older.id


def test_get_or_create_default_session_skips_archived(db_session):
    u = _make_user(db_session, "default-arch@example.com")
    archived = svc.create_session(
        db_session, user_id=u.id, department="secretary", title="archived"
    )
    svc.archive_session(db_session, session_id=archived.id, user_id=u.id)
    row = svc.get_or_create_default_session(db_session, user_id=u.id, department="secretary")
    assert row.id != archived.id
    assert row.is_archived is False


def test_get_or_create_default_session_scopes_to_user(db_session):
    a = _make_user(db_session, "default-a@example.com")
    b = _make_user(db_session, "default-b@example.com")
    a_row = svc.get_or_create_default_session(db_session, user_id=a.id, department="secretary")
    b_row = svc.get_or_create_default_session(db_session, user_id=b.id, department="secretary")
    assert a_row.id != b_row.id
    assert a_row.user_id == a.id and b_row.user_id == b.id


def test_get_or_create_default_session_scopes_to_department(db_session):
    u = _make_user(db_session, "default-dept@example.com")
    sec = svc.get_or_create_default_session(db_session, user_id=u.id, department="secretary")
    mb = svc.get_or_create_default_session(db_session, user_id=u.id, department="morning_briefing")
    assert sec.id != mb.id
    assert sec.department == "secretary"
    assert mb.department == "morning_briefing"
