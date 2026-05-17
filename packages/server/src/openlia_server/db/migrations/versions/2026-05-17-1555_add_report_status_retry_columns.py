"""add report status + retry columns

Revision ID: 9b3077e1c7ee
Revises: 83062e1da1ec
Create Date: 2026-05-17 15:55:30.649267+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9b3077e1c7ee"
down_revision: str | Sequence[str] | None = "83062e1da1ec"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("reports") as batch_op:
        batch_op.add_column(
            sa.Column("status", sa.String(), nullable=False, server_default="complete")
        )
        batch_op.add_column(sa.Column("failure_reason", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("original_request", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("idx_reports_status", "reports", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_reports_status", table_name="reports")
    with op.batch_alter_table("reports") as batch_op:
        batch_op.drop_column("started_at")
        batch_op.drop_column("original_request")
        batch_op.drop_column("failure_reason")
        batch_op.drop_column("status")
