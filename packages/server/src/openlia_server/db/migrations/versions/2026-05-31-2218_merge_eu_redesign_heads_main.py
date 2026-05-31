"""merge eu redesign heads + main

Revision ID: 984fc020381a
Revises: 79187a917367, 898ac749e884
Create Date: 2026-05-31 22:18:16.890878+00:00
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '984fc020381a'
down_revision: str | Sequence[str] | None = ('79187a917367', '898ac749e884')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
