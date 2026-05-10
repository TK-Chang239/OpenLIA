"""Slice 6 — graph_extraction_proposals.

Persistent queue of LLM-extracted graph additions awaiting user review.
``statement_hash`` is the dedup key: dismissed proposals act as
tombstones so the slice-8 extractor doesn't re-propose statements the
user has already declined.

Revision ID: 20260510_2130_graph_extraction_proposals
Revises: 20260510_2030_graph_user_constructs
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260510_2130_graph_extraction_proposals"
down_revision: str | Sequence[str] | None = "20260510_2030_graph_user_constructs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "graph_extraction_proposals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("source_kind", sa.String(length=16), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("statement_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
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
        sa.PrimaryKeyConstraint("id", name="pk_graph_extraction_proposals"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_graph_extraction_proposals_user_id_users",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_graph_extraction_proposals_user_id_status",
        "graph_extraction_proposals",
        ["user_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_graph_extraction_proposals_statement_hash",
        "graph_extraction_proposals",
        ["user_id", "statement_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_graph_extraction_proposals_statement_hash",
        table_name="graph_extraction_proposals",
    )
    op.drop_index(
        "ix_graph_extraction_proposals_user_id_status",
        table_name="graph_extraction_proposals",
    )
    op.drop_table("graph_extraction_proposals")
