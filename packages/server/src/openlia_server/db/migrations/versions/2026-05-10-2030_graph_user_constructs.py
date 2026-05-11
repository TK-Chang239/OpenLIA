"""Slice 5 — graph_user_constructs.

Stores user-stated beliefs / positions anchored to an entity (positions,
theses, concerns, watchlist items). The slice-11 retrieval pipeline pulls
constructs whose ``entity_id`` matches an entity referenced in the
current chat turn and injects them into the system prompt.

Revision ID: 20260510_2030_graph_user_constructs
Revises: 20260510_1930_graph_entities_and_edges
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260510_2030_graph_user_constructs"
down_revision: str | Sequence[str] | None = "20260510_1930_graph_entities_and_edges"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "graph_user_constructs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="confirmed",
        ),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.String(length=128), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_graph_user_constructs"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_graph_user_constructs_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["graph_entities.id"],
            name="fk_graph_user_constructs_entity_id_graph_entities",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_graph_user_constructs_user_id",
        "graph_user_constructs",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_graph_user_constructs_entity_id",
        "graph_user_constructs",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_graph_user_constructs_user_id_status",
        "graph_user_constructs",
        ["user_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_graph_user_constructs_user_id_status", table_name="graph_user_constructs")
    op.drop_index("ix_graph_user_constructs_entity_id", table_name="graph_user_constructs")
    op.drop_index("ix_graph_user_constructs_user_id", table_name="graph_user_constructs")
    op.drop_table("graph_user_constructs")
