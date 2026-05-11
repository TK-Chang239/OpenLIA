"""Slice 1 (runtime spec) — add ``timezone`` + ``timezone_source`` to user_prefs.

Single source of truth for user-local clock across all OpenLIA features
(MB/EU/RS schedules, graph extraction, etc.). ``source='auto'`` means
the value came from the browser; ``'manual'`` means the user picked it
in Settings — once manual, browser drift is ignored.

Revision ID: 20260510_2330_user_timezone
Revises: 20260510_2230_graph_vectors
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260510_2330_user_timezone"
down_revision: str | Sequence[str] | None = "20260510_2230_graph_vectors"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("user_prefs") as batch:
        batch.add_column(
            sa.Column(
                "timezone",
                sa.String(length=64),
                nullable=False,
                server_default="UTC",
            )
        )
        batch.add_column(
            sa.Column(
                "timezone_source",
                sa.String(length=8),
                nullable=False,
                server_default="auto",
            )
        )
        batch.create_check_constraint(
            "ck_user_prefs_timezone_source",
            "timezone_source IN ('auto','manual')",
        )


def downgrade() -> None:
    with op.batch_alter_table("user_prefs") as batch:
        batch.drop_constraint("ck_user_prefs_timezone_source", type_="check")
        batch.drop_column("timezone_source")
        batch.drop_column("timezone")
