"""Add web_search_budgets_by_mode JSON column to er_user_configs.

Phase 5f — per-report web-search budget user override. Nullable; the
runner falls back to the framework default when the column is null or
the mode key is absent.

Revision ID: 20260515_0000_er_web_search_budgets
Revises: 20260514_0000_drop_report_tool_cache
Create Date: 2026-05-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260515_0000_er_web_search_budgets"
down_revision: str | Sequence[str] | None = "20260514_0000_drop_report_tool_cache"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("er_user_configs") as batch:
        batch.add_column(
            sa.Column(
                "web_search_budgets_by_mode",
                sa.JSON(),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("er_user_configs") as batch:
        batch.drop_column("web_search_budgets_by_mode")
