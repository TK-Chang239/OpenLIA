"""ORM model for v2.3 equity-research per-user model assignments.

One row per (user, slot). The slot key is a string drawn from
``openlia.llm.runtime.report_v2_3.slots.LLM_V23_SLOTS`` (the seven
LLM-using slots; VISUALIZE/ASSEMBLE are deterministic and have no
row). Not enforced at the DB layer to keep migrations cheap when the
slot inventory evolves.

Deliberately separate from ``er_v2_model_assignments`` — the v2.3 engine
is fully independent of v1/v2.2 per project memory, so the per-user
picker has its own table and routes.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base, UTCDateTime


class ErV23ModelAssignment(Base):
    __tablename__ = "er_v2_3_model_assignments"

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

    __table_args__ = (PrimaryKeyConstraint("user_id", "slot", name="pk_er_v2_3_model_assignments"),)
