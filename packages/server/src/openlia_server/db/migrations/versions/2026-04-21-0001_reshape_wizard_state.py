"""Reshape wizard_state for the Plan 10 setup wizard.

- current_step changes from Integer to String(32) (named step id).
- Adds completed_steps JSON array (default []).
- Adds active_session_token String(64) nullable.

Existing rows (created by `openlia wizard reset` pre-reshape) carry
integer current_step values; the upgrade maps known values to the new
string scheme and drops back to "mode" for unknown values.

Revision ID: 5d41c9a7e812
Revises: 3c8e1a2b4d9f
Create Date: 2026-04-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5d41c9a7e812"
down_revision: str | Sequence[str] | None = "3c8e1a2b4d9f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_INT_TO_STEP = {
    1: "mode",
    2: "account",
    3: "models",
    4: "data_providers",
    5: "policy",
    6: "review",
    7: "done",
    8: "done",
}


def upgrade() -> None:
    with op.batch_alter_table("wizard_state", schema=None) as batch_op:
        batch_op.add_column(sa.Column("completed_steps", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("active_session_token", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("_current_step_new", sa.String(length=32), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, current_step FROM wizard_state")).fetchall()
    for row in rows:
        mapped = _INT_TO_STEP.get(int(row.current_step), "mode")
        conn.execute(
            sa.text("UPDATE wizard_state SET _current_step_new = :v WHERE id = :id"),
            {"v": mapped, "id": row.id},
        )
    conn.execute(
        sa.text("UPDATE wizard_state SET completed_steps = :v WHERE completed_steps IS NULL"),
        {"v": "[]"},
    )

    with op.batch_alter_table("wizard_state", schema=None) as batch_op:
        batch_op.drop_column("current_step")
        batch_op.alter_column(
            "_current_step_new",
            new_column_name="current_step",
            existing_type=sa.String(length=32),
            nullable=False,
            server_default="mode",
        )
        batch_op.alter_column(
            "completed_steps",
            existing_type=sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        )


def downgrade() -> None:
    with op.batch_alter_table("wizard_state", schema=None) as batch_op:
        batch_op.add_column(sa.Column("_current_step_old", sa.Integer(), nullable=True))

    conn = op.get_bind()
    reverse = {v: k for k, v in _INT_TO_STEP.items() if v != "done"}
    reverse["done"] = 8
    rows = conn.execute(sa.text("SELECT id, current_step FROM wizard_state")).fetchall()
    for row in rows:
        mapped = reverse.get(row.current_step, 1)
        conn.execute(
            sa.text("UPDATE wizard_state SET _current_step_old = :v WHERE id = :id"),
            {"v": mapped, "id": row.id},
        )

    with op.batch_alter_table("wizard_state", schema=None) as batch_op:
        batch_op.drop_column("current_step")
        batch_op.alter_column(
            "_current_step_old",
            new_column_name="current_step",
            existing_type=sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        )
        batch_op.drop_column("active_session_token")
        batch_op.drop_column("completed_steps")
