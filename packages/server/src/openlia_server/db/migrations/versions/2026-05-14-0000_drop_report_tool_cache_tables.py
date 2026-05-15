"""drop report_tool_cache tables

Revision ID: 20260514_0000_drop_report_tool_cache
Revises: a4a4885e1e30
Create Date: 2026-05-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260514_0000_drop_report_tool_cache"
down_revision: str | Sequence[str] | None = "a4a4885e1e30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_report_tool_usage_lookup", table_name="report_tool_usage")
    op.drop_index("ix_report_tool_usage_department_id", table_name="report_tool_usage")
    op.drop_index("ix_report_tool_usage_user_id", table_name="report_tool_usage")
    op.drop_table("report_tool_usage")
    op.drop_table("report_tool_warmup")


def downgrade() -> None:
    op.create_table(
        "report_tool_warmup",
        sa.Column("user_id", sa.String(length=36), primary_key=True),
        sa.Column("department_id", sa.String(length=64), primary_key=True),
        sa.Column("runs_completed", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "report_tool_usage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("department_id", sa.String(length=64), nullable=False),
        sa.Column("tool_name", sa.String(length=255), nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_report_tool_usage_user_id",
        "report_tool_usage",
        ["user_id"],
    )
    op.create_index(
        "ix_report_tool_usage_department_id",
        "report_tool_usage",
        ["department_id"],
    )
    op.create_index(
        "ix_report_tool_usage_lookup",
        "report_tool_usage",
        ["user_id", "department_id", "tool_name", "run_date"],
    )
