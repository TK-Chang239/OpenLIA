"""ORM models for the v2 Morning Briefing engine.

Forked from ``report_eu.py`` (itself a fork of ``report_v3.py``) for the
artifact tables, with Morning-Briefing-specific deltas and no revision
flow. MB runs are purely template/instructions-driven — there is no
ticker and no fiscal date — and are time-triggered (cron) rather than
event-triggered, so each run records which schedule fired it:

  - ``report_mb``                  the run itself, PLUS ``trigger_kind``
                                   (scheduled|on_demand), a nullable
                                   ``schedule_id`` (the ``mb_schedules``
                                   row that fired it), and a nullable
                                   ``instructions_id``. No ``ticker`` /
                                   ``fiscal_date``.
  - ``report_mb_sections``         one row per written section (no
                                   ``revision_id`` — MB v2 has no
                                   revisions; ``version`` stays for parity)
  - ``report_mb_charts``           one row per emitted chart spec (no
                                   ``revision_id``)
  - ``report_mb_citations``        unique-by-source_id bibliography roll-up
  - ``report_mb_tool_call_log``    per-turn audit trail
  - ``report_mb_templates``        built-in default + user-uploaded
                                   templates
  - ``report_mb_instructions``     free-form analyst methodology profiles

All user-scoped tables FK back to ``users.id`` and cascade on user
delete. Artifact child tables FK back to ``report_mb.id`` and cascade on
report delete. ``report_mb.schedule_id`` FKs to ``mb_schedules.id`` and
SET NULLs when the schedule is deleted, so historical runs survive a
schedule removal. The ``report_mb_`` prefix keeps these clear of the v3
``report_v3_`` and EU ``report_eu_`` tables.
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


class ReportMb(Base):
    """One v2 Morning Briefing run.

    Mirrors ``ReportEu`` minus the earnings-specific anchor columns:
    MB runs are never ticker-anchored, so there is no ``ticker`` or
    ``fiscal_date``. ``trigger_kind`` records whether the run was
    ``scheduled`` (fired by the scheduler from a cron ``mb_schedules``
    row) or ``on_demand`` (user initiated). ``schedule_id`` points at
    the firing schedule (nullable; SET NULL on schedule delete so the
    run survives). ``instructions_id`` pins the methodology profile.
    """

    __tablename__ = "report_mb"

    id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject: Mapped[str] = mapped_column(String(256), nullable=False)
    trigger_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    schedule_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("mb_schedules.id", ondelete="SET NULL"),
        nullable=True,
    )
    template_id: Mapped[str] = mapped_column(String(128), nullable=False)
    instructions_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
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
        PrimaryKeyConstraint("id", name="pk_report_mb"),
        Index("ix_report_mb_user_id_created_at", "user_id", "created_at"),
        Index("ix_report_mb_user_id_status", "user_id", "status"),
    )


class ReportMbSection(Base):
    """One section the model wrote via ``write_section``.

    Mirrors ``ReportEuSection``. MB v2 has no revision flow, so there is
    no ``revision_id`` column or FK. ``version`` is kept (default 1) and
    the unique constraint stays (report_id, section_id, version) for
    storage parity.
    """

    __tablename__ = "report_mb_sections"

    id: Mapped[int] = mapped_column(Integer, autoincrement=True, nullable=False)
    report_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("report_mb.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_id: Mapped[str] = mapped_column(String(128), nullable=False)
    section_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_report_mb_sections"),
        UniqueConstraint(
            "report_id",
            "section_id",
            "version",
            name="uq_report_mb_sections_report_id_section_id_version",
        ),
        Index("ix_report_mb_sections_report_id", "report_id"),
        Index(
            "ix_report_mb_sections_report_id_section_id_version",
            "report_id",
            "section_id",
            "version",
        ),
    )


class ReportMbChart(Base):
    """One chart spec the model emitted via ``emit_chart``.

    Mirrors ``ReportEuChart``. ``version`` is kept (default 1); unique
    constraint is (report_id, chart_id, version).
    """

    __tablename__ = "report_mb_charts"

    id: Mapped[int] = mapped_column(Integer, autoincrement=True, nullable=False)
    report_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("report_mb.id", ondelete="CASCADE"),
        nullable=False,
    )
    chart_id: Mapped[str] = mapped_column(String(128), nullable=False)
    chart_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    spec_json: Mapped[str] = mapped_column(Text, nullable=False)
    rendered_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_report_mb_charts"),
        UniqueConstraint(
            "report_id",
            "chart_id",
            "version",
            name="uq_report_mb_charts_report_id_chart_id_version",
        ),
        Index("ix_report_mb_charts_report_id", "report_id"),
        Index(
            "ix_report_mb_charts_report_id_chart_id_version",
            "report_id",
            "chart_id",
            "version",
        ),
    )


class ReportMbCitation(Base):
    """One bibliography entry — unique per ``source_id`` per report.

    Same shape as ``ReportEuCitation``.
    """

    __tablename__ = "report_mb_citations"

    id: Mapped[int] = mapped_column(Integer, autoincrement=True, nullable=False)
    report_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("report_mb.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    display_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provenance_json: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_report_mb_citations"),
        UniqueConstraint(
            "report_id",
            "source_id",
            name="uq_report_mb_citations_report_id_source_id",
        ),
        Index("ix_report_mb_citations_report_id", "report_id"),
    )


class ReportMbTemplate(Base):
    """MB v2 template — built-in default or user-uploaded.

    Same shape as ``ReportEuTemplate``. The migration seeds the single
    built-in ``mb_default`` row (``user_id`` NULL, ``is_builtin`` True);
    user uploads carry a UUID id, the owner's user_id, and the original
    upload artifacts for round-trip re-parse.
    """

    __tablename__ = "report_mb_templates"

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
        PrimaryKeyConstraint("id", name="pk_report_mb_templates"),
        Index("ix_report_mb_templates_user_id", "user_id"),
    )


class ReportMbInstructions(Base):
    """MB v2 instruction profile — free-form analyst methodology.

    Forked from ``ReportEuInstructions`` (same shape, MB-owned table).
    Distinct from a template: a template defines the report's *shape*
    (sections, order); an instruction profile is free-form prose guidance
    fed verbatim into the system prompt. ``body_text`` holds the
    server-extracted plain text; ``source_doc_blob`` / ``source_doc_mime``
    keep the original upload for re-extract. ``deleted_at`` drives
    owner-scoped soft-delete. The ``is_builtin`` / nullable ``user_id``
    columns mirror ``report_mb_templates`` for parity.
    """

    __tablename__ = "report_mb_instructions"

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
        PrimaryKeyConstraint("id", name="pk_report_mb_instructions"),
        Index("ix_report_mb_instructions_user_id", "user_id"),
    )


class ReportMbToolCallLog(Base):
    """Per-turn audit trail of every tool call the engine dispatched.

    Same shape as ``ReportEuToolCallLog``.
    """

    __tablename__ = "report_mb_tool_call_log"

    id: Mapped[int] = mapped_column(Integer, autoincrement=True, nullable=False)
    report_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("report_mb.id", ondelete="CASCADE"),
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
        PrimaryKeyConstraint("id", name="pk_report_mb_tool_call_log"),
        Index(
            "ix_report_mb_tool_call_log_report_id_turn_index",
            "report_id",
            "turn_index",
        ),
    )
