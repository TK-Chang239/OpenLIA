"""ORM model for v2.3 equity-research suspended-run state.

One row per active or suspended pipeline run, keyed by `run_id` (UUID).
The `state_json` column holds the full `ReportState` payload serialized by
`ReportState.model_dump_json()`; subsequent loads round-trip via
`ReportState.model_validate_json()`.

The status column is denormalized from state_json so callers can list /
filter runs (e.g. "show all WAITING_ON_USER runs for this user") without
deserializing every row.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, PrimaryKeyConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base, UTCDateTime


class ErV23RunState(Base):
    __tablename__ = "er_v2_3_run_state"

    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    state_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("run_id", name="pk_er_v2_3_run_state"),
        Index("ix_er_v2_3_run_state_user_id_status", "user_id", "status"),
    )
