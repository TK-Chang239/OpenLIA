"""Cross-session memory graph (slice 1).

Tier-2 taxonomy from ``planning/specs/systems/`` (graph memory design):

* ``GraphEntity`` — canonical, deduplicated nodes for tickers, sectors,
  themes, macro regimes. The string PK is ``f"{kind}:{value}"`` (e.g.
  ``"ticker:NVDA"``) so two callers reach the same node without a lookup
  round-trip.
* ``GraphEdge`` — polymorphic edges. ``src_kind`` / ``dst_kind`` is one
  of ``entity | construct | report | session | snapshot`` so edges can
  point into existing artifact tables without duplicating their rows.

UserConstruct nodes and embedding columns land in later slices.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DDL,
    JSON,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base, TimestampMixin


class GraphEntity(Base, TimestampMixin):
    __tablename__ = "graph_entities"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[str] = mapped_column(String(96), nullable=False)
    props: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_trigger_disabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )

    __table_args__ = (
        UniqueConstraint("kind", "value", name="uq_graph_entities_kind_value"),
        Index("ix_graph_entities_kind", "kind"),
    )


class GraphEdge(Base):
    __tablename__ = "graph_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    src_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    src_id: Mapped[str] = mapped_column(String(128), nullable=False)
    dst_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    dst_id: Mapped[str] = mapped_column(String(128), nullable=False)
    edge_type: Mapped[str] = mapped_column(String(32), nullable=False)
    props: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "ix_graph_edges_src",
            "src_kind",
            "src_id",
            "edge_type",
        ),
        Index(
            "ix_graph_edges_dst",
            "dst_kind",
            "dst_id",
            "edge_type",
        ),
    )


class GraphUserConstruct(Base, TimestampMixin):
    """User-stated belief or position anchored to an entity (slice 5).

    ``status`` lifecycle: ``proposed`` (extracted by slice-6 LLM, awaiting
    user confirmation) → ``confirmed`` (visible in retrieval) | ``rejected``
    (tombstone so the same statement isn't re-proposed). Constructs created
    via the explicit user-facing API short-circuit to ``confirmed``.

    ``entity_id`` is the canonical ``"kind:value"`` string (e.g.
    ``"ticker:NVDA"``) — a foreign key into ``graph_entities`` so deletes
    cascade if an entity is ever pruned.
    """

    __tablename__ = "graph_user_constructs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="confirmed",
        server_default="confirmed",
    )
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("graph_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    provenance: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_graph_user_constructs_user_id", "user_id"),
        Index("ix_graph_user_constructs_entity_id", "entity_id"),
        Index("ix_graph_user_constructs_user_id_status", "user_id", "status"),
    )


class GraphExtractionProposal(Base, TimestampMixin):
    """Pending or resolved LLM-extracted graph addition (slice 6).

    The async extractor (slice 8) reads chat-session transcripts, asks
    an LLM what user constructs and entity mentions it observed, and
    writes each as a ``pending`` proposal here. The user accepts /
    dismisses via slice-7 routes; ``dismissed`` rows become tombstones
    so the extractor doesn't re-propose the same statement on the next
    run (matched via ``statement_hash``).

    ``payload`` shape is kind-specific:
    * ``user_construct``: ``{construct_kind, statement, entity_kind,
      entity_value, source_excerpt?}``
    * ``mention``: ``{entity_kind, entity_value, artifact_kind,
      artifact_id}``
    """

    __tablename__ = "graph_extraction_proposals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    statement_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    __table_args__ = (
        Index(
            "ix_graph_extraction_proposals_user_id_status",
            "user_id",
            "status",
        ),
        Index(
            "ix_graph_extraction_proposals_statement_hash",
            "user_id",
            "statement_hash",
        ),
    )


class GraphArtifactSummary(Base, TimestampMixin):
    """LLM-generated short summary of an artifact, with its embedding.

    One row per (user, artifact). Used by slice-12 vector recall to find
    artifacts semantically close to the user's live message. Storing the
    summary text alongside the embedding means retrieval can return a
    human-readable hit without joining back to the artifact's table.

    ``embedding`` is a packed little-endian float32 BLOB sized at
    ``dim * 4`` bytes; ``embedding_model`` tags the producer so a model
    swap can trigger re-embedding rather than mixing dimensions.
    """

    __tablename__ = "graph_artifact_summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    artifact_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    artifact_id: Mapped[str] = mapped_column(String(36), nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Slice 9 — claude-mem-style structured metadata for pre-filter-then-rank
    # retrieval. ``summary_text`` + ``embedding`` remain the canonical
    # embedded text used for cosine. These columns add cheap SQL filters
    # (e.g. ``WHERE tone='bullish' AND horizon='medium'``) ahead of the
    # vector search and surface a richer hit payload without rejoining
    # the artifact table.
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    tagline: Mapped[str | None] = mapped_column(Text, nullable=True)
    findings_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    entities_mentioned: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    tone: Mapped[str | None] = mapped_column(String(16), nullable=True)
    horizon: Mapped[str | None] = mapped_column(String(16), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "artifact_kind",
            "artifact_id",
            name="uq_graph_artifact_summaries_user_artifact",
        ),
        Index("ix_graph_artifact_summaries_user_id", "user_id"),
    )


class GraphExtractionRun(Base):
    """Slice 4 — audit row for one nightly graph-extraction invocation.

    Watermark for "new since last run" = the latest ``started_at`` across
    rows where ``error IS NULL`` AND ``finished_at IS NOT NULL`` for a
    user. Failed runs do not advance the watermark; the next attempt
    will re-cover that window.
    """

    __tablename__ = "graph_extraction_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        # Aware UTC; project base uses UTCDateTime via type_annotation_map.
        # Declared explicitly so Mapped[datetime] picks up the right column type.
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    proposals_inserted: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    sessions_processed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    error: Mapped[str | None] = mapped_column(String(256), nullable=True)

    __table_args__ = (
        Index("ix_graph_extraction_runs_user_id_started_at", "user_id", "started_at"),
    )


# ---------------------------------------------------------------------------
# SQLite-only FTS5 shadow of GraphArtifactSummary (slice 10 — hybrid retrieval).
#
# Alembic migration 20260511_0200 creates these objects in production
# databases. The DDL listeners below ensure the same virtual table +
# triggers exist when Base.metadata.create_all() is used (tests). Both
# code paths are gated on the SQLite dialect — Postgres uses a separate
# tsvector path (out of scope for this slice).
# ---------------------------------------------------------------------------

_FTS_CREATE = DDL(
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS graph_artifact_summaries_fts USING fts5(
        summary_text,
        subject,
        tagline,
        findings_text,
        content='graph_artifact_summaries',
        content_rowid='rowid'
    )
    """
)

