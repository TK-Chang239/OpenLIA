"""Department-scoped tables.

Currently hosts per-user Equity Research configuration. Additional
department-specific tables (Earnings Update, Morning Briefing, etc.)
belong here as they are added.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
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
    selected_template_id_by_mode: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )
    # Phase 5f: per-mode override for the web search budget the model is
    # allowed to spend per report. Nullable; absent keys fall back to
    # the framework default (and ultimately to 8). Stored as a JSON
    # dict of {mode_key: positive_int}.
    web_search_budgets_by_mode: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=None
    )

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


class ErTemplate(Base, TimestampMixin):
    """User-uploaded or admin-published Equity Research report template.

    Bytes are immutable once persisted (re-uploading creates a new row).
    Metadata (name, compatible_modes) is mutable via metadata-only edits.
    """

    __tablename__ = "er_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_scope: Mapped[str] = mapped_column(String(16), nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    created_by_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    compatible_modes: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default=text("'[]'")
    )
    raw_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    raw_mime: Mapped[str] = mapped_column(String(128), nullable=False)
    raw_size_bytes: Mapped[int] = mapped_column(nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(nullable=False)
    estimated_tokens: Mapped[int] = mapped_column(nullable=False)

    __table_args__ = (
        CheckConstraint(
            "owner_scope IN ('global','user')",
            name="ck_er_templates_owner_scope",
        ),
        CheckConstraint(
            "(owner_scope = 'global' AND owner_user_id IS NULL) OR "
            "(owner_scope = 'user' AND owner_user_id IS NOT NULL)",
            name="ck_er_templates_scope_owner_consistency",
        ),
        Index("ix_er_templates_owner_scope_user", "owner_scope", "owner_user_id"),
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


class MbUserConfig(Base, TimestampMixin):
    """Per-user Morning Briefing config. One row per user."""

    __tablename__ = "mb_user_configs"

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
    section_topics: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )
    custom_sections: Mapped[list[dict]] = mapped_column(
        JSON, nullable=False, default=list, server_default=text("'[]'")
    )
    reference_portfolio: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0")
    )

    __table_args__ = (
        CheckConstraint(
            "report_length IN ('concise', 'normal', 'elaborative')",
            name="ck_mb_user_configs_length",
        ),
    )
