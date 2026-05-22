"""add pipeline_runs

Revision ID: a1b2c3d4e5f6
Revises: f3d303f0d092
Create Date: 2026-05-21 12:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f3d303f0d092"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("department", sa.String(length=64), nullable=False),
        sa.Column("template_id", sa.String(length=128), nullable=False),
        sa.Column("template_raw", sa.Text(), nullable=False),
        sa.Column(
            "template_format",
            sa.String(length=8),
            nullable=False,
            server_default=sa.text("'yaml'"),
        ),
        sa.Column("composer_inputs", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("paused_at_stage", sa.String(length=64), nullable=True),
        sa.Column("clarification_history", sa.JSON(), nullable=False),
        sa.Column("last_clarifier_output", sa.JSON(), nullable=True),
        sa.Column("last_clarifier_round", sa.Integer(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_pipeline_runs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["chat_sessions.id"],
            name=op.f("fk_pipeline_runs_session_id_chat_sessions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pipeline_runs")),
    )
    with op.batch_alter_table("pipeline_runs", schema=None) as batch_op:
        batch_op.create_index("ix_pipeline_runs_user_state", ["user_id", "state"], unique=False)
        batch_op.create_index("ix_pipeline_runs_session", ["session_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("pipeline_runs", schema=None) as batch_op:
        batch_op.drop_index("ix_pipeline_runs_session")
        batch_op.drop_index("ix_pipeline_runs_user_state")
    op.drop_table("pipeline_runs")
