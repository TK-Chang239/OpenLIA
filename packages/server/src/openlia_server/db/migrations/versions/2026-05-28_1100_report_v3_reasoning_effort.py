"""report_v3: add reasoning_effort column

Persists the user-selected extended-thinking knob ("medium" | "high")
at dispatch time, or NULL when reasoning was off. The chat-thread
chips read this on page reload so the "Reasoning" chip survives
re-mounting without an in-memory snapshot.

Revision ID: f9a2c5d8e7b3
Revises: e7c4a9b1d2f5
Create Date: 2026-05-28 11:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f9a2c5d8e7b3"
down_revision: str | Sequence[str] | None = "e7c4a9b1d2f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("report_v3") as batch:
        batch.add_column(
            sa.Column("reasoning_effort", sa.String(length=16), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("report_v3") as batch:
        batch.drop_column("reasoning_effort")
