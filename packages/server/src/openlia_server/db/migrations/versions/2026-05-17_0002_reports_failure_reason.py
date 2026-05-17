"""Add failure_reason column to reports table.

failure_reason stores the short reason string set when a background
report is cancelled or fails (e.g. 'user_cancelled').

Revision ID: 20260517_0002_reports_failure_reason
Revises: 20260517_0001_reports_bg_fields
Create Date: 2026-05-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260517_0002_reports_failure_reason"
down_revision: str | Sequence[str] | None = "20260517_0001_reports_bg_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("reports") as batch:
        batch.add_column(sa.Column("failure_reason", sa.String(512), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("reports") as batch:
        batch.drop_column("failure_reason")
