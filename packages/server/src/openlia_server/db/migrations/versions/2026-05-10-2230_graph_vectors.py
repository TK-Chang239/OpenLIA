"""Slice 10 — vector storage columns + artifact summaries table.

Adds ``embedding`` + ``embedding_model`` to ``graph_user_constructs``
and creates the ``graph_artifact_summaries`` table. Embeddings are
packed little-endian float32 BLOBs; the ``embedding_model`` column
tags the producer so a model change can trigger re-embedding rather
than silently mixing dimensions.

Revision ID: 20260510_2230_graph_vectors
Revises: 20260510_2130_graph_extraction_proposals
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260510_2230_graph_vectors"
down_revision: str | Sequence[str] | None = "20260510_2130_graph_extraction_proposals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("graph_user_constructs") as batch:
        batch.add_column(sa.Column("embedding", sa.LargeBinary(), nullable=True))
        batch.add_column(sa.Column("embedding_model", sa.String(length=64), nullable=True))

    op.create_table(
        "graph_artifact_summaries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("artifact_kind", sa.String(length=16), nullable=False),
        sa.Column("artifact_id", sa.String(length=36), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("embedding", sa.LargeBinary(), nullable=True),
        sa.Column("embedding_model", sa.String(length=64), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_graph_artifact_summaries"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_graph_artifact_summaries_user_id_users",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "user_id",
            "artifact_kind",
            "artifact_id",
            name="uq_graph_artifact_summaries_user_artifact",
        ),
    )
    op.create_index(
        "ix_graph_artifact_summaries_user_id",
        "graph_artifact_summaries",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_graph_artifact_summaries_user_id", table_name="graph_artifact_summaries")
    op.drop_table("graph_artifact_summaries")
    with op.batch_alter_table("graph_user_constructs") as batch:
        batch.drop_column("embedding_model")
        batch.drop_column("embedding")
