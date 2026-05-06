"""Per-(user, department) model preference.

Adds the ``user_department_model_prefs`` table backing the per-page
model picker. Wins over the user-level ``user_prefs.preferred_model_id``
and the tier defaults; absence of a row falls back to that chain.

Revision ID: 20260505_1400_user_department_model_prefs
Revises: 20260505_1300_report_tool_cache
Create Date: 2026-05-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260505_1400_user_department_model_prefs"
down_revision: str | Sequence[str] | None = "20260505_1300_report_tool_cache"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_department_model_prefs",
        sa.Column("user_id", sa.String(length=36), primary_key=True),
        sa.Column("department_id", sa.String(length=64), primary_key=True),
        sa.Column("model_id", sa.String(length=36), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
            name="fk_user_department_model_prefs_user_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["llm_models.id"],
            ondelete="CASCADE",
            name="fk_user_department_model_prefs_model_id_llm_models",
        ),
    )


def downgrade() -> None:
    op.drop_table("user_department_model_prefs")
