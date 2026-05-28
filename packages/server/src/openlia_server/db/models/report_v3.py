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
    Boolean,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.sqlite import JSON
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
    # JSON-serialised CoverSpec from the model's ``set_cover`` tool call.
    # Nullable so older rows (and runs where the model skipped set_cover)
    # render with the bare cover. PR9.
    cover_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_report_v3"),
        Index("ix_report_v3_user_id_created_at", "user_id", "created_at"),
        Index("ix_report_v3_user_id_status", "user_id", "status"),
    )


class ReportV3Section(Base):
    """One section the model wrote via ``write_section``.

    ``section_index`` is the section's position in the rendered report
    (template order for built-in sections, append order for sections
    the LLM added during a revision). ``markdown`` is stored with
    the raw ``[^source_id]`` and ``{{chart:id}}`` markers intact —
    the citation rewriter resolves them at render time.

    PR4 adds versioning. The original run inserts rows with
    ``revision_id=NULL`` and ``version=1``. Each revision that
    rewrites a section appends a NEW row with the next version and
    its ``revision_id`` set; prior versions stay for audit + the
    "Open original" toggle. The renderer reads the latest version per
    ``section_id`` for the live view; specific versions on demand.

    The old unique (report_id, section_id) constraint is gone — that
    invariant is now (report_id, section_id, version), enforced by
    the migration's replacement unique constraint.
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
    # Null means "original run". Set to a revisions.id for revised
    # sections. CASCADE delete means a revision delete also wipes the
    # section versions written by it.
    revision_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("report_v3_revisions.id", ondelete="CASCADE"),
        nullable=True,
    )
    # 1-based monotonic version per (report_id, section_id). 1 for the
    # original run, 2+ for revisions that touch that section.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_report_v3_sections"),
        UniqueConstraint(
            "report_id",
            "section_id",
            "version",
            name="uq_report_v3_sections_report_id_section_id_version",
        ),
        Index("ix_report_v3_sections_report_id", "report_id"),
        Index(
            "ix_report_v3_sections_report_id_section_id_version",
            "report_id",
            "section_id",
            "version",
        ),
    )


class ReportV3Chart(Base):
    """One chart spec the model emitted via ``emit_chart``.

    ``spec_json`` is the full ``ChartSpec`` Pydantic dump — the
    renderer reads it back via ``ChartSpec.model_validate_json``.
    ``rendered_url`` is populated by Phase 2b's chart_renderer; null
    until rendering completes.

    Versioned the same way as ReportV3Section. A revision that
    re-emits a chart appends a new row at the next version; the
    renderer reads the latest version per ``chart_id``.
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
    revision_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("report_v3_revisions.id", ondelete="CASCADE"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_report_v3_charts"),
        UniqueConstraint(
            "report_id",
            "chart_id",
            "version",
            name="uq_report_v3_charts_report_id_chart_id_version",
        ),
        Index("ix_report_v3_charts_report_id", "report_id"),
        Index(
            "ix_report_v3_charts_report_id_chart_id_version",
            "report_id",
            "chart_id",
            "version",
        ),
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


class ReportV3Template(Base):
    """v3 equity-research template — built-in or user-uploaded.

    v3 owns its own template storage rather than reusing v2.3's
    ``report_templates`` table so the two engines stay independent
    (deletion semantics, lifecycle, eventual schema drift all live
    on their own track). The runtime schema is reused (``TemplateSpec``
    from v2.3 is already engine-agnostic) — only the storage and
    discovery surface is v3-specific.

    Built-in rows are seeded by the migration:
      - ``id`` = the built-in's stable template_id
        (``initiation_default`` etc.)
      - ``user_id`` = NULL
      - ``is_builtin`` = True
      - ``deleted_at`` is never set on built-ins

    User uploads:
      - ``id`` = UUID
      - ``user_id`` = the owner
      - ``is_builtin`` = False
      - ``source_markdown`` / ``source_doc_blob`` / ``source_doc_mime``
        hold the original upload so a future re-parse / edit flow can
        round-trip without losing fidelity
      - ``deleted_at`` flips on owner-scoped soft-delete; the resolver
        ignores soft-deleted rows but they linger for audit
    """

    __tablename__ = "report_v3_templates"

    id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Serialized ``TemplateSpec.model_dump()``. Reads go through
    # ``TemplateSpec.model_validate`` to reconstitute the runtime object.
    template_spec_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Original upload artifacts — null for built-ins. Stored verbatim so
    # the review UI can re-render the source.
    source_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_doc_blob: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    source_doc_mime: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    # Soft-delete tombstone. Resolver and list endpoint filter on
    # ``deleted_at IS NULL`` so soft-deleted rows are invisible to the
    # user but available for audit / forensic recovery.
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_report_v3_templates"),
        Index("ix_report_v3_templates_user_id", "user_id"),
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


class ReportV3Revision(Base):
    """One user-initiated revision of a completed v3 report.

    Each row models a single round of "the user asked for a change,
    the engine ran a revise pass". The engine pre-loads the prior
    report into the LLM's context, accepts a free-form revision
    request, and writes new section/chart versions linked back via
    ``ReportV3Section.revision_id`` / ``ReportV3Chart.revision_id``.

    Concurrency: the route layer rejects POST /revise with HTTP 409
    when this report already has a non-terminal revision in flight.
    ``revision_index`` is a 1-based monotonic counter per report —
    drives the chronological order in the chat UI and the version
    numbers shown on revised sections.
    """

    __tablename__ = "report_v3_revisions"

    id: Mapped[str] = mapped_column(String(36), nullable=False)
    report_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("report_v3.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # Free-form revision instruction the user typed in chat — fed to
    # the model verbatim as the user turn after the prior-report
    # context. Holds the same role chat history would in v2.2.
    request: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True
    )

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_report_v3_revisions"),
        UniqueConstraint(
            "report_id",
            "revision_index",
            name="uq_report_v3_revisions_report_id_revision_index",
        ),
        Index(
            "ix_report_v3_revisions_report_id_created_at",
            "report_id",
            "created_at",
        ),
        Index(
            "ix_report_v3_revisions_report_id_status",
            "report_id",
            "status",
        ),
    )
