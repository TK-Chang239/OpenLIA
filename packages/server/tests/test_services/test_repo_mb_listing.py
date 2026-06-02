"""Repo save/unsave/list integration for Morning Briefing v2 reports.

Mirrors the EU v2 repo coverage: save creates exactly one polymorphic
``repo_items`` pointer (idempotent on repeat), the filtered listing fans the
saved MB report into a ``RepoRow`` with department ``"morning_briefing"``, and
unsave removes the pointer.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import RepoItem
from openlia_server.db.models.report_mb import ReportMb
from openlia_server.services import repo as svc
from sqlalchemy import select


def _user(db_session, tag: str = "mb") -> User:
    u = User(
        id=str(uuid.uuid4()),
        email=f"{tag}-{uuid.uuid4().hex[:6]}@example.com",
        display_name=tag,
        is_admin=False,
        is_disabled=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(u)
    db_session.commit()
    return u


def _mb_report(db_session, user_id: str, *, subject: str = "Pre-market briefing - 2026-06-02"):
    row = ReportMb(
        id=str(uuid.uuid4()),
        user_id=user_id,
        subject=subject,
        trigger_kind="scheduled",
        schedule_id=None,
        template_id="mb_default",
        instructions_id=None,
        language="en",
        length="normal",
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        status="completed",
        error_message=None,
        created_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        cover_json=None,
        reasoning_effort=None,
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_save_mb_report_creates_one_pointer_idempotent(db_session):
    u = _user(db_session)
    report = _mb_report(db_session, u.id)

    a = svc.save_mb_report_to_repo(db_session, user_id=u.id, mb_report_id=report.id)
    b = svc.save_mb_report_to_repo(db_session, user_id=u.id, mb_report_id=report.id)
    assert a.id == b.id
    assert a.mb_v2_report_id == report.id

    pointers = list(
        db_session.execute(select(RepoItem).where(RepoItem.mb_v2_report_id == report.id)).scalars()
    )
    assert len(pointers) == 1
    assert svc.is_mb_report_saved(db_session, user_id=u.id, mb_report_id=report.id) is True


def test_save_mb_report_unknown_id_raises(db_session):
    u = _user(db_session)
    with pytest.raises(LookupError):
        svc.save_mb_report_to_repo(db_session, user_id=u.id, mb_report_id="no-such-report")


def test_save_mb_report_other_user_raises(db_session):
    owner = _user(db_session, "owner")
    other = _user(db_session, "other")
    report = _mb_report(db_session, owner.id)
    with pytest.raises(LookupError):
        svc.save_mb_report_to_repo(db_session, user_id=other.id, mb_report_id=report.id)


def test_list_items_filtered_includes_saved_mb_report(db_session):
    u = _user(db_session)
    report = _mb_report(db_session, u.id, subject="Asia open briefing - 2026-06-02")
    svc.save_mb_report_to_repo(db_session, user_id=u.id, mb_report_id=report.id)

    rows = svc.list_items_filtered(db_session, user_id=u.id)
    mb_rows = [r for r in rows if r.engine == "mb_v2"]
    assert len(mb_rows) == 1
    row = mb_rows[0]
    assert row.department == "morning_briefing"
    assert row.target_id == report.id
    assert row.title == "Asia open briefing - 2026-06-02"


def test_list_items_filtered_department_filter_for_mb(db_session):
    u = _user(db_session)
    report = _mb_report(db_session, u.id)
    svc.save_mb_report_to_repo(db_session, user_id=u.id, mb_report_id=report.id)

    rows = svc.list_items_filtered(db_session, user_id=u.id, departments=["morning_briefing"])
    assert len(rows) == 1
    assert rows[0].engine == "mb_v2"
    assert rows[0].department == "morning_briefing"

    # A filter that excludes morning_briefing skips the MB fanout entirely.
    rows = svc.list_items_filtered(db_session, user_id=u.id, departments=["equity_research"])
    assert rows == []


def test_unsave_mb_report_removes_pointer(db_session):
    u = _user(db_session)
    report = _mb_report(db_session, u.id)
    svc.save_mb_report_to_repo(db_session, user_id=u.id, mb_report_id=report.id)

    svc.unsave_mb_report_from_repo(db_session, user_id=u.id, mb_report_id=report.id)

    pointers = list(
        db_session.execute(select(RepoItem).where(RepoItem.mb_v2_report_id == report.id)).scalars()
    )
    assert pointers == []
    assert svc.is_mb_report_saved(db_session, user_id=u.id, mb_report_id=report.id) is False
    assert svc.list_items_filtered(db_session, user_id=u.id) == []


def test_facets_counts_saved_mb_report(db_session):
    u = _user(db_session)
    report = _mb_report(db_session, u.id)
    svc.save_mb_report_to_repo(db_session, user_id=u.id, mb_report_id=report.id)

    f = svc.facets(db_session, user_id=u.id)
    slugs = {d["slug"]: d["count"] for d in f["departments"]}
    assert slugs.get("morning_briefing") == 1
