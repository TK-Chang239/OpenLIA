"""Drop data_providers and data_provider_requirement_mapping.

The cutover replaced the legacy data-provider system with the connector
subsystem (see docs/superpowers/specs/2026-04-27-connector-cutover-design.md).
Downgrade re-creates both tables empty (schema only) for migration-chain
reversibility — production code no longer references either table.

Revision ID: 20260427_1900_drop_dp
Revises: 20260427_1730_drop_credref
Create Date: 2026-04-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260427_1900_drop_dp"
down_revision: str | Sequence[str] | None = "20260427_1730_drop_credref"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("data_provider_requirement_mapping")
    op.drop_table("data_providers")


def downgrade() -> None:
    op.create_table(
        "data_providers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column(
            "category",
            sa.String(length=16),
            nullable=False,
            server_default="financial",
        ),
        sa.Column(
            "mode",
            sa.String(length=16),
            nullable=False,
            server_default="api_key",
        ),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("env_var_name", sa.String(length=64), nullable=True),
        sa.Column("base_url", sa.String(length=512), nullable=True),
        sa.Column("mcp_url", sa.String(length=512), nullable=True),
        sa.Column("mcp_auth_header", sa.Text(), nullable=True),
        sa.Column("extra_config", sa.JSON(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_data_providers_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_providers")),
        sa.CheckConstraint(
            "category IN ('financial', 'news', 'social_media', 'search')",
            name="ck_data_providers_category",
        ),
        sa.CheckConstraint(
            "mode IN ('api_key', 'mcp')",
            name="ck_data_providers_mode",
        ),
    )
    with op.batch_alter_table("data_providers", schema=None) as batch_op:
        batch_op.create_index("ix_data_providers_kind", ["kind"], unique=False)
        batch_op.create_index("ix_data_providers_is_enabled", ["is_enabled"], unique=False)
        batch_op.create_index("ix_data_providers_category", ["category"], unique=False)

    op.create_table(
        "data_provider_requirement_mapping",
        sa.Column("requirement_type", sa.String(length=64), nullable=False),
        sa.Column("provider_id", sa.String(length=36), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["data_providers.id"],
            name=op.f("fk_data_provider_requirement_mapping_provider_id_data_providers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "requirement_type",
            "provider_id",
            name=op.f("pk_data_provider_requirement_mapping"),
        ),
    )
