"""Unit tests for repo service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import Report
from openlia_server.services import repo as svc


def _user(db_session, tag: str) -> User:
    u = User(
        id=str(uuid.uuid4()),
        email=f"{tag}@example.com",
        display_name=tag,
        is_admin=False,
        is_disabled=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(u)
    db_session.commit()
    return u


def _report(db_session, user_id: str) -> Report:
    r = Report(
        id=str(uuid.uuid4()),
        user_id=user_id,
        department="secretary",
        report_type="summary",
        title="Test",
        content_markdown="# Test",
        content_structured={},
        model_ref="gpt-4",
    )
    db_session.add(r)
    db_session.commit()
    return r


def test_save_creates_entry(db_session):
    u = _user(db_session, "save")
    r = _report(db_session, u.id)
    item = svc.save_to_repo(db_session, user_id=u.id, report_id=r.id)
    assert item.id is not None
    assert item.user_id == u.id
    assert item.report_id == r.id


def test_save_is_idempotent(db_session):
    u = _user(db_session, "idem")
    r = _report(db_session, u.id)
    a = svc.save_to_repo(db_session, user_id=u.id, report_id=r.id)
    b = svc.save_to_repo(db_session, user_id=u.id, report_id=r.id)
    assert a.id == b.id


def test_unsave_removes_entry(db_session):
    u = _user(db_session, "unsave")
    r = _report(db_session, u.id)
    svc.save_to_repo(db_session, user_id=u.id, report_id=r.id)
    svc.unsave_from_repo(db_session, user_id=u.id, report_id=r.id)
    assert svc.list_items(db_session, user_id=u.id) == []


def test_unsave_is_idempotent_when_absent(db_session):
    u = _user(db_session, "absent")
    r = _report(db_session, u.id)
    svc.unsave_from_repo(db_session, user_id=u.id, report_id=r.id)  # must not raise


def test_list_items_scoped_to_user(db_session):
    a = _user(db_session, "list-a")
    b = _user(db_session, "list-b")
    ra = _report(db_session, a.id)
    rb = _report(db_session, b.id)
    svc.save_to_repo(db_session, user_id=a.id, report_id=ra.id)
    svc.save_to_repo(db_session, user_id=b.id, report_id=rb.id)
    assert [i.report_id for i in svc.list_items(db_session, user_id=a.id)] == [ra.id]


def test_save_raises_on_missing_report(db_session):
    u = _user(db_session, "missing")
    with pytest.raises(LookupError):
        svc.save_to_repo(db_session, user_id=u.id, report_id="nonexistent")
