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
    Index,
    Integer,
    String,
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
