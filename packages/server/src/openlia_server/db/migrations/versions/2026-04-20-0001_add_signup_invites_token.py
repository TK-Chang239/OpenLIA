"""Add token column to signup_invites table.

Revision ID: 3c8e1a2b4d9f
Revises: f2a9566f7bf9
Create Date: 2026-04-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3c8e1a2b4d9f"
down_revision: str | Sequence[str] | None = "f2a9566f7bf9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("signup_invites", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("token", sa.String(length=64), nullable=True)
        )
        batch_op.create_unique_constraint(
            op.f("uq_signup_invites_token"), ["token"]
        )


def downgrade() -> None:
    with op.batch_alter_table("signup_invites", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("uq_signup_invites_token"), type_="unique")
        batch_op.drop_column("token")
