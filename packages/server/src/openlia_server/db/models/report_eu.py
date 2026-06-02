"""ORM models for the v2 Earnings Update engine.

Forked from ``report_v3.py`` for the artifact tables, with three
earnings-specific deltas and no revision flow:

  - ``report_eu``                  the run itself, PLUS ``ticker``,
                                   ``trigger_kind`` (scheduled|on_demand),
                                   and a nullable ``fiscal_date``
  - ``report_eu_sections``         one row per written section (no
                                   ``revision_id`` — EU v2 has no
                                   revisions; ``version`` stays for parity)
  - ``report_eu_charts``           one row per emitted chart spec (no
                                   ``revision_id``)
  - ``report_eu_citations``        unique-by-source_id bibliography roll-up
  - ``report_eu_tool_call_log``    per-turn audit trail
  - ``report_eu_templates``        built-in default + user-uploaded
                                   templates

Plus three control tables that drive the watchlist / calendar-sync /
auto-dispatch loop:

  - ``eu_v2_watchlist``            tickers a user tracks for earnings
  - ``eu_v2_earnings_schedule``    forward calendar built by the weekly
                                   sync; the dispatcher fires runs from it
  - ``eu_v2_settings``             per-user defaults + connector toggles

All user-scoped tables FK back to ``users.id`` and cascade on user
delete. Artifact child tables FK back to ``report_eu.id`` and cascade on
report delete. The ``report_eu_`` / ``eu_v2_`` prefixes keep these clear
of the v3 ``report_v3_`` and the v1 ``eu_*`` tables.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base, UTCDateTime


class ReportEu(Base):
    """One v2 Earnings Update run.

    Mirrors ``ReportV3`` plus the earnings-specific anchor columns:
    ``ticker`` is always present (EU runs are ticker-anchored),
    ``trigger_kind`` records whether the run was ``scheduled`` (fired by
    the dispatcher from the earnings calendar) or ``on_demand`` (user
    initiated), and ``fiscal_date`` is the release date the run covers
    (nullable for on-demand runs without a calendar match).
    """

    __tablename__ = "report_eu"

    id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject: Mapped[str] = mapped_column(String(256), nullable=False)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    fiscal_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    template_id: Mapped[str] = mapped_column(String(128), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    length: Mapped[str] = mapped_column(String(16), nullable=False)
    provider_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    # JSON-serialised CoverSpec from the model's ``set_cover`` tool call.
    cover_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # User-selected extended-thinking knob ("medium" | "high") at dispatch
    # time, or NULL when reasoning was off.
    reasoning_effort: Mapped[str | None] = mapped_column(String(16), nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_report_eu"),
        Index("ix_report_eu_user_id_created_at", "user_id", "created_at"),
        Index("ix_report_eu_user_id_status", "user_id", "status"),
    )


class ReportEuSection(Base):
    """One section the model wrote via ``write_section``.

    Mirrors ``ReportV3Section`` minus the revision linkage — EU v2 has no
    revision flow, so there is no ``revision_id`` column or FK. ``version``
    is kept (default 1) and the unique constraint stays
    (report_id, section_id, version) for storage parity with v3.
    """

    __tablename__ = "report_eu_sections"

    id: Mapped[int] = mapped_column(Integer, autoincrement=True, nullable=False)
    report_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("report_eu.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_id: Mapped[str] = mapped_column(String(128), nullable=False)
    section_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_report_eu_sections"),
        UniqueConstraint(
            "report_id",
            "section_id",
            "version",
            name="uq_report_eu_sections_report_id_section_id_version",
        ),
        Index("ix_report_eu_sections_report_id", "report_id"),
        Index(
            "ix_report_eu_sections_report_id_section_id_version",
            "report_id",
            "section_id",
            "version",
        ),
    )


class ReportEuChart(Base):
    """One chart spec the model emitted via ``emit_chart``.

    Mirrors ``ReportV3Chart`` minus the revision linkage. ``version`` is
    kept (default 1); unique constraint is (report_id, chart_id, version).
    """

    __tablename__ = "report_eu_charts"

    id: Mapped[int] = mapped_column(Integer, autoincrement=True, nullable=False)
    report_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("report_eu.id", ondelete="CASCADE"),
        nullable=False,
    )
    chart_id: Mapped[str] = mapped_column(String(128), nullable=False)
    chart_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    spec_json: Mapped[str] = mapped_column(Text, nullable=False)
    rendered_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_report_eu_charts"),
        UniqueConstraint(
            "report_id",
            "chart_id",
            "version",
            name="uq_report_eu_charts_report_id_chart_id_version",
        ),
        Index("ix_report_eu_charts_report_id", "report_id"),
        Index(
            "ix_report_eu_charts_report_id_chart_id_version",
            "report_id",
            "chart_id",
            "version",
        ),
    )


class ReportEuCitation(Base):
    """One bibliography entry — unique per ``source_id`` per report.

    Same shape as ``ReportV3Citation``.
    """

    __tablename__ = "report_eu_citations"

    id: Mapped[int] = mapped_column(Integer, autoincrement=True, nullable=False)
    report_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("report_eu.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    display_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provenance_json: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_report_eu_citations"),
        UniqueConstraint(
            "report_id",
            "source_id",
            name="uq_report_eu_citations_report_id_source_id",
        ),
        Index("ix_report_eu_citations_report_id", "report_id"),
    )


class ReportEuTemplate(Base):
    """EU v2 template — built-in default or user-uploaded.

    Same shape as ``ReportV3Template``. The migration seeds the single
    built-in ``eu_default`` row (``user_id`` NULL, ``is_builtin`` True);
    user uploads carry a UUID id, the owner's user_id, and the original
    upload artifacts for round-trip re-parse.
    """

    __tablename__ = "report_eu_templates"

    id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    template_spec_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_doc_blob: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    source_doc_mime: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_report_eu_templates"),
        Index("ix_report_eu_templates_user_id", "user_id"),
    )


class ReportEuInstructions(Base):
    """EU v2 instruction profile — free-form analyst methodology.

    Forked from ``ReportV3Instructions`` (same shape, EU-owned table).
    Distinct from a template: a template defines the report's *shape*
    (sections, order); an instruction profile is free-form prose guidance
    fed verbatim into the system prompt. ``body_text`` holds the
    server-extracted plain text; ``source_doc_blob`` / ``source_doc_mime``
    keep the original upload for re-extract. ``deleted_at`` drives
    owner-scoped soft-delete. The ``is_builtin`` / nullable ``user_id``
    columns mirror ``report_eu_templates`` for parity.
    """

    __tablename__ = "report_eu_instructions"

    id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    is_builtin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0")
    )
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_doc_blob: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    source_doc_mime: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_report_eu_instructions"),
        Index("ix_report_eu_instructions_user_id", "user_id"),
    )


class ReportEuToolCallLog(Base):
    """Per-turn audit trail of every tool call the engine dispatched.

    Same shape as ``ReportV3ToolCallLog``.
    """

    __tablename__ = "report_eu_tool_call_log"

    id: Mapped[int] = mapped_column(Integer, autoincrement=True, nullable=False)
    report_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("report_eu.id", ondelete="CASCADE"),
        nullable=False,
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    arguments_json: Mapped[str] = mapped_column(Text, nullable=False)
    result_summary: Mapped[str] = mapped_column(Text, nullable=False)
    provenance_json: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    output_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    wall_time_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_report_eu_tool_call_log"),
        Index(
            "ix_report_eu_tool_call_log_report_id_turn_index",
            "report_id",
            "turn_index",
        ),
    )


class EuV2WatchlistEntry(Base):
    """A ticker a user tracks for earnings-triggered reports."""

    __tablename__ = "eu_v2_watchlist"

    id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_eu_v2_watchlist"),
        UniqueConstraint("user_id", "ticker", name="uq_eu_v2_watchlist_user_ticker"),
        Index("ix_eu_v2_watchlist_user_id", "user_id"),
    )


class EuV2EarningsSchedule(Base):
    """Forward earnings calendar built by the weekly sync.

    One row per (user, ticker, fiscal_date). ``status`` walks
    pending -> reported (run fired) or skipped (gave up after retries).
    ``scheduled_run_at`` is when the dispatcher should fire the run.
    """

    __tablename__ = "eu_v2_earnings_schedule"

    id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    fiscal_date: Mapped[str] = mapped_column(String(32), nullable=False)
    release_timing: Mapped[str | None] = mapped_column(String(16), nullable=True)
    eps_estimate: Mapped[str | None] = mapped_column(String(32), nullable=True)
    revenue_estimate: Mapped[str | None] = mapped_column(String(32), nullable=True)
    scheduled_run_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    report_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_eu_v2_earnings_schedule"),
        UniqueConstraint(
            "user_id",
            "ticker",
            "fiscal_date",
            name="uq_eu_v2_earnings_schedule_user_ticker_fiscal",
        ),
        Index(
            "ix_eu_v2_earnings_schedule_status_run_at",
            "status",
            "scheduled_run_at",
        ),
        Index("ix_eu_v2_earnings_schedule_user_id", "user_id"),
    )


class EuV2Settings(Base):
    """Per-user EU v2 defaults + connector toggles."""

    __tablename__ = "eu_v2_settings"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    template_id: Mapped[str] = mapped_column(String(64), nullable=False)
    instructions_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    language: Mapped[str] = mapped_column(
        String(16), nullable=False, default="en", server_default="en"
    )
    length: Mapped[str] = mapped_column(
        String(16), nullable=False, default="normal", server_default="normal"
    )
    reasoning_effort: Mapped[str | None] = mapped_column(String(16), nullable=True)
    enabled_provider_ids: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list, server_default="[]"
    )
    web_search_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0")
    )
    # Opt-in: route this user's scheduled EU runs through the provider Batch
    # API (OpenAI / Anthropic) for ~50% cost at the cost of async delivery.
    # Default off keeps the live (on-demand) path. Honored only for
    # scheduled dispatch and only when the provider supports batch.
    batch_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    __table_args__ = (PrimaryKeyConstraint("user_id", name="pk_eu_v2_settings"),)
