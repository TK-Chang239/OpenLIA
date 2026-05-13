"""Slice 4 — audit table + extraction-time preference.

Each nightly extraction run lands a row in ``graph_extraction_runs``.
The high-watermark = the latest ``started_at`` of a successful run per
user. Errors are recorded but do not advance the watermark. The
user's preferred extraction time (default 03:00) lives on UserPrefs
alongside the existing timezone column added by slice 1.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from openlia_server.db.models.auth import User
from openlia_server.services import graph_extraction_runs as svc
from openlia_server.services import user_prefs
from sqlalchemy.orm import Session


def _user(db: Session) -> User:
    uid = str(uuid.uuid4())
    u = User(id=uid, email=f"{uid}@example.test", password_hash="x", display_name="A")
    db.add(u)
    db.flush()
    return u


def test_default_graph_extraction_time_is_0300(create_tables, db_session: Session) -> None:
    """Spec default — see graph-memory-runtime.md."""
    u = _user(db_session)
    prefs = user_prefs.get_or_create(db_session, user_id=u.id)
    assert prefs.graph_extraction_time == "03:00"


def test_set_graph_extraction_time_persists(create_tables, db_session: Session) -> None:
    u = _user(db_session)
    user_prefs.set_graph_extraction_time(db_session, user_id=u.id, time="04:30")
    prefs = user_prefs.get_or_create(db_session, user_id=u.id)
    assert prefs.graph_extraction_time == "04:30"


def test_set_graph_extraction_time_rejects_malformed(create_tables, db_session: Session) -> None:
    u = _user(db_session)
    with pytest.raises(ValueError):
        user_prefs.set_graph_extraction_time(db_session, user_id=u.id, time="25:99")


def test_record_run_writes_audit_row(create_tables, db_session: Session) -> None:
    u = _user(db_session)
    run = svc.record_run_start(db_session, user_id=u.id, model_id="m-quick")
    assert run.id
    assert run.user_id == u.id
    assert run.started_at is not None
    assert run.finished_at is None
    assert run.error is None


def test_finish_run_marks_success(create_tables, db_session: Session) -> None:
    u = _user(db_session)
    run = svc.record_run_start(db_session, user_id=u.id, model_id="m-quick")
    svc.record_run_finish(
        db_session,
        run_id=run.id,
        proposals_inserted=3,
        sessions_processed=2,
    )
    refreshed = svc.get_run(db_session, run_id=run.id)
    assert refreshed.finished_at is not None
    assert refreshed.proposals_inserted == 3
    assert refreshed.sessions_processed == 2
    assert refreshed.error is None


def test_finish_run_records_error(create_tables, db_session: Session) -> None:
    u = _user(db_session)
    run = svc.record_run_start(db_session, user_id=u.id, model_id="m-quick")
    svc.record_run_finish(db_session, run_id=run.id, error="rate_limit")
    refreshed = svc.get_run(db_session, run_id=run.id)
    assert refreshed.error == "rate_limit"
    assert refreshed.finished_at is not None


def test_high_watermark_returns_latest_successful(create_tables, db_session: Session) -> None:
    """Watermark = the start time of the most recent successful run.
    Failed runs (error != None) must not advance it — otherwise an
    LLM outage silently drops yesterday's chat from the next extraction."""
    u = _user(db_session)
    older = svc.record_run_start(db_session, user_id=u.id, model_id="m")
    older.started_at = datetime.now(UTC) - timedelta(days=2)
    svc.record_run_finish(db_session, run_id=older.id, proposals_inserted=1)

    newer_failed = svc.record_run_start(db_session, user_id=u.id, model_id="m")
    newer_failed.started_at = datetime.now(UTC) - timedelta(hours=1)
    svc.record_run_finish(db_session, run_id=newer_failed.id, error="oops")

    wm = svc.high_watermark(db_session, user_id=u.id)
    # Watermark must be the older successful run, not the recent failure.
    assert wm == older.started_at


def test_high_watermark_is_none_for_user_with_no_successful_runs(
    create_tables, db_session: Session
) -> None:
    u = _user(db_session)
    assert svc.high_watermark(db_session, user_id=u.id) is None


def test_runs_are_scoped_per_user(create_tables, db_session: Session) -> None:
    """Bob's extraction run history must not leak into Alice's watermark."""
    alice = _user(db_session)
    bob = _user(db_session)
    bob_run = svc.record_run_start(db_session, user_id=bob.id, model_id="m")
    bob_run.started_at = datetime.now(UTC) - timedelta(hours=1)
    svc.record_run_finish(db_session, run_id=bob_run.id, proposals_inserted=1)

    assert svc.high_watermark(db_session, user_id=alice.id) is None
    assert svc.high_watermark(db_session, user_id=bob.id) == bob_run.started_at
