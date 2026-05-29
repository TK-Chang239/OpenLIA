"""report_v3.instructions_id column

Records which saved instruction profile a v3 run used, so a later
revision can re-resolve the same methodology and feed it back into the
revise prompt. Nullable — runs with no profile (and all pre-existing
rows) leave it NULL.

Revision ID: d2f4b6a8c0e1
Revises: c1e3a7d9f2b4
Create Date: 2026-05-29 15:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d2f4b6a8c0e1"
down_revision: str | Sequence[str] | None = "c1e3a7d9f2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "report_v3",
        sa.Column("instructions_id", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("report_v3", "instructions_id")
