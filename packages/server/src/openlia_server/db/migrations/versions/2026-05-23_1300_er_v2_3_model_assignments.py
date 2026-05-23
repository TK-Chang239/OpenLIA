"""er_v2_3_model_assignments

Revision ID: b1c2d4e5f6a7
Revises: a9b1c2d4e5f6
Create Date: 2026-05-23 13:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d4e5f6a7"
down_revision: str | Sequence[str] | None = "a9b1c2d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "er_v2_3_model_assignments",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("slot", sa.String(length=64), nullable=False),
        sa.Column("model_id", sa.String(length=36), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_er_v2_3_model_assignments_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["llm_models.id"],
            name=op.f("fk_er_v2_3_model_assignments_model_id_llm_models"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("user_id", "slot", name="pk_er_v2_3_model_assignments"),
    )


def downgrade() -> None:
    op.drop_table("er_v2_3_model_assignments")
