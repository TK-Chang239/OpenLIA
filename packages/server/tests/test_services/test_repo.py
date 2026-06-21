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


def test_save_rejects_other_users_report(db_session):
    owner = _user(db_session, "repo-owner")
    other = _user(db_session, "repo-other")
    r = _report(db_session, owner.id)
    # Another user must not be able to create a repo pointer at this report.
    with pytest.raises(LookupError):
        svc.save_to_repo(db_session, user_id=other.id, report_id=r.id)
    assert svc.list_items(db_session, user_id=other.id) == []


# ---------------------------------------------------------------------------
# v3 polymorphic target
# ---------------------------------------------------------------------------


def _v3_report(db_session, user_id: str):
    from openlia_server.db.models.report_v3 import ReportV3

    r = ReportV3(
        id=str(uuid.uuid4()),
        user_id=user_id,
        subject="RKLB.US",
        template_id="initiation_default",
        language="en",
        length="normal",
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        status="completed",
        error_message=None,
        created_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
    )
    db_session.add(r)
    db_session.commit()
    return r


def test_save_v3_creates_entry(db_session):
    u = _user(db_session, "v3-save")
    r = _v3_report(db_session, u.id)
    item = svc.save_v3_report_to_repo(db_session, user_id=u.id, v3_report_id=r.id)
    assert item.id is not None
    assert item.v3_report_id == r.id
    assert item.report_id is None
    assert item.pipeline_run_id is None


def test_save_v3_is_idempotent(db_session):
    u = _user(db_session, "v3-idem")
    r = _v3_report(db_session, u.id)
    a = svc.save_v3_report_to_repo(db_session, user_id=u.id, v3_report_id=r.id)
    b = svc.save_v3_report_to_repo(db_session, user_id=u.id, v3_report_id=r.id)
    assert a.id == b.id


def test_unsave_v3_removes_entry(db_session):
    u = _user(db_session, "v3-unsave")
    r = _v3_report(db_session, u.id)
    svc.save_v3_report_to_repo(db_session, user_id=u.id, v3_report_id=r.id)
    svc.unsave_v3_report_from_repo(db_session, user_id=u.id, v3_report_id=r.id)
    assert svc.is_v3_report_saved(db_session, user_id=u.id, v3_report_id=r.id) is False


def test_save_v3_raises_on_missing_report(db_session):
    u = _user(db_session, "v3-missing")
    with pytest.raises(LookupError):
        svc.save_v3_report_to_repo(db_session, user_id=u.id, v3_report_id="nope")


def test_save_v3_raises_when_owned_by_other_user(db_session):
    owner = _user(db_session, "v3-owner")
    intruder = _user(db_session, "v3-intruder")
    r = _v3_report(db_session, owner.id)
    with pytest.raises(LookupError):
        svc.save_v3_report_to_repo(db_session, user_id=intruder.id, v3_report_id=r.id)


def test_v3_save_is_isolated_from_v1_save(db_session):
    """Saving a v3 report and a v1 report in the same user's repo
    yields two distinct rows, each pointing at the right target."""
    u = _user(db_session, "v3-v1-mix")
    v1 = _report(db_session, u.id)
    v3 = _v3_report(db_session, u.id)
    svc.save_to_repo(db_session, user_id=u.id, report_id=v1.id)
    svc.save_v3_report_to_repo(db_session, user_id=u.id, v3_report_id=v3.id)
    rows = svc.list_items(db_session, user_id=u.id)
    assert len(rows) == 2
    v1_rows = [r for r in rows if r.report_id is not None]
    v3_rows = [r for r in rows if r.v3_report_id is not None]
    assert len(v1_rows) == 1 and v1_rows[0].report_id == v1.id
    assert len(v3_rows) == 1 and v3_rows[0].v3_report_id == v3.id


# ---------------------------------------------------------------------------
# EU v2 polymorphic target
# ---------------------------------------------------------------------------


def _eu_report(db_session, user_id: str):
    from openlia_server.db.models.report_eu import ReportEu

    r = ReportEu(
        id=str(uuid.uuid4()),
        user_id=user_id,
        subject="RKLB.US",
        ticker="RKLB.US",
        trigger_kind="on_demand",
        fiscal_date=None,
        template_id="eu_default",
        language="en",
        length="normal",
        provider_kind="anthropic",
        model="m",
        status="completed",
        error_message=None,
        created_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        cover_json=None,
        reasoning_effort=None,
    )
    db_session.add(r)
    db_session.commit()
    return r


def test_save_eu_creates_entry(db_session):
    u = _user(db_session, "eu-save")
    r = _eu_report(db_session, u.id)
    item = svc.save_eu_report_to_repo(db_session, user_id=u.id, eu_report_id=r.id)
    assert item.id is not None
    assert item.eu_v2_report_id == r.id
    assert item.report_id is None
    assert item.pipeline_run_id is None
    assert item.v3_report_id is None


def test_save_eu_is_idempotent(db_session):
    u = _user(db_session, "eu-idem")
    r = _eu_report(db_session, u.id)
    a = svc.save_eu_report_to_repo(db_session, user_id=u.id, eu_report_id=r.id)
    b = svc.save_eu_report_to_repo(db_session, user_id=u.id, eu_report_id=r.id)
    assert a.id == b.id
    assert len(svc.list_items(db_session, user_id=u.id)) == 1


def test_is_eu_report_saved(db_session):
    u = _user(db_session, "eu-issaved")
    r = _eu_report(db_session, u.id)
    assert svc.is_eu_report_saved(db_session, user_id=u.id, eu_report_id=r.id) is False
    svc.save_eu_report_to_repo(db_session, user_id=u.id, eu_report_id=r.id)
    assert svc.is_eu_report_saved(db_session, user_id=u.id, eu_report_id=r.id) is True


def test_unsave_eu_removes_entry(db_session):
    u = _user(db_session, "eu-unsave")
    r = _eu_report(db_session, u.id)
    svc.save_eu_report_to_repo(db_session, user_id=u.id, eu_report_id=r.id)
    svc.unsave_eu_report_from_repo(db_session, user_id=u.id, eu_report_id=r.id)
    assert svc.is_eu_report_saved(db_session, user_id=u.id, eu_report_id=r.id) is False


def test_save_eu_raises_on_missing_report(db_session):
    u = _user(db_session, "eu-missing")
    with pytest.raises(LookupError):
        svc.save_eu_report_to_repo(db_session, user_id=u.id, eu_report_id="nope")


def test_save_eu_raises_when_owned_by_other_user(db_session):
    owner = _user(db_session, "eu-owner")
    intruder = _user(db_session, "eu-intruder")
    r = _eu_report(db_session, owner.id)
    with pytest.raises(LookupError):
        svc.save_eu_report_to_repo(db_session, user_id=intruder.id, eu_report_id=r.id)


def test_saved_eu_report_appears_in_filtered_listing(db_session):
    """A saved EU report shows up in the Repository-page listing tagged
    with the eu_v2 engine so the frontend opens it as an eu_v2_report."""
    u = _user(db_session, "eu-listing")
    r = _eu_report(db_session, u.id)
    svc.save_eu_report_to_repo(db_session, user_id=u.id, eu_report_id=r.id)
    rows = svc.list_items_filtered(db_session, user_id=u.id)
    eu_rows = [row for row in rows if row.engine == "eu_v2"]
    assert len(eu_rows) == 1
    assert eu_rows[0].target_id == r.id
    assert eu_rows[0].department == "earnings_update"
    assert eu_rows[0].title == r.subject
