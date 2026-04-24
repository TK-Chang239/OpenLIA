"""Unit tests for repo filter/sort/pagination + facets helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import RepoItem, Report
from openlia_server.services import repo as svc


def _mk_user(db) -> User:
    u = User(
        id=str(uuid.uuid4()),
        email=f"u-{uuid.uuid4().hex[:8]}@example.com",
        display_name="U",
        password_hash="x",
        is_admin=False,
    )
    db.add(u)
    db.flush()
    return u


def _mk_report(db, *, user_id: str, department: str, title: str, created_at: datetime) -> Report:
    r = Report(
        id=str(uuid.uuid4()),
        user_id=user_id,
        department=department,
        report_type=f"{department}_report",
        title=title,
        subject=None,
        content_markdown="md",
        content_structured={"title": title, "sections": []},
        model_ref="test-model",
    )
    db.add(r)
    db.flush()
    r.created_at = created_at
    db.flush()
    return r


def _save(db, *, user_id: str, report_id: str, saved_at: datetime) -> RepoItem:
    item = RepoItem(id=str(uuid.uuid4()), user_id=user_id, report_id=report_id, created_at=saved_at)
    db.add(item)
    db.flush()
    return item


@pytest.fixture()
def seeded(db_session):
    u = _mk_user(db_session)
    now = datetime(2026, 4, 10, 12, 0, tzinfo=UTC)
    reports = [
        _mk_report(
            db_session,
            user_id=u.id,
            department="equity_research",
            title="AAPL-initiation-coverage",
            created_at=now - timedelta(days=7),
        ),
        _mk_report(
            db_session,
            user_id=u.id,
            department="earnings_update",
            title="AAPL-earnings-q1-2026",
            created_at=now - timedelta(days=5),
        ),
        _mk_report(
            db_session,
            user_id=u.id,
            department="secretary",
            title="briefing-notes",
            created_at=now - timedelta(days=3),
        ),
        _mk_report(
            db_session,
            user_id=u.id,
            department="equity_research",
            title="MSFT-update",
            created_at=now - timedelta(days=1),
        ),
    ]
    saves = [
        _save(db_session, user_id=u.id, report_id=reports[0].id, saved_at=now - timedelta(days=6)),
        _save(db_session, user_id=u.id, report_id=reports[1].id, saved_at=now - timedelta(days=4)),
        _save(db_session, user_id=u.id, report_id=reports[2].id, saved_at=now - timedelta(days=2)),
        _save(db_session, user_id=u.id, report_id=reports[3].id, saved_at=now),
    ]
    db_session.commit()
    return {"user": u, "reports": reports, "saves": saves, "now": now}


def test_list_filtered_default_sort_is_saved_desc(db_session, seeded):
    rows = svc.list_items_filtered(db_session, user_id=seeded["user"].id)
    titles = [row.report.title for row in rows]
    assert titles == [
        "MSFT-update",
        "briefing-notes",
        "AAPL-earnings-q1-2026",
        "AAPL-initiation-coverage",
    ]


def test_list_filtered_department_multi_union(db_session, seeded):
    rows = svc.list_items_filtered(
        db_session, user_id=seeded["user"].id, departments=["equity_research", "secretary"]
    )
    titles = sorted(row.report.title for row in rows)
    assert titles == ["AAPL-initiation-coverage", "MSFT-update", "briefing-notes"]


def test_list_filtered_q_case_insensitive(db_session, seeded):
    rows = svc.list_items_filtered(db_session, user_id=seeded["user"].id, q="aapl")
    titles = sorted(row.report.title for row in rows)
    assert titles == ["AAPL-earnings-q1-2026", "AAPL-initiation-coverage"]


def test_list_filtered_generated_range_inclusive(db_session, seeded):
    now = seeded["now"]
    rows = svc.list_items_filtered(
        db_session,
        user_id=seeded["user"].id,
        generated_from=(now - timedelta(days=5)).date(),
        generated_to=(now - timedelta(days=3)).date(),
    )
    titles = sorted(row.report.title for row in rows)
    assert titles == ["AAPL-earnings-q1-2026", "briefing-notes"]


def test_list_filtered_pagination(db_session, seeded):
    page1 = svc.list_items_filtered(
        db_session, user_id=seeded["user"].id, page=1, page_size=2, sort="saved_desc"
    )
    page2 = svc.list_items_filtered(
        db_session, user_id=seeded["user"].id, page=2, page_size=2, sort="saved_desc"
    )
    assert [r.report.title for r in page1] == ["MSFT-update", "briefing-notes"]
    assert [r.report.title for r in page2] == [
        "AAPL-earnings-q1-2026",
        "AAPL-initiation-coverage",
    ]


def test_list_filtered_sort_filename_asc(db_session, seeded):
    rows = svc.list_items_filtered(db_session, user_id=seeded["user"].id, sort="filename_asc")
    titles = [row.report.title for row in rows]
    assert titles == sorted(titles)


def test_list_filtered_invalid_sort(db_session, seeded):
    with pytest.raises(ValueError):
        svc.list_items_filtered(db_session, user_id=seeded["user"].id, sort="bogus")  # type: ignore


def test_list_filtered_scoped_to_user(db_session, seeded):
    other = _mk_user(db_session)
    db_session.commit()
    rows = svc.list_items_filtered(db_session, user_id=other.id)
    assert rows == []


def test_facets_counts_by_department(db_session, seeded):
    f = svc.facets(db_session, user_id=seeded["user"].id)
    dep_counts = {d["slug"]: d["count"] for d in f["departments"]}
    assert dep_counts == {"equity_research": 2, "earnings_update": 1, "secretary": 1}
    assert f["total"] == 4


def test_facets_excludes_other_users(db_session, seeded):
    other = _mk_user(db_session)
    db_session.commit()
    f = svc.facets(db_session, user_id=other.id)
    assert f == {"departments": [], "total": 0}
