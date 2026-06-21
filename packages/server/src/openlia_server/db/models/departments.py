"""Department-scoped tables.

Hosts per-user Earnings Update configuration. Additional
department-specific tables (Morning Briefing, etc.) belong here as
they are added.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base, TimestampMixin


class EuWatchlistEntry(Base, TimestampMixin):
    """Per-user Earnings Update watchlist entry. One row per (user_id, ticker)."""

    __tablename__ = "eu_watchlist"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    company_name: Mapped[str] = mapped_column(String(256), nullable=False)
    next_earnings_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    release_timing: Mapped[str | None] = mapped_column(String(16), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "ticker", name="uq_eu_watchlist_user_ticker"),
        CheckConstraint(
            "release_timing IS NULL OR release_timing IN ('pre_market', 'post_market')",
            name="ck_eu_watchlist_release_timing",
        ),
        Index("ix_eu_watchlist_user", "user_id"),
    )


class EuUserConfig(Base, TimestampMixin):
    """Per-user Earnings Update config. One row per user."""

    __tablename__ = "eu_user_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    report_length: Mapped[str] = mapped_column(
        String(16), nullable=False, default="normal", server_default="normal"
    )
    enabled_section_ids: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default=text("'[]'")
    )
    custom_sections: Mapped[list[dict]] = mapped_column(
        JSON, nullable=False, default=list, server_default=text("'[]'")
    )

    __table_args__ = (
        CheckConstraint(
            "report_length IN ('concise', 'normal', 'elaborative')",
            name="ck_eu_user_configs_length",
        ),
    )
