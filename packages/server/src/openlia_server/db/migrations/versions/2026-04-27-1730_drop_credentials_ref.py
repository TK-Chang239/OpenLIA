"""Drop credentials_ref from connectors.

The cutover replaces this placeholder with api_key_encrypted (added in
the prior migration). credentials_ref was never populated.

Revision ID: 20260427_1730_drop_credref
Revises: 20260427_1700_connector_secrets
Create Date: 2026-04-27
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260427_1730_drop_credref"
down_revision: str | Sequence[str] | None = "20260427_1700_connector_secrets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("connectors", schema=None) as batch_op:
        batch_op.drop_column("credentials_ref")


def downgrade() -> None:
    import sqlalchemy as sa

    with op.batch_alter_table("connectors", schema=None) as batch_op:
        batch_op.add_column(sa.Column("credentials_ref", sa.String(length=128), nullable=True))
