"""Create runner_callable_specs table.

Per spec §3.5: stores per-(department, need) callable resolution. The
wizard-time adapter LLM populates these; the deterministic runtime runner
walks them at execution time. Unique on (department_id, need_id).

Revision ID: 20260428_0300_rcs
Revises: 20260428_0200_conn_v2
Create Date: 2026-04-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260428_0300_rcs"
down_revision: str | Sequence[str] | None = "20260428_0200_conn_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runner_callable_specs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("department_id", sa.String(length=64), nullable=False),
        sa.Column("need_id", sa.String(length=64), nullable=False),
        sa.Column(
            "connector_id",
            sa.String(length=36),
            sa.ForeignKey("connectors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("access_mode", sa.String(length=16), nullable=False),
        sa.Column("spec", sa.JSON(), nullable=False),
        sa.Column("canary_value", sa.JSON(), nullable=True),
        sa.Column("canary_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("department_id", "need_id", name="uq_dept_need"),
        sa.CheckConstraint(
            "access_mode IN ('cli_mcp', 'remote_mcp', 'python_lib')",
            name="access_mode",
        ),
    )
    op.create_index("ix_rcs_department_id", "runner_callable_specs", ["department_id"])
    op.create_index("ix_rcs_connector_id", "runner_callable_specs", ["connector_id"])


def downgrade() -> None:
    op.drop_index("ix_rcs_connector_id", table_name="runner_callable_specs")
    op.drop_index("ix_rcs_department_id", table_name="runner_callable_specs")
    op.drop_table("runner_callable_specs")
