"""v2 repo support + pipeline_run lifecycle columns.

Two related concerns rolled into one migration:

1. repo_items can now point at a pipeline_run (v2 report) in addition to
   a v1 report. report_id becomes nullable and a sibling pipeline_run_id
   column is added; a CHECK constraint enforces that exactly one of the
   two is populated.

2. pipeline_runs grows deleted_at + expired_at for soft-delete (used by
   the v2 ReportCard's Delete button) and the future 7-day retention
   sweep (C6).

Revision ID: f7a9b1c2d4e5
Revises: e5f7a9b1c2d4
Create Date: 2026-05-22 20:30:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7a9b1c2d4e5"
down_revision: str | Sequence[str] | None = "e5f7a9b1c2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # pipeline_runs: soft-delete + retention columns.
    with op.batch_alter_table("pipeline_runs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True)
        )

    # repo_items: polymorphic pointer — exactly one of (report_id, pipeline_run_id).
    with op.batch_alter_table("repo_items", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("pipeline_run_id", sa.String(length=36), nullable=True)
        )
        batch_op.alter_column("report_id", existing_type=sa.String(length=36), nullable=True)
        batch_op.create_foreign_key(
            "fk_repo_items_pipeline_run_id",
            "pipeline_runs",
            ["pipeline_run_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_unique_constraint(
            "uq_repo_items_user_pipeline_run",
            ["user_id", "pipeline_run_id"],
        )
        batch_op.create_check_constraint(
            "ck_repo_items_exactly_one_target",
            "(report_id IS NOT NULL AND pipeline_run_id IS NULL) OR "
            "(report_id IS NULL AND pipeline_run_id IS NOT NULL)",
        )


def downgrade() -> None:
    with op.batch_alter_table("repo_items", schema=None) as batch_op:
        batch_op.drop_constraint("ck_repo_items_exactly_one_target", type_="check")
        batch_op.drop_constraint("uq_repo_items_user_pipeline_run", type_="unique")
        batch_op.drop_constraint("fk_repo_items_pipeline_run_id", type_="foreignkey")
        batch_op.alter_column("report_id", existing_type=sa.String(length=36), nullable=False)
        batch_op.drop_column("pipeline_run_id")

    with op.batch_alter_table("pipeline_runs", schema=None) as batch_op:
        batch_op.drop_column("expired_at")
        batch_op.drop_column("deleted_at")
