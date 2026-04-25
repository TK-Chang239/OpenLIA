"""Phase 1b NEW-1b-09 — ORM-level contract for rs_classification_log."""

from __future__ import annotations

from datetime import UTC, datetime

from openlia_server.db.models.dashboard import RsClassificationLog
from sqlalchemy import inspect
from sqlalchemy.orm import Session


def test_rs_classification_log_columns(engine, create_tables) -> None:
    insp = inspect(engine)
    cols = {c["name"]: c for c in insp.get_columns("rs_classification_log")}
    expected = {
        "id",
        "batch_id",
        "ticker",
        "model_ref",
        "item_count",
        "prompt_tokens",
        "completion_tokens",
        "latency_ms",
        "error",
        "created_at",
    }
    assert expected.issubset(set(cols.keys()))


def test_rs_classification_log_indexes(engine, create_tables) -> None:
    insp = inspect(engine)
    index_names = {idx["name"] for idx in insp.get_indexes("rs_classification_log")}
    assert {
        "ix_rs_classification_log_ticker_created",
        "ix_rs_classification_log_batch",
    }.issubset(index_names)


def test_rs_classification_log_insert_round_trip(create_tables, db_session: Session) -> None:
    now = datetime.now(UTC)
    row = RsClassificationLog(
        id="cl-1",
        batch_id="b-1",
        ticker="AAPL",
        model_ref="openai/gpt-4o-mini",
        item_count=5,
        prompt_tokens=123,
        completion_tokens=45,
        latency_ms=890,
        created_at=now,
    )
    db_session.add(row)
    db_session.commit()
    db_session.expire_all()

    reloaded = db_session.get(RsClassificationLog, "cl-1")
    assert reloaded is not None
    assert reloaded.ticker == "AAPL"
    assert reloaded.prompt_tokens == 123
    assert reloaded.error is None
