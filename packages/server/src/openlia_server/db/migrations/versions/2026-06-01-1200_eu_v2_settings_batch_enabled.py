"""eu_v2_settings.batch_enabled

Revision ID: eu_batch_enabled_0601
Revises: enc_secrets_0601
Create Date: 2026-06-01 12:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "eu_batch_enabled_0601"
down_revision: str | Sequence[str] | None = "enc_secrets_0601"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "eu_v2_settings",
        sa.Column(
            "batch_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("eu_v2_settings", "batch_enabled")
