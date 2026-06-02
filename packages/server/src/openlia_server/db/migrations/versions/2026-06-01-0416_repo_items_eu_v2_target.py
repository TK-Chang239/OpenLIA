"""repo_items eu_v2 target

Revision ID: 1c6b0cda0ed9
Revises: 984fc020381a
Create Date: 2026-06-01 04:16:22.990630+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1c6b0cda0ed9"
down_revision: str | Sequence[str] | None = "984fc020381a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("repo_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("eu_v2_report_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_repo_items_eu_v2_report_id",
            "report_eu",
            ["eu_v2_report_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_unique_constraint(
            "uq_repo_items_user_eu_report", ["user_id", "eu_v2_report_id"]
        )
        batch_op.drop_constraint("ck_repo_items_exactly_one_target", type_="check")
        batch_op.create_check_constraint(
            "ck_repo_items_exactly_one_target",
            "((CASE WHEN report_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN pipeline_run_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN v3_report_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN eu_v2_report_id IS NOT NULL THEN 1 ELSE 0 END)) = 1",
        )


def downgrade() -> None:
    with op.batch_alter_table("repo_items", schema=None) as batch_op:
        batch_op.drop_constraint("ck_repo_items_exactly_one_target", type_="check")
        batch_op.drop_constraint("uq_repo_items_user_eu_report", type_="unique")
        batch_op.drop_constraint("fk_repo_items_eu_v2_report_id", type_="foreignkey")
        batch_op.drop_column("eu_v2_report_id")
        batch_op.create_check_constraint(
            "ck_repo_items_exactly_one_target",
            "((CASE WHEN report_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN pipeline_run_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN v3_report_id IS NOT NULL THEN 1 ELSE 0 END)) = 1",
        )
