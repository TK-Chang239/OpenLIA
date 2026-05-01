"""Drop tool_allowlists table.

Allowlist concept retired: the runtime router walks the full validated
tool inventory per spec §8.1.

Revision ID: 20260428_0100_drop_ta
Revises: 20260428_0001_drop_dp
Create Date: 2026-04-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260428_0100_drop_ta"
down_revision: str | Sequence[str] | None = "20260428_0001_drop_dp"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_tool_allowlists_connector_id", table_name="tool_allowlists")
    op.drop_index("ix_tool_allowlists_department_id", table_name="tool_allowlists")
    op.drop_table("tool_allowlists")


def downgrade() -> None:
    op.create_table(
        "tool_allowlists",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("department_id", sa.String(length=64), nullable=False),
        sa.Column(
            "connector_id",
            sa.String(length=36),
            sa.ForeignKey("connectors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column(
            "scoped_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("scoped_by", sa.String(length=16), nullable=False),
        sa.UniqueConstraint(
            "department_id",
            "connector_id",
            "tool_name",
            name="uq_tool_allowlists_dep_conn_tool",
        ),
        sa.CheckConstraint(
            "scoped_by IN ('built_in_map', 'llm_adapter')",
            name="scoped_by",
        ),
    )
    op.create_index("ix_tool_allowlists_department_id", "tool_allowlists", ["department_id"])
    op.create_index("ix_tool_allowlists_connector_id", "tool_allowlists", ["connector_id"])
