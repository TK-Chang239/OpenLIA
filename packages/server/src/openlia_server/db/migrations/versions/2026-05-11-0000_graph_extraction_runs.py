"""Slice 4 — graph extraction audit table + per-user extraction time.

Adds:
- ``user_prefs.graph_extraction_time`` (HH:MM, default "03:00") — the
  wall-clock time in the user's timezone at which the nightly job runs.
- ``graph_extraction_runs`` — audit log; one row per pipeline invocation
  (scheduled or admin-forced). Watermark for "new since last run" =
  latest ``started_at`` per user where ``error IS NULL``.

Revision ID: 20260511_0000_graph_extraction_runs
Revises: 20260510_2400_entity_trigger_flag
Create Date: 2026-05-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260511_0000_graph_extraction_runs"
down_revision: str | Sequence[str] | None = "20260510_2400_entity_trigger_flag"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("user_prefs") as batch:
        batch.add_column(
            sa.Column(
                "graph_extraction_time",
                sa.String(length=5),
                nullable=False,
                server_default="03:00",
            )
        )

    op.create_table(
        "graph_extraction_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("model_id", sa.String(length=64), nullable=True),
        sa.Column(
            "proposals_inserted",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "sessions_processed",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("error", sa.String(length=256), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_graph_extraction_runs_user_id_started_at",
        "graph_extraction_runs",
        ["user_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_graph_extraction_runs_user_id_started_at",
        table_name="graph_extraction_runs",
    )
    op.drop_table("graph_extraction_runs")
    with op.batch_alter_table("user_prefs") as batch:
        batch.drop_column("graph_extraction_time")
