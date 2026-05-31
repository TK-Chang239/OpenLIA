"""eu v2 enabled_provider_ids on eu_v2_settings

Replaces the three coarse connector booleans (``financial_enabled`` /
``calendar_enabled`` / ``web_search_enabled``) storage model with a
provider-id set: a JSON ``enabled_provider_ids`` column plus the kept
``web_search_enabled`` boolean. Existing rows where either the financial
or calendar connector was on map to ``["eodhd"]`` (the curated EODHD
provider that backed both today); rows with both off map to ``[]``.

Revision ID: 898ac749e884
Revises: 7f2a9c4be103
Create Date: 2026-05-31 12:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "898ac749e884"
down_revision: str | Sequence[str] | None = "7f2a9c4be103"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("eu_v2_settings") as batch_op:
        batch_op.add_column(
            sa.Column(
                "enabled_provider_ids",
                sa.JSON(),
                nullable=False,
                server_default="[]",
            ),
        )

    # Data-migrate existing rows before dropping the source columns: any
    # row with the financial or calendar connector on maps to the curated
    # EODHD provider.
    op.execute(
        sa.text(
            "UPDATE eu_v2_settings SET enabled_provider_ids = '[\"eodhd\"]' "
            "WHERE financial_enabled = 1 OR calendar_enabled = 1"
        )
    )

    with op.batch_alter_table("eu_v2_settings") as batch_op:
        batch_op.drop_column("financial_enabled")
        batch_op.drop_column("calendar_enabled")


def downgrade() -> None:
    with op.batch_alter_table("eu_v2_settings") as batch_op:
        batch_op.add_column(
            sa.Column(
                "financial_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )
        batch_op.add_column(
            sa.Column(
                "calendar_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )

    # Re-derive the two booleans: both true iff EODHD was in the set.
    op.execute(
        sa.text(
            "UPDATE eu_v2_settings SET financial_enabled = "
            "CASE WHEN enabled_provider_ids LIKE '%\"eodhd\"%' THEN 1 ELSE 0 END, "
            "calendar_enabled = "
            "CASE WHEN enabled_provider_ids LIKE '%\"eodhd\"%' THEN 1 ELSE 0 END"
        )
    )

    with op.batch_alter_table("eu_v2_settings") as batch_op:
        batch_op.drop_column("enabled_provider_ids")
