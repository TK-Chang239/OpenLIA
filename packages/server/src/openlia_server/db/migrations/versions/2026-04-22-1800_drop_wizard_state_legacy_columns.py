"""Drop legacy wizard_state columns: started_at, completed_at, updated_at

Revision ID: 7f3a1e9b2c4d
Revises: 5d41c9a7e812
Create Date: 2026-04-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "7f3a1e9b2c4d"
down_revision: str = "5d41c9a7e812"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("wizard_state", schema=None) as batch_op:
        batch_op.drop_column("started_at")
        batch_op.drop_column("completed_at")
        batch_op.drop_column("updated_at")


def downgrade() -> None:
    with op.batch_alter_table("wizard_state", schema=None) as batch_op:
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
