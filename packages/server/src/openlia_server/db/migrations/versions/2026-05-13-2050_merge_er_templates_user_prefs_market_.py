"""merge er_templates + user_prefs_market_basket heads

Revision ID: a4a4885e1e30
Revises: 20260512_0000_er_templates, 20260513_0100_user_prefs_market_basket
Create Date: 2026-05-13 20:50:48.378640+00:00
"""
from __future__ import annotations

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = 'a4a4885e1e30'
down_revision: str | Sequence[str] | None = (
    "20260512_0000_er_templates",
    "20260513_0100_user_prefs_market_basket",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
