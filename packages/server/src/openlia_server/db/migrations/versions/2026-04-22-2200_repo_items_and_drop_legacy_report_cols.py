"""Consolidate saved-report persistence on repo_items.

Creates `repo_items` (user_id × report_id) and drops the legacy
`Report.is_starred` and `Report.tags` columns. See spec
docs/superpowers/specs/2026-04-22-plan-12-blockers-design.md.

Revision ID: c1f4e2d7a931
Revises: b3d8f5a0e192
Create Date: 2026-04-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c1f4e2d7a931"
down_revision: str | Sequence[str] | None = "b3d8f5a0e192"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "repo_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "report_id", name="uq_repo_items_user_report"),
    )
    op.create_index(
        "ix_repo_items_user_id_created_at",
        "repo_items",
        ["user_id", "created_at"],
    )

    with op.batch_alter_table("reports", schema=None) as batch_op:
        batch_op.drop_column("is_starred")
        batch_op.drop_column("tags")


def downgrade() -> None:
    with op.batch_alter_table("reports", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_starred", sa.Boolean(), nullable=True)
        )
        batch_op.add_column(sa.Column("tags", sa.JSON(), nullable=True))

    op.drop_index("ix_repo_items_user_id_created_at", table_name="repo_items")
    op.drop_table("repo_items")
