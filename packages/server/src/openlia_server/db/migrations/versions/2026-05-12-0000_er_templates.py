"""Add er_templates table + selected_template_id_by_mode column on er_user_configs.

User-uploaded report template feature for the Equity Research department.

Revision ID: 20260512_0000_er_templates
Revises: 20260511_0600_user_prefs_cadence_15min
Create Date: 2026-05-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260512_0000_er_templates"
down_revision: str | Sequence[str] | None = "20260511_0600_user_prefs_cadence_15min"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "er_templates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("owner_scope", sa.String(length=16), nullable=False),
        sa.Column(
            "owner_user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("compatible_modes", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("raw_filename", sa.String(length=512), nullable=False),
        sa.Column("raw_mime", sa.String(length=128), nullable=False),
        sa.Column("raw_size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("estimated_tokens", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "owner_scope IN ('global','user')",
            name="ck_er_templates_owner_scope",
        ),
        sa.CheckConstraint(
            "(owner_scope = 'global' AND owner_user_id IS NULL) OR "
            "(owner_scope = 'user' AND owner_user_id IS NOT NULL)",
            name="ck_er_templates_scope_owner_consistency",
        ),
    )
    op.create_index(
        "ix_er_templates_owner_scope_user",
        "er_templates",
        ["owner_scope", "owner_user_id"],
    )

    with op.batch_alter_table("er_user_configs") as batch:
        batch.add_column(
            sa.Column(
                "selected_template_id_by_mode",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("er_user_configs") as batch:
        batch.drop_column("selected_template_id_by_mode")
    op.drop_index("ix_er_templates_owner_scope_user", table_name="er_templates")
    op.drop_table("er_templates")
