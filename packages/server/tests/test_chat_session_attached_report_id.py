"""ChatSession gains an optional attached_report_id column; existing
sessions get NULL (backward compatible). An index is created on the
new column."""

from __future__ import annotations

from openlia_server.db.models.content import ChatSession
from sqlalchemy import inspect


def test_chat_session_model_has_attached_report_id_column() -> None:
    mapper = inspect(ChatSession)
    column_names = {c.name for c in mapper.columns}
    assert "attached_report_id" in column_names


def test_attached_report_id_is_nullable() -> None:
    mapper = inspect(ChatSession)
    col = mapper.columns["attached_report_id"]
    assert col.nullable is True


def test_attached_report_id_is_indexed(db_session_factory) -> None:
    """The migration adds an explicit index for the new column."""
    with db_session_factory() as session:
        bind = session.get_bind()
        insp = inspect(bind)
        idx_names = [ix["name"] for ix in insp.get_indexes("chat_sessions")]
        assert "idx_chat_sessions_attached_report_id" in idx_names
