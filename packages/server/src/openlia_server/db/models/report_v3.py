"""ORM models for the v3 equity-research engine.

Five normalized tables persist one v3 run:

  - ``report_v3``                  the run itself (status, subject,
                                   template, language, error)
  - ``report_v3_sections``         one row per template section the
                                   model wrote (markdown with raw
                                   ``[^source_id]`` markers; rendering
                                   resolves to numbered footnotes)
  - ``report_v3_charts``           one row per emitted chart spec
                                   (rendered_url is populated by the
                                   render pipeline in Phase 2b)
  - ``report_v3_citations``        unique-by-source_id roll-up the
                                   bibliography is built from
                                   (display_index assigned at finalize)
  - ``report_v3_tool_call_log``    full per-turn audit trail for
                                   diagnostics + cost telemetry

All tables FK back to ``users.id`` and cascade on user delete. The
``report_id`` column on each child table FKs back to ``report_v3.id``
and cascades on report delete.

Naming uses the ``report_v3_`` prefix so they sit alongside the v2.3
``er_v2_3_`` tables without colliding.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base, UTCDateTime


class ReportV3(Base):
    """One v3 equity-research run.

    ``status`` mirrors the engine's ``RunStatus`` literal
    (``running`` / ``completed`` / ``failed``). ``subject`` is the
    ticker or topic the user requested. ``template_id`` is the
    template the run was bound to (built-in id today; UUID once
    user-uploaded templates land in Phase 1.5).
    """

    __tablename__ = "report_v3"

    id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject: Mapped[str] = mapped_column(String(256), nullable=False)
    template_id: Mapped[str] = mapped_column(String(128), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    length: Mapped[str] = mapped_column(String(16), nullable=False)
    provider_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_report_v3"),
        Index("ix_report_v3_user_id_created_at", "user_id", "created_at"),
        Index("ix_report_v3_user_id_status", "user_id", "status"),
    )


class ReportV3Section(Base):
    """One section the model wrote via ``write_section``.

    ``section_index`` is the section's position in the template's
    section list, used by the renderer for ordering. ``markdown`` is
    stored with the raw ``[^source_id]`` and ``{{chart:id}}`` markers
    intact — the citation rewriter (Phase 2b) resolves them at
    render time.
    """

    __tablename__ = "report_v3_sections"

    id: Mapped[int] = mapped_column(Integer, autoincrement=True, nullable=False)
    report_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("report_v3.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_id: Mapped[str] = mapped_column(String(128), nullable=False)
    section_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_report_v3_sections"),
        UniqueConstraint(
            "report_id",
            "section_id",
            name="uq_report_v3_sections_report_id_section_id",
        ),
        Index("ix_report_v3_sections_report_id", "report_id"),
    )


class ReportV3Chart(Base):
    """One chart spec the model emitted via ``emit_chart``.

    ``spec_json`` is the full ``ChartSpec`` Pydantic dump — the
    renderer reads it back via ``ChartSpec.model_validate_json``.
    ``rendered_url`` is populated by Phase 2b's chart_renderer; null
    until rendering completes.
    """

    __tablename__ = "report_v3_charts"

    id: Mapped[int] = mapped_column(Integer, autoincrement=True, nullable=False)
    report_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("report_v3.id", ondelete="CASCADE"),
        nullable=False,
    )
    chart_id: Mapped[str] = mapped_column(String(128), nullable=False)
    chart_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    spec_json: Mapped[str] = mapped_column(Text, nullable=False)
    rendered_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_report_v3_charts"),
        UniqueConstraint(
            "report_id",
            "chart_id",
            name="uq_report_v3_charts_report_id_chart_id",
        ),
        Index("ix_report_v3_charts_report_id", "report_id"),
    )


class ReportV3Citation(Base):
    """One bibliography entry — unique per ``source_id`` per report.

    Built from the ``CitationLedger`` at run completion. ``display_index``
    is the 1-based number the renderer shows readers (``[^1]``, ``[^2]``);
    assigned in the order the source first appears across the body
    sections in template order.
    """

    __tablename__ = "report_v3_citations"

    id: Mapped[int] = mapped_column(Integer, autoincrement=True, nullable=False)
    report_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("report_v3.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    display_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provenance_json: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_report_v3_citations"),
        UniqueConstraint(
            "report_id",
            "source_id",
            name="uq_report_v3_citations_report_id_source_id",
        ),
        Index("ix_report_v3_citations_report_id", "report_id"),
    )


class ReportV3ToolCallLog(Base):
    """Per-turn audit trail of every tool call the engine dispatched.

    Holds enough detail to reconstruct what the model did during a
    run: arguments, summary, provenance, token / time telemetry, and
    the assigned ``source_id`` (when the call produced one). Distinct
    from ``report_v3_citations`` because a single source_id is the
    bibliography view; this table is the call-by-call audit view.
    """

    __tablename__ = "report_v3_tool_call_log"

    id: Mapped[int] = mapped_column(Integer, autoincrement=True, nullable=False)
    report_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("report_v3.id", ondelete="CASCADE"),
        nullable=False,
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    arguments_json: Mapped[str] = mapped_column(Text, nullable=False)
    result_summary: Mapped[str] = mapped_column(Text, nullable=False)
    provenance_json: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wall_time_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_report_v3_tool_call_log"),
        Index(
            "ix_report_v3_tool_call_log_report_id_turn_index",
            "report_id",
            "turn_index",
        ),
    )
