"""repo_items: add v3_report_id polymorphic target

Extends ``repo_items`` with a third nullable FK column,
``v3_report_id`` (-> ``report_v3.id``), so v3 equity-research reports
can be saved into the same repository that already holds v1 reports
(``report_id``) and v2.2 pipeline runs (``pipeline_run_id``).

Updates the existing CHECK constraint so it now allows *exactly one*
of the three target columns, mirrors the per-target uniqueness
constraint, and adds an index on (user_id, v3_report_id) for the
SavedReportsContext hydration query.

Existing rows are untouched — they still satisfy the new CHECK
because their ``v3_report_id`` defaults to NULL on add.

Revision ID: d3f8a6e2c9b4
Revises: c7e3a5b9d4f1
Create Date: 2026-05-28 09:30:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d3f8a6e2c9b4"
down_revision: str | Sequence[str] | None = "c7e3a5b9d4f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # SQLite can't ALTER existing CHECK constraints in-place; the
    # standard alembic pattern is batch_alter_table, which copies the
    # table under the hood.
    with op.batch_alter_table("repo_items") as batch:
        batch.add_column(sa.Column("v3_report_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_repo_items_v3_report_id",
            "report_v3",
            ["v3_report_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.drop_constraint("ck_repo_items_exactly_one_target", type_="check")
        batch.create_check_constraint(
            "ck_repo_items_exactly_one_target",
            "((report_id IS NOT NULL)::int + "
            "(pipeline_run_id IS NOT NULL)::int + "
            "(v3_report_id IS NOT NULL)::int) = 1"
            if op.get_bind().dialect.name == "postgresql"
            else "((CASE WHEN report_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN pipeline_run_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN v3_report_id IS NOT NULL THEN 1 ELSE 0 END)) = 1",
        )
        batch.create_unique_constraint("uq_repo_items_user_v3_report", ["user_id", "v3_report_id"])

    op.create_index(
        "ix_repo_items_user_id_v3_report_id",
        "repo_items",
        ["user_id", "v3_report_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_repo_items_user_id_v3_report_id", table_name="repo_items")
    with op.batch_alter_table("repo_items") as batch:
        batch.drop_constraint("uq_repo_items_user_v3_report", type_="unique")
        batch.drop_constraint("ck_repo_items_exactly_one_target", type_="check")
        batch.create_check_constraint(
            "ck_repo_items_exactly_one_target",
            "(report_id IS NOT NULL AND pipeline_run_id IS NULL) OR "
            "(report_id IS NULL AND pipeline_run_id IS NOT NULL)",
        )
        batch.drop_constraint("fk_repo_items_v3_report_id", type_="foreignkey")
        batch.drop_column("v3_report_id")
