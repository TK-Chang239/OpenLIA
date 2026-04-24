"""Department-scoped tables.

Currently hosts per-user Equity Research configuration. Additional
department-specific tables (Earnings Update, Morning Briefing, etc.)
belong here as they are added.
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base, TimestampMixin


class ErUserConfig(Base, TimestampMixin):
    """Per-user Equity Research configuration (one row per user)."""

    __tablename__ = "er_user_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    report_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    report_length: Mapped[str] = mapped_column(String(16), nullable=False)
    sections_by_mode: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    custom_sections_by_mode: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        CheckConstraint(
            "report_mode IN ('stock_initiation','stock_update','sector_research')",
            name="ck_er_user_configs_report_mode",
        ),
        CheckConstraint(
            "report_length IN ('concise','normal','elaborative')",
            name="ck_er_user_configs_report_length",
        ),
        Index("ix_er_user_configs_user_id", "user_id"),
    )
