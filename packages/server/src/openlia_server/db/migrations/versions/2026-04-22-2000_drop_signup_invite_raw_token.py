"""Drop raw signup_invites.token column; token_hash is source of truth.

Revision ID: 9a4b7c2e6f01
Revises: 7f3a1e9b2c4d
Create Date: 2026-04-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "9a4b7c2e6f01"
down_revision: str = "7f3a1e9b2c4d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("signup_invites", schema=None) as batch_op:
        batch_op.drop_column("token")


def downgrade() -> None:
    with op.batch_alter_table("signup_invites", schema=None) as batch_op:
        batch_op.add_column(sa.Column("token", sa.String(length=64), nullable=True))
        batch_op.create_unique_constraint("uq_signup_invites_token", ["token"])
