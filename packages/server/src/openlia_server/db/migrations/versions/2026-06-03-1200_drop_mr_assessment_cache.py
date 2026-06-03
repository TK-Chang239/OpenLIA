"""drop mr_assessment_cache table

Removes the legacy tiered (T1-T5) Macro Research assessment cache. The
tiered engine has been superseded by the ``report_dash_mr`` engine, which
persists to ``mr_dashboard_cache``. Nothing reads or writes
``mr_assessment_cache`` anymore.

Revision ID: drop_mr_assessment_cache
Revises: mr_dashboard_cache
Create Date: 2026-06-03 12:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "drop_mr_assessment_cache"
down_revision: str | Sequence[str] | None = "mr_dashboard_cache"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("mr_assessment_cache")


def downgrade() -> None:
    op.create_table(
        "mr_assessment_cache",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("dashboard", sa.String(length=32), nullable=False),
        sa.Column("assessment_type", sa.String(length=16), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("model_ref", sa.String(length=128), nullable=False),
        sa.Column("token_usage", sa.JSON(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mr_assessment_cache")),
        sa.UniqueConstraint(
            "dashboard",
            "assessment_type",
            "input_hash",
            name="uq_mr_assessment_dash_type_hash",
        ),
    )
