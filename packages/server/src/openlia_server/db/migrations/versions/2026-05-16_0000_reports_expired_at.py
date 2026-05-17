"""Add expired_at column to reports table.

Tombstone marker for the report retention feature: rows where
``expired_at IS NOT NULL`` have had their body fields blanked, their
report_versions / repo_items / graph_artifact_summaries deleted, but
remain in place as chat-history anchors. Both the nightly maintenance
sweep and the DELETE /reports/{id} route set this via the shared
``services/reports.py::tombstone_report`` function.

Revision ID: 20260516_0000_reports_expired_at
Revises: 20260515_0000_er_web_search_budgets
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260516_0000_reports_expired_at"
down_revision: str | Sequence[str] | None = "20260515_0000_er_web_search_budgets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("reports") as batch:
        batch.add_column(
            sa.Column(
                "expired_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
    op.create_index("ix_reports_expired_at", "reports", ["expired_at"])


def downgrade() -> None:
    op.drop_index("ix_reports_expired_at", table_name="reports")
    with op.batch_alter_table("reports") as batch:
        batch.drop_column("expired_at")
