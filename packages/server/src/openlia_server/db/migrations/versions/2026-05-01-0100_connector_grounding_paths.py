"""Add user-supplied grounding_paths to connectors.

Lets the user restrict the resolver's filesystem-tool view to a hand-picked
subset (e.g. ``["docs", "schemas"]``) instead of the whole clone. Stored as
JSON array of relative paths under the grounding clone root, or absolute
local paths.

Revision ID: 20260501_0100_grounding_paths
Revises: 20260430_0100_grounding
Create Date: 2026-05-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260501_0100_grounding_paths"
down_revision: str | Sequence[str] | None = "20260430_0100_grounding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("connectors") as batch:
        batch.add_column(sa.Column("grounding_paths", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("connectors") as batch:
        batch.drop_column("grounding_paths")
