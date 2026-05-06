"""Per-(user, department) report tool cache.

Two tables:

- ``report_tool_warmup`` tracks how many runs have started in the
  (user, department) bucket. The cache exposes the full connector
  surface to the LLM during the first ``WARMUP_RUN_QUOTA`` runs.

- ``report_tool_usage`` is an append-only log of tool calls. The cache
  policy reads this log lazily at run start to decide which tools to
  expose. See ``services/report_tool_cache.py`` for the rules.

Revision ID: 20260505_1300_report_tool_cache
Revises: 20260504_1930_chat_session_disabled_lists
Create Date: 2026-05-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260505_1300_report_tool_cache"
down_revision: str | Sequence[str] | None = "20260504_1930_chat_session_disabled_lists"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_index("ix_report_tool_usage_lookup", table_name="report_tool_usage")
    op.drop_index("ix_report_tool_usage_department_id", table_name="report_tool_usage")
    op.drop_index("ix_report_tool_usage_user_id", table_name="report_tool_usage")
    op.drop_table("report_tool_usage")
    op.drop_table("report_tool_warmup")
