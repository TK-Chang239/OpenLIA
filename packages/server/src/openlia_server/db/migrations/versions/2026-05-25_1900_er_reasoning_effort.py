"""Add report_reasoning_effort column to er_user_configs.

Persists the user's extended-thinking pill choice (off/medium/high) so it
survives across browsers and machines. Nullable + no server default: the
wiring layer treats NULL the same as "off", and the route normalises on
read. A CheckConstraint mirrors report_length's pattern.

Revision ID: c2d4e5f6a7b8
Revises: b1c2d4e5f6a7
Create Date: 2026-05-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c2d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b1c2d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("er_user_configs") as batch:
        batch.add_column(
            sa.Column(
                "report_reasoning_effort",
                sa.String(length=16),
                nullable=True,
            )
        )
        batch.create_check_constraint(
            "ck_er_user_configs_reasoning_effort",
            "report_reasoning_effort IS NULL OR "
            "report_reasoning_effort IN ('off','medium','high')",
        )


def downgrade() -> None:
    with op.batch_alter_table("er_user_configs") as batch:
        batch.drop_constraint(
            "ck_er_user_configs_reasoning_effort", type_="check"
        )
        batch.drop_column("report_reasoning_effort")
