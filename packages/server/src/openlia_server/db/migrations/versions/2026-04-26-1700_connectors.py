"""Connector redesign — connectors and tool_allowlists tables.

Adds the new MCP-only connector model defined in
docs/superpowers/specs/2026-04-26-connector-redesign-design.md.

Does NOT drop data_providers in this revision; the cutover happens
later in the connector-redesign sequence.

Revision ID: 20260426_1700_connectors
Revises: 20260425_1500_rs_sched
Create Date: 2026-04-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260426_1700_connectors"
down_revision: str | Sequence[str] | None = "20260425_1500_rs_sched"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connectors",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("launch", sa.JSON(), nullable=False),
        sa.Column("credentials_ref", sa.String(length=128), nullable=True),
        sa.Column("cached_tools", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "source IN ('built_in', 'remote_mcp', 'cli_mcp')",
            name="source",
        ),
        sa.CheckConstraint(
            "category IN ('financial', 'news', 'social', 'web_search')",
            name="category",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'validated', 'failed')",
            name="status",
        ),
    )
    op.create_index("ix_connectors_provider_id", "connectors", ["provider_id"])
    op.create_index("ix_connectors_category", "connectors", ["category"])
    op.create_index("ix_connectors_status", "connectors", ["status"])

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


def downgrade() -> None:
    op.drop_index("ix_tool_allowlists_connector_id", table_name="tool_allowlists")
    op.drop_index("ix_tool_allowlists_department_id", table_name="tool_allowlists")
    op.drop_table("tool_allowlists")
    op.drop_index("ix_connectors_status", table_name="connectors")
    op.drop_index("ix_connectors_category", table_name="connectors")
    op.drop_index("ix_connectors_provider_id", table_name="connectors")
    op.drop_table("connectors")
