"""reshape_wizard_state — current_step -> String, add completed_steps + active_session_token

Revision ID: 3c0b1b6f475a
Revises: f2a9566f7bf9
Create Date: 2026-04-22 17:44:47.619577+00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = '3c0b1b6f475a'
down_revision: str = 'f2a9566f7bf9'
branch_labels = None
depends_on = None

_STEP_ORDER = ["mode", "identity", "admin", "models", "providers", "access_control", "review", "done"]


def upgrade() -> None:
    with op.batch_alter_table("wizard_state") as batch_op:
        batch_op.add_column(sa.Column("completed_steps", sa.JSON(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("active_session_token", sa.String(length=64), nullable=True))
        batch_op.alter_column(
            "current_step",
            existing_type=sa.Integer(),
            type_=sa.String(length=32),
            existing_nullable=False,
            server_default="mode",
            postgresql_using="'mode'",
        )
        batch_op.drop_column("status")
        batch_op.drop_column("mode")
        batch_op.drop_column("started_at")
        batch_op.drop_column("completed_at")
        batch_op.drop_column("updated_at")
    op.execute(
        "UPDATE wizard_state SET current_step = 'mode' WHERE current_step NOT IN ("
        + ",".join(f"'{s}'" for s in _STEP_ORDER)
        + ")"
    )


def downgrade() -> None:
    with op.batch_alter_table("wizard_state") as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(length=32), nullable=False, server_default="not_started"))
        batch_op.add_column(sa.Column("mode", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("started_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("completed_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
        batch_op.alter_column(
            "current_step",
            existing_type=sa.String(length=32),
            type_=sa.Integer(),
            existing_nullable=False,
            server_default="1",
            postgresql_using="1",
        )
        batch_op.drop_column("active_session_token")
        batch_op.drop_column("completed_steps")
    op.execute("UPDATE wizard_state SET current_step = 1")
