"""eu_v2_batch_run.state_json (resume snapshot)

Revision ID: eu_batch_state_0602
Revises: eu_batch_tables_0601
Create Date: 2026-06-02 09:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "eu_batch_state_0602"
down_revision: str | Sequence[str] | None = "eu_batch_tables_0601"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("eu_v2_batch_run", sa.Column("state_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("eu_v2_batch_run", "state_json")