_FTS_TRIGGERS = [
    DDL(
        """
        CREATE TRIGGER IF NOT EXISTS graph_artifact_summaries_ai
        AFTER INSERT ON graph_artifact_summaries BEGIN
            INSERT INTO graph_artifact_summaries_fts(
                rowid, summary_text, subject, tagline, findings_text
            ) VALUES (
                new.rowid, new.summary_text, new.subject, new.tagline, new.findings_text
            );
        END
        """
    ),
    DDL(
        """
        CREATE TRIGGER IF NOT EXISTS graph_artifact_summaries_ad
        AFTER DELETE ON graph_artifact_summaries BEGIN
            INSERT INTO graph_artifact_summaries_fts(
                graph_artifact_summaries_fts, rowid,
                summary_text, subject, tagline, findings_text
            ) VALUES (
                'delete', old.rowid,
                old.summary_text, old.subject, old.tagline, old.findings_text
            );
        END
        """
    ),
    DDL(
        """
        CREATE TRIGGER IF NOT EXISTS graph_artifact_summaries_au
        AFTER UPDATE ON graph_artifact_summaries BEGIN
            INSERT INTO graph_artifact_summaries_fts(
                graph_artifact_summaries_fts, rowid,
                summary_text, subject, tagline, findings_text
            ) VALUES (
                'delete', old.rowid,
                old.summary_text, old.subject, old.tagline, old.findings_text
            );
            INSERT INTO graph_artifact_summaries_fts(
                rowid, summary_text, subject, tagline, findings_text
            ) VALUES (
                new.rowid, new.summary_text, new.subject, new.tagline, new.findings_text
            );
        END
        """
    ),
]


@event.listens_for(GraphArtifactSummary.__table__, "after_create")
def _create_artifact_summary_fts(target, connection, **kw) -> None:
    if connection.dialect.name != "sqlite":
        return
    connection.execute(_FTS_CREATE)
    for trig in _FTS_TRIGGERS:
        connection.execute(trig)


@event.listens_for(GraphArtifactSummary.__table__, "before_drop")
def _drop_artifact_summary_fts(target, connection, **kw) -> None:
    if connection.dialect.name != "sqlite":
        return
    connection.execute(DDL("DROP TRIGGER IF EXISTS graph_artifact_summaries_au"))
    connection.execute(DDL("DROP TRIGGER IF EXISTS graph_artifact_summaries_ad"))
    connection.execute(DDL("DROP TRIGGER IF EXISTS graph_artifact_summaries_ai"))
    connection.execute(DDL("DROP TABLE IF EXISTS graph_artifact_summaries_fts"))
