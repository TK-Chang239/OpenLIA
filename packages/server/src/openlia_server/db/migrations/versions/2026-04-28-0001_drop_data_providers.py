"""Drop data_providers tables.

Removes the legacy `data_provider_requirement_mapping` and `data_providers`
tables; the connector subsystem replaces them.

Revision ID: 20260428_0001_drop_dp
Revises: 20260426_1700_connectors
Create Date: 2026-04-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260428_0001_drop_dp"
down_revision: str | Sequence[str] | None = "20260426_1700_connectors"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("data_provider_requirement_mapping")
    op.drop_table("data_providers")


def downgrade() -> None:
    op.create_table(
        "data_providers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False, server_default="financial"),
        sa.Column("mode", sa.String(length=16), nullable=False, server_default="api_key"),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("env_var_name", sa.String(length=64), nullable=True),
        sa.Column("base_url", sa.String(length=512), nullable=True),
        sa.Column("mcp_url", sa.String(length=512), nullable=True),
        sa.Column("mcp_auth_header", sa.Text(), nullable=True),
        sa.Column("extra_config", sa.JSON(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_by_user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "category IN ('financial', 'news', 'social_media', 'search')",
            name="ck_data_providers_category",
        ),
        sa.CheckConstraint(
            "mode IN ('api_key', 'mcp')",
            name="ck_data_providers_mode",
        ),
    )
    op.create_index("ix_data_providers_kind", "data_providers", ["kind"])
    op.create_index("ix_data_providers_is_enabled", "data_providers", ["is_enabled"])
    op.create_index("ix_data_providers_category", "data_providers", ["category"])
    op.create_table(
        "data_provider_requirement_mapping",
        sa.Column("requirement_type", sa.String(length=64), primary_key=True),
        sa.Column(
            "provider_id",
            sa.String(length=36),
            sa.ForeignKey("data_providers.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
