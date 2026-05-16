"""Tests for services.reports.tombstone_report — the single canonical
operation that produces a tombstoned report row.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from openlia_server.db.models.content import RepoItem, Report, ReportVersion
from openlia_server.db.models.graph import GraphArtifactSummary
from openlia_server.services.reports import tombstone_report
from sqlalchemy.orm import Session


def _mk_report(
    db: Session,
    *,
    report_id: str | None = None,
    user_id: str | None = "u-1",
    title: str = "AAPL — Initiation",
    body: str = "# Body markdown",
    structured: dict | None = None,
) -> Report:
    rid = report_id or f"r-{uuid.uuid4().hex[:8]}"
    row = Report(
        id=rid,
        user_id=user_id,
        department="equity_research",
        report_type="stock_initiation",
        title=title,
        subject="AAPL",
        content_markdown=body,
        content_structured=structured or {"cover": {"title": title}},
        model_ref="test-model",
    )
    db.add(row)
    db.flush()
    return row


def _mk_version(db: Session, *, report_id: str, version_number: int = 1) -> ReportVersion:
    v = ReportVersion(
        id=f"v-{uuid.uuid4().hex[:8]}",
        report_id=report_id,
        version_number=version_number,
        content_markdown="prior body",
        content_structured={"cover": {"title": "prior"}},
    )
    db.add(v)
    db.flush()
    return v


def _mk_repo_item(db: Session, *, report_id: str, user_id: str = "u-1") -> RepoItem:
    item = RepoItem(
        id=f"ri-{uuid.uuid4().hex[:8]}",
        user_id=user_id,
        report_id=report_id,
    )
    db.add(item)
    db.flush()
    return item


def _mk_graph_summary(db: Session, *, report_id: str, user_id: str = "u-1") -> GraphArtifactSummary:
    summary = GraphArtifactSummary(
        id=f"gs-{uuid.uuid4().hex[:8]}",
        user_id=user_id,
        artifact_kind="report",
        artifact_id=report_id,
        summary_text="Short summary text for recall.",
    )
    db.add(summary)
    db.flush()
    return summary


def test_tombstone_blanks_body_and_sets_expired_at(create_tables, db_session: Session) -> None:
    report = _mk_report(db_session)
    rid = report.id

    changed = tombstone_report(db_session, report_id=rid)

    assert changed is True
    db_session.flush()
    db_session.expire_all()
    row = db_session.get(Report, rid)
    assert row is not None
    assert row.content_markdown == ""
    assert row.content_structured == {}
    assert row.expired_at is not None
    assert isinstance(row.expired_at, datetime)


def test_tombstone_deletes_report_versions(create_tables, db_session: Session) -> None:
    report = _mk_report(db_session)
    _mk_version(db_session, report_id=report.id, version_number=1)
    _mk_version(db_session, report_id=report.id, version_number=2)

    tombstone_report(db_session, report_id=report.id)

    remaining = db_session.query(ReportVersion).filter(ReportVersion.report_id == report.id).count()
    assert remaining == 0


def test_tombstone_deletes_repo_items(create_tables, db_session: Session) -> None:
    report = _mk_report(db_session)
    _mk_repo_item(db_session, report_id=report.id, user_id="u-1")

    tombstone_report(db_session, report_id=report.id)

    remaining = db_session.query(RepoItem).filter(RepoItem.report_id == report.id).count()
    assert remaining == 0


def test_tombstone_deletes_graph_artifact_summary(create_tables, db_session: Session) -> None:
    report = _mk_report(db_session)
    _mk_graph_summary(db_session, report_id=report.id, user_id="u-1")

    tombstone_report(db_session, report_id=report.id)

    remaining = (
        db_session.query(GraphArtifactSummary)
        .filter(
            GraphArtifactSummary.artifact_kind == "report",
            GraphArtifactSummary.artifact_id == report.id,
        )
        .count()
    )
    assert remaining == 0


def test_tombstone_works_on_unsaved_report(create_tables, db_session: Session) -> None:
    """No RepoItem rows present — should still succeed."""
    report = _mk_report(db_session)

    changed = tombstone_report(db_session, report_id=report.id)

    assert changed is True


def test_tombstone_works_when_no_graph_summary(create_tables, db_session: Session) -> None:
    """No GraphArtifactSummary row — should still succeed."""
    report = _mk_report(db_session)

    changed = tombstone_report(db_session, report_id=report.id)

    assert changed is True


def test_tombstone_is_idempotent(create_tables, db_session: Session) -> None:
    report = _mk_report(db_session)
    rid = report.id

    first = tombstone_report(db_session, report_id=rid)
    expired_at_first = db_session.get(Report, rid).expired_at
    second = tombstone_report(db_session, report_id=rid)
    expired_at_second = db_session.get(Report, rid).expired_at

    assert first is True
    assert second is False
    assert expired_at_first == expired_at_second


def test_tombstone_missing_report_returns_false(create_tables, db_session: Session) -> None:
    changed = tombstone_report(db_session, report_id="does-not-exist")
    assert changed is False


def test_tombstone_does_not_touch_other_reports(create_tables, db_session: Session) -> None:
    keep = _mk_report(db_session, title="Keep me alive")
    target = _mk_report(db_session, title="Tombstone me")
    _mk_version(db_session, report_id=keep.id)
    _mk_repo_item(db_session, report_id=keep.id)
    _mk_graph_summary(db_session, report_id=keep.id)

    tombstone_report(db_session, report_id=target.id)

    db_session.expire_all()
    keep_row = db_session.get(Report, keep.id)
    assert keep_row.content_markdown == "# Body markdown"
    assert keep_row.expired_at is None
    assert db_session.query(ReportVersion).filter(ReportVersion.report_id == keep.id).count() == 1
    assert db_session.query(RepoItem).filter(RepoItem.report_id == keep.id).count() == 1
    assert (
        db_session.query(GraphArtifactSummary)
        .filter(GraphArtifactSummary.artifact_id == keep.id)
        .count()
        == 1
    )


@pytest.mark.parametrize("user_id", [None, "u-1"])
def test_tombstone_works_on_owned_and_orphan_reports(
    create_tables, db_session: Session, user_id: str | None
) -> None:
    """The service does not gate on user_id — orphans (user_id=None) are
    legitimate inputs from the sweep's regular branch."""
    report = _mk_report(db_session, user_id=user_id)
    changed = tombstone_report(db_session, report_id=report.id)
    assert changed is True
