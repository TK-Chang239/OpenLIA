"""remove tiers, add llm_slot_defaults

Revision ID: 20260513_0000_remove_tiers
Revises: 20260511_0600_user_prefs_cadence_15min
Create Date: 2026-05-13 00:00:00

Drops the per-tier resolution system. Adds llm_slot_defaults to store the
admin-assigned model for each user-facing department and each internal
system role. No data backfill - this project is pre-production.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260513_0000_remove_tiers"
down_revision = "20260511_0600_user_prefs_cadence_15min"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("user_llm_preferences")

    with op.batch_alter_table("llm_models") as batch:
        batch.drop_index("ix_llm_models_tier_is_enabled")
        batch.drop_index("uq_llm_models_tier_default")
        batch.drop_constraint("tier_enum", type_="check")
        batch.drop_column("is_tier_default")
        batch.drop_column("tier")

    op.create_table(
        "llm_slot_defaults",
        sa.Column("slot_kind", sa.String(16), nullable=False),
        sa.Column("slot_id", sa.String(64), nullable=False),
        sa.Column(
            "model_id",
            sa.String(36),
            sa.ForeignKey("llm_models.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("slot_kind", "slot_id"),
        sa.CheckConstraint(
            "slot_kind IN ('department','system_role')", name="slot_kind_enum"
        ),
    )
    op.create_index(
        "ix_llm_slot_defaults_model_id", "llm_slot_defaults", ["model_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_llm_slot_defaults_model_id", table_name="llm_slot_defaults")
    op.drop_table("llm_slot_defaults")

    with op.batch_alter_table("llm_models") as batch:
        batch.add_column(
            sa.Column("tier", sa.String(16), nullable=False, server_default="everyday")
        )
        batch.add_column(
            sa.Column(
                "is_tier_default",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.create_check_constraint(
            "tier_enum", "tier IN ('thinking', 'everyday', 'quick')"
        )
        batch.create_index(
            "uq_llm_models_tier_default",
            ["tier"],
            unique=True,
            sqlite_where=sa.text("is_tier_default = 1"),
            postgresql_where=sa.text("is_tier_default"),
        )
        batch.create_index("ix_llm_models_tier_is_enabled", ["tier", "is_enabled"])

    op.create_table(
        "user_llm_preferences",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("tier", sa.String(16), primary_key=True),
        sa.Column(
            "model_id",
            sa.String(36),
            sa.ForeignKey("llm_models.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "tier IN ('thinking', 'everyday', 'quick')", name="tier_enum"
        ),
    )
