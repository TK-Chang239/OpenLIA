"""pipeline_runs.final_html

Revision ID: c2d4e6f8a0b1
Revises: a1b2c3d4e5f6
Create Date: 2026-05-22 13:30:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c2d4e6f8a0b1"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("pipeline_runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("final_html", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("final_html_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("pipeline_runs", schema=None) as batch_op:
        batch_op.drop_column("final_html_at")
        batch_op.drop_column("final_html")
