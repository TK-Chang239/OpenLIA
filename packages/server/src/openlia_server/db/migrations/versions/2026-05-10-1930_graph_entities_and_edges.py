"""Slice 1 — graph_entities and graph_edges.

Cross-session memory graph foundations. ``graph_entities`` holds canonical
deduplicated nodes (tickers, sectors, themes, macro regimes); their PK is
``f"{kind}:{value}"`` so callers reach the same node without a lookup
round-trip. ``graph_edges`` is polymorphic — ``src_kind`` / ``dst_kind``
can be ``entity | construct | report | session | snapshot`` so edges
reference existing artifact tables without duplicating their rows.

UserConstruct nodes (``graph_user_constructs``), the proposal queue
(``graph_extraction_proposals``), and embedding columns land in later
migrations.

Revision ID: 20260510_1930_graph_entities_and_edges
Revises: 20260510_1100_chat_session_response_length
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260510_1930_graph_entities_and_edges"
down_revision: str | Sequence[str] | None = "20260510_1100_chat_session_response_length"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "graph_entities",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("value", sa.String(length=96), nullable=False),
        sa.Column("props", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_graph_entities"),
        sa.UniqueConstraint("kind", "value", name="uq_graph_entities_kind_value"),
    )
    op.create_index(
        "ix_graph_entities_kind",
        "graph_entities",
        ["kind"],
        unique=False,
    )

    op.create_table(
        "graph_edges",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("src_kind", sa.String(length=16), nullable=False),
        sa.Column("src_id", sa.String(length=128), nullable=False),
        sa.Column("dst_kind", sa.String(length=16), nullable=False),
        sa.Column("dst_id", sa.String(length=128), nullable=False),
        sa.Column("edge_type", sa.String(length=32), nullable=False),
        sa.Column("props", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_graph_edges"),
    )
    op.create_index(
        "ix_graph_edges_src",
        "graph_edges",
        ["src_kind", "src_id", "edge_type"],
        unique=False,
    )
    op.create_index(
        "ix_graph_edges_dst",
        "graph_edges",
        ["dst_kind", "dst_id", "edge_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_graph_edges_dst", table_name="graph_edges")
    op.drop_index("ix_graph_edges_src", table_name="graph_edges")
    op.drop_table("graph_edges")
    op.drop_index("ix_graph_entities_kind", table_name="graph_entities")
    op.drop_table("graph_entities")
