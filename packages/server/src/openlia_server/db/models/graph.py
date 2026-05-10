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
    JSON,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
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
