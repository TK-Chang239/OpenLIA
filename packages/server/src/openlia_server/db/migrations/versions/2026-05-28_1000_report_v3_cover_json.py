"""report_v3: add cover_json column for v3 cover synthesis

Adds a nullable ``cover_json`` text column to the ``report_v3`` table.
Stores the JSON-serialised ``CoverSpec`` from the model's
``set_cover`` tool call (PR9). Older rows + runs where the model
skipped ``set_cover`` keep ``NULL`` and render with the bare cover
(just subject + template-derived eyebrow).

Revision ID: e7c4a9b1d2f5
Revises: d3f8a6e2c9b4
Create Date: 2026-05-28 10:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7c4a9b1d2f5"
down_revision: str | Sequence[str] | None = "d3f8a6e2c9b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("report_v3") as batch:
        batch.add_column(sa.Column("cover_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("report_v3") as batch:
        batch.drop_column("cover_json")
