"""eu_v2 batch job + run tables

Revision ID: eu_batch_tables_0601
Revises: eu_batch_enabled_0601
Create Date: 2026-06-01 12:30:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "eu_batch_tables_0601"
down_revision: str | Sequence[str] | None = "eu_batch_enabled_0601"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "eu_v2_batch_job",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("provider_kind", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="submitted"),
        sa.Column("provider_batch_id", sa.String(length=128), nullable=True),
        sa.Column("turn_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_eu_v2_batch_job"),
    )
    op.create_index("ix_eu_v2_batch_job_status", "eu_v2_batch_job", ["status"])

    op.create_table(
        "eu_v2_batch_run",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("batch_job_id", sa.String(length=36), nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("custom_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["batch_job_id"], ["eu_v2_batch_job.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["report_id"], ["report_eu.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_eu_v2_batch_run"),
    )
    op.create_index("ix_eu_v2_batch_run_batch_job_id", "eu_v2_batch_run", ["batch_job_id"])


def downgrade() -> None:
    op.drop_index("ix_eu_v2_batch_run_batch_job_id", table_name="eu_v2_batch_run")
    op.drop_table("eu_v2_batch_run")
    op.drop_index("ix_eu_v2_batch_job_status", table_name="eu_v2_batch_job")
    op.drop_table("eu_v2_batch_job")
