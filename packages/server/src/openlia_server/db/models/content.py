"""Plan 1a Content tables (`database-design.md` §6).

Owns the chat session/message/attachment tables, the report + report_version
pair, the `repo_items` saved-to-repository join table (added by Plan 12),
portfolio holdings, and watchlists. See the spec for the full column list
and FK/cascade contracts. Legacy `Report.is_starred` and `Report.tags`
columns were dropped by migration
`2026-04-22-2200_repo_items_and_drop_legacy_report_cols.py`; starring is now
the presence of a `repo_items` row.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from openlia_server.db.base import Base, TimestampMixin, UTCDateTime


class ChatSession(Base, TimestampMixin):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    department: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("llm_models.id", ondelete="SET NULL"), nullable=True
    )
    # Per-session connector + skill toggles (chat-input "Tools" dropdown).
    # Empty list = nothing disabled. Filtered out at dispatcher build /
    # skill registry visibility, so disabled entries never reach the
    # router or the model.
    disabled_connector_ids: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default=text("'[]'")
    )
    disabled_skill_ids: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default=text("'[]'")
    )
    # Per-session composer choice: ``"concise"``, ``"normal"``, or
    # ``"detailed"``. ``NULL`` = no explicit choice (model default
    # discipline). The Secretary chat runtime injects a length directive
    # into the system prompt only for ``concise`` / ``detailed``.
    response_length: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Optional report bound to this session at creation (used by
    # "Ask in Secretary" handoffs from report viewers). ``NULL`` when
    # the session was created without an attached report.
    attached_report_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("reports.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )

    messages: Mapped[list[ChatMessage]] = relationship(
        "ChatMessage", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        Index("ix_chat_sessions_user_id_department", "user_id", "department"),
        Index("ix_chat_sessions_user_id_updated_at", "user_id", "updated_at"),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[list | None] = mapped_column(JSON, nullable=True)
    model_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    token_usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )
    stopped_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    __table_args__ = (Index("ix_chat_messages_session_id_created_at", "session_id", "created_at"),)


class ChatAttachment(Base):
    __tablename__ = "chat_attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    # Cached server-side extracted text for non-native-content paths (PDF
    # on non-pdf_native providers, all Office docs, decoded text files).
    # NULL when the attachment is passed to the provider as raw bytes
    # (images, native PDFs). See composer-attachments-design.md.
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_chat_attachments_message_id", "message_id"),)


class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    department: Mapped[str] = mapped_column(String(32), nullable=False)
    report_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(128), nullable=True)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    content_structured: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True
    )
    model_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    token_usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    generation_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Non-null when the report has been tombstoned: body fields blanked,
    # report_versions + repo_items + GraphArtifactSummary deleted. The row
    # itself remains as a chat-history anchor (EquityResearch artifact
    # card renders a tombstone). Both the nightly maintenance sweep and
    # the DELETE /reports/{id} route set this via the shared
    # services/reports.py::tombstone_report function.
    expired_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    # Background report generation fields (Task 6).
    # status: 'generating' | 'complete' | 'failed' | 'cancelled'. Sync paths
    # persist with 'complete' (services/reports.py); background paths set
    # 'generating' on stub-row create and transition on terminal events.
    # Legacy rows may carry NULL — kept nullable on the model for back-compat.
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Short reason string set on terminal failure/cancellation.
    failure_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Serialised GenerateReportIn body — used by the retry flow to
    # re-submit the same request without the client resending it.
    original_request: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Wall-clock time when the background task was submitted.
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    __table_args__ = (
        Index("ix_reports_user_id_department", "user_id", "department"),
        Index("ix_reports_user_id_created_at", "user_id", "created_at"),
        Index("ix_reports_subject", "subject"),
        Index("ix_reports_report_type", "report_type"),
        Index("ix_reports_expired_at", "expired_at"),
    )


class ReportVersion(Base):
    __tablename__ = "report_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    content_structured: Mapped[dict] = mapped_column(JSON, nullable=False)
    change_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "report_id",
            "version_number",
            name="uq_report_versions_report_id_version_number",
        ),
    )


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    shares: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    cost_basis: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("user_id", "ticker", name="uq_portfolio_holdings_user_id_ticker"),
    )


class Watchlist(Base, TimestampMixin):
    __tablename__ = "watchlists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_watchlists_user_id_name"),)


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    watchlist_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("watchlists.id", ondelete="CASCADE"), primary_key=True
    )
    ticker: Mapped[str] = mapped_column(String(16), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )


class RepoItem(Base):
    """Saved-report pointer. Polymorphic across four targets:

    - ``report_id`` -> v1 report (``reports.id``)
    - ``pipeline_run_id`` -> v2.2 pipeline run (``pipeline_runs.id``)
    - ``v3_report_id`` -> v3 equity-research report (``report_v3.id``)
    - ``eu_v2_report_id`` -> Earnings Update v2 report (``report_eu.id``)

    Exactly one is set on any given row, enforced by a CHECK
    constraint. Listing endpoints fan out and merge all four sources
    before returning to the frontend.
    """

    __tablename__ = "repo_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    report_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("reports.id", ondelete="CASCADE"), nullable=True
    )
    pipeline_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("pipeline_runs.id", ondelete="CASCADE"),
        nullable=True,
    )
    v3_report_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("report_v3.id", ondelete="CASCADE"),
        nullable=True,
    )
    eu_v2_report_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("report_eu.id", ondelete="CASCADE"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "report_id", name="uq_repo_items_user_report"),
        UniqueConstraint("user_id", "pipeline_run_id", name="uq_repo_items_user_pipeline_run"),
        UniqueConstraint("user_id", "v3_report_id", name="uq_repo_items_user_v3_report"),
        UniqueConstraint("user_id", "eu_v2_report_id", name="uq_repo_items_user_eu_report"),
        Index("ix_repo_items_user_id_created_at", "user_id", "created_at"),
        Index("ix_repo_items_user_id_v3_report_id", "user_id", "v3_report_id"),
        CheckConstraint(
            "((CASE WHEN report_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN pipeline_run_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN v3_report_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN eu_v2_report_id IS NOT NULL THEN 1 ELSE 0 END)) = 1",
            name="ck_repo_items_exactly_one_target",
        ),
    )


class PortfolioQuote(Base):
    """Latest quote per ticker, deduped across all users.

    Populated by JobType.PORTFOLIO_PRICE_REFRESH and the manual refresh
    route. Day-change is computed on read from ``last_price - previous_close``.
    """

    __tablename__ = "portfolio_quotes"

    ticker: Mapped[str] = mapped_column(String(32), primary_key=True)
    last_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    previous_close: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    day_open: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    day_high: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    day_low: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    quote_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)


class PortfolioQuoteIntraday(Base):
    """Intraday tick points captured by the scheduler. Wiped at session start."""

    __tablename__ = "portfolio_quote_intraday"

    ticker: Mapped[str] = mapped_column(String(32), primary_key=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime(), primary_key=True)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)

    __table_args__ = (Index("ix_portfolio_quote_intraday_ticker_ts", "ticker", "ts"),)


class PortfolioQuoteDaily(Base):
    """Canonical daily OHLCV series, populated by post-close fires and 5Y backfill."""

    __tablename__ = "portfolio_quote_daily"

    ticker: Mapped[str] = mapped_column(String(32), primary_key=True)
    trade_date: Mapped[datetime] = mapped_column(Date, primary_key=True)
    open: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    high: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    low: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    close: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (Index("ix_portfolio_quote_daily_ticker_date", "ticker", "trade_date"),)
