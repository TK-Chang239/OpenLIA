"""Add background-report columns to reports table.

status, original_request, started_at columns support the
POST /reports/generate immediate-return background path.

Revision ID: 20260517_0001_reports_bg_fields
Revises: 20260517_0000_chat_session_attached_report_id
Create Date: 2026-05-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260517_0001_reports_bg_fields"
down_revision: str | Sequence[str] | None = "20260517_0000_chat_session_attached_report_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("reports") as batch:
        batch.add_column(sa.Column("status", sa.String(32), nullable=True))
        batch.add_column(sa.Column("original_request", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("reports") as batch:
        batch.drop_column("started_at")
        batch.drop_column("original_request")
        batch.drop_column("status")
