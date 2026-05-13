"""Add default_market_basket JSON column to user_prefs.

fix-chats — lets the user override the hardcoded Secretary snapshot basket
(tape / risk / macro / crypto sections). Nullable so existing rows stay
untouched; the service layer falls back to the locked Basket B default
when the column is null.

Revision ID: 20260513_0100_user_prefs_market_basket
Revises: 20260513_0000_remove_tiers
Create Date: 2026-05-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260513_0100_user_prefs_market_basket"
down_revision: str | Sequence[str] | None = "20260513_0000_remove_tiers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("user_prefs") as batch:
        batch.add_column(
            sa.Column(
                "default_market_basket",
                sa.JSON(),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("user_prefs") as batch:
        batch.drop_column("default_market_basket")
