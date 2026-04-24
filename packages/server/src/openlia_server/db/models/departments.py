"""Department-scoped tables.

Currently hosts per-user Equity Research configuration. Additional
department-specific tables (Earnings Update, Morning Briefing, etc.)
belong here as they are added.
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
    report_length: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    enabled_section_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    custom_sections: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)

    __table_args__ = (
        CheckConstraint(
            "report_length IN ('concise', 'normal', 'elaborative')",
            name="ck_eu_user_configs_length",
        ),
    )
