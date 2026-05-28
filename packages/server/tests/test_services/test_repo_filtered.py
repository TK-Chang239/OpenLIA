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
    titles = [row.title for row in rows]
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
    titles = sorted(row.title for row in rows)
    assert titles == ["AAPL-initiation-coverage", "MSFT-update", "briefing-notes"]


def test_list_filtered_q_case_insensitive(db_session, seeded):
    rows = svc.list_items_filtered(db_session, user_id=seeded["user"].id, q="aapl")
    titles = sorted(row.title for row in rows)
    assert titles == ["AAPL-earnings-q1-2026", "AAPL-initiation-coverage"]


def test_list_filtered_generated_range_inclusive(db_session, seeded):
    now = seeded["now"]
    rows = svc.list_items_filtered(
        db_session,
        user_id=seeded["user"].id,
        generated_from=(now - timedelta(days=5)).date(),
        generated_to=(now - timedelta(days=3)).date(),
    )
    titles = sorted(row.title for row in rows)
    assert titles == ["AAPL-earnings-q1-2026", "briefing-notes"]


def test_list_filtered_pagination(db_session, seeded):
    page1 = svc.list_items_filtered(
        db_session, user_id=seeded["user"].id, page=1, page_size=2, sort="saved_desc"
    )
    page2 = svc.list_items_filtered(
        db_session, user_id=seeded["user"].id, page=2, page_size=2, sort="saved_desc"
    )
    assert [r.title for r in page1] == ["MSFT-update", "briefing-notes"]
    assert [r.title for r in page2] == [
        "AAPL-earnings-q1-2026",
        "AAPL-initiation-coverage",
    ]


def test_list_filtered_sort_filename_asc(db_session, seeded):
    rows = svc.list_items_filtered(db_session, user_id=seeded["user"].id, sort="filename_asc")
    titles = [row.title for row in rows]
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


# ---------------------------------------------------------------------------
# v3 fanout (PR10)
# ---------------------------------------------------------------------------


def _mk_v3_report(
    db,
    *,
    user_id: str,
    subject: str,
    template_id: str = "initiation_default",
    created_at: datetime,
):
    from openlia_server.db.models.report_v3 import ReportV3

    r = ReportV3(
        id=str(uuid.uuid4()),
        user_id=user_id,
        subject=subject,
        template_id=template_id,
        language="en",
        length="normal",
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        status="completed",
        error_message=None,
        created_at=created_at,
        completed_at=created_at,
    )
    db.add(r)
    db.flush()
    return r


def _save_v3(db, *, user_id: str, v3_report_id: str, saved_at: datetime):
    item = RepoItem(
        id=str(uuid.uuid4()),
        user_id=user_id,
        v3_report_id=v3_report_id,
        created_at=saved_at,
    )
    db.add(item)
    db.flush()
    return item


@pytest.fixture()
def seeded_with_v3(db_session, seeded):
    """Extends ``seeded`` with two saved v3 equity-research reports."""
    u = seeded["user"]
    now = seeded["now"]
    v3a = _mk_v3_report(
        db_session,
        user_id=u.id,
        subject="RKLB.US",
        created_at=now - timedelta(hours=12),
    )
    v3b = _mk_v3_report(
        db_session,
        user_id=u.id,
        subject="NVDA.US",
        template_id="update_default",
        created_at=now - timedelta(days=2),
    )
    _save_v3(db_session, user_id=u.id, v3_report_id=v3a.id, saved_at=now - timedelta(hours=11))
    _save_v3(db_session, user_id=u.id, v3_report_id=v3b.id, saved_at=now - timedelta(days=2))
    db_session.commit()
    return {**seeded, "v3a": v3a, "v3b": v3b}


def test_list_filtered_merges_v1_and_v3_rows(db_session, seeded_with_v3):
    rows = svc.list_items_filtered(db_session, user_id=seeded_with_v3["user"].id)
    engines = [r.engine for r in rows]
    assert engines.count("v3") == 2
    assert engines.count("v1") == 4


def test_v3_rows_carry_engine_and_target_id(db_session, seeded_with_v3):
    rows = svc.list_items_filtered(db_session, user_id=seeded_with_v3["user"].id)
    v3_rows = [r for r in rows if r.engine == "v3"]
    subjects = {r.title for r in v3_rows}
    assert subjects == {"RKLB.US", "NVDA.US"}
    for r in v3_rows:
        assert r.target_id  # report_v3.id surfaces here
        assert r.department == "equity_research"
        assert r.filename.endswith(".pdf")


def test_default_sort_interleaves_v1_and_v3_by_saved_desc(db_session, seeded_with_v3):
    rows = svc.list_items_filtered(db_session, user_id=seeded_with_v3["user"].id)
    titles = [r.title for r in rows]
    # The most-recent v3 save (RKLB ~11h ago) lands between the two
    # most-recent v1 saves (MSFT-update at now, briefing-notes ~2d ago).
    assert titles[0] == "MSFT-update"
    assert titles[1] == "RKLB.US"


def test_filter_department_equity_research_excludes_unrelated_v1_rows(
    db_session, seeded_with_v3
):
    rows = svc.list_items_filtered(
        db_session,
        user_id=seeded_with_v3["user"].id,
        departments=["equity_research"],
    )
    # Should include the 2 v1 equity-research rows + the 2 v3 rows.
    titles = sorted(r.title for r in rows)
    assert titles == ["AAPL-initiation-coverage", "MSFT-update", "NVDA.US", "RKLB.US"]


def test_filter_department_secretary_skips_v3_fanout(db_session, seeded_with_v3):
    rows = svc.list_items_filtered(
        db_session,
        user_id=seeded_with_v3["user"].id,
        departments=["secretary"],
    )
    assert [r.title for r in rows] == ["briefing-notes"]
    assert all(r.engine == "v1" for r in rows)


def test_q_search_matches_v3_subject(db_session, seeded_with_v3):
    rows = svc.list_items_filtered(
        db_session, user_id=seeded_with_v3["user"].id, q="rklb"
    )
    titles = [r.title for r in rows]
    assert titles == ["RKLB.US"]
    assert rows[0].engine == "v3"


def test_pagination_across_merged_rows(db_session, seeded_with_v3):
    page1 = svc.list_items_filtered(
        db_session, user_id=seeded_with_v3["user"].id, page=1, page_size=3, sort="saved_desc"
    )
    page2 = svc.list_items_filtered(
        db_session, user_id=seeded_with_v3["user"].id, page=2, page_size=3, sort="saved_desc"
    )
    assert len(page1) == 3
    assert len(page2) == 3
    # Whole-set size = 4 v1 + 2 v3 = 6.
    combined_ids = {r.id for r in page1 + page2}
    assert len(combined_ids) == 6


def test_facets_counts_v3_under_equity_research(db_session, seeded_with_v3):
    f = svc.facets(db_session, user_id=seeded_with_v3["user"].id)
    dep_counts = {d["slug"]: d["count"] for d in f["departments"]}
    # 2 v1 equity-research + 2 v3 equity-research = 4
    assert dep_counts["equity_research"] == 4
    assert dep_counts["earnings_update"] == 1
    assert dep_counts["secretary"] == 1
    assert f["total"] == 6
