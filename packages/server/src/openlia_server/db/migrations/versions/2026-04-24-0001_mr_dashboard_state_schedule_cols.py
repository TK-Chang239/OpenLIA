"""mr_dashboard_state assessment_schedule + last_assessment_at

Revision ID: 20260424_0001_mr
Revises: 20260423_2100_mb
Create Date: 2026-04-24 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260424_0001_mr"
down_revision: str | Sequence[str] | None = "20260423_2100_mb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("mr_dashboard_state") as batch:
        batch.add_column(
            sa.Column("assessment_schedule", sa.String(length=64), nullable=True)
        )
        batch.add_column(
            sa.Column("last_assessment_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("mr_dashboard_state") as batch:
        batch.drop_column("last_assessment_at")
        batch.drop_column("assessment_schedule")
