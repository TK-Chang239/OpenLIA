"""Reports table gains: status (default 'complete'), failure_reason,
original_request (JSON), started_at. Existing rows backfill as
'complete'. Status is indexed."""

from __future__ import annotations

from openlia_server.db.models.content import Report
from sqlalchemy import inspect


def test_report_model_has_new_columns() -> None:
    mapper = inspect(Report)
    column_names = {c.name for c in mapper.columns}
    assert "status" in column_names
    assert "failure_reason" in column_names
    assert "original_request" in column_names
    assert "started_at" in column_names


def test_status_column_default_complete() -> None:
    mapper = inspect(Report)
    col = mapper.columns["status"]
    assert col.nullable is False
    # Default of "complete" so existing rows backfill correctly.
    assert col.server_default is not None or col.default is not None


def test_failure_reason_and_started_at_nullable() -> None:
    mapper = inspect(Report)
    assert mapper.columns["failure_reason"].nullable is True
    assert mapper.columns["started_at"].nullable is True
    assert mapper.columns["original_request"].nullable is True


def test_status_index_created(db_session_factory) -> None:
    with db_session_factory() as session:
        bind = session.get_bind()
        insp = inspect(bind)
        idx_names = [ix["name"] for ix in insp.get_indexes("reports")]
        assert "idx_reports_status" in idx_names
