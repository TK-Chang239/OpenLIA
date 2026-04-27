"""Add api_key_encrypted to connectors.

See docs/superpowers/specs/2026-04-27-connector-cutover-design.md §5.1.
Mirrors the LLMProvider / WebSearchProvider pattern: AES-256-GCM with
the row id as AAD, applied at the ORM layer (set_credential /
get_credential — added in H2.2).

Revision ID: 20260427_1700_connector_secrets
Revises: 20260426_1700_connectors
Create Date: 2026-04-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260427_1700_connector_secrets"
down_revision: str | Sequence[str] | None = "20260426_1700_connectors"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("connectors", schema=None) as batch_op:
        batch_op.add_column(sa.Column("api_key_encrypted", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("connectors", schema=None) as batch_op:
        batch_op.drop_column("api_key_encrypted")
