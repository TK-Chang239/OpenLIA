"""ORM model for v2.2 equity-research per-user model assignments.

One row per (user, slot). The slot key is a string drawn from
`openlia.llm.runtime.report_v2.slots.V2Slot`; not enforced at the DB layer
to keep migrations cheap when the slot inventory evolves.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base, UTCDateTime


class ErV2ModelAssignment(Base):
    __tablename__ = "er_v2_model_assignments"

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    slot: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("llm_models.id", ondelete="RESTRICT"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "slot", name="pk_er_v2_model_assignments"),
    )
