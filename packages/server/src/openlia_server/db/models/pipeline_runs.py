"""ORM model for v2.2 pipeline runs (Step 2 of the ClarifierModal wiring).

A pipeline run snapshots enough state to suspend the v2.2 orchestrator at
the Clarifier stage and pick it up later from a resume endpoint. The
caller persists ``composer_inputs`` and the raw template source so a
fresh worker can rebuild the inputs to ``RunnerV2.execute()`` after a
restart.

States mirror :class:`openlia.llm.runtime.report_v2.runner_v2.RunState`
verbatim; they are stored as plain strings to stay decoupled from the
core enum.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base, UTCDateTime


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    department: Mapped[str] = mapped_column(String(64), nullable=False)
    template_id: Mapped[str] = mapped_column(String(128), nullable=False)
    template_raw: Mapped[str] = mapped_column(Text, nullable=False)
    template_format: Mapped[str] = mapped_column(
        String(8), nullable=False, default="yaml", server_default=text("'yaml'")
    )
    composer_inputs: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    paused_at_stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    clarification_history: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    last_clarifier_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_clarifier_round: Mapped[int | None] = mapped_column(nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    paused_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    __table_args__ = (
        Index("ix_pipeline_runs_user_state", "user_id", "state"),
        Index("ix_pipeline_runs_session", "session_id"),
    )
