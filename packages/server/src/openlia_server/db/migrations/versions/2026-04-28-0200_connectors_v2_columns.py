"""Reshape connectors columns for v2.

Per spec §3.2:
- Drop credentials_ref (replaced by inline secrets map)
- Add secrets JSON NOT NULL DEFAULT '{}' (plaintext key->value map)
- Add cached_python_callables JSON NULL
- Add display_name VARCHAR(128) NOT NULL
- Add updated_at timestamp with onupdate
- Rename last_validated_at -> validated_at
- Relax source CHECK to include 'python_lib' and 'skill'

Revision ID: 20260428_0200_conn_v2
Revises: 20260428_0100_drop_ta
Create Date: 2026-04-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260428_0200_conn_v2"
down_revision: str | Sequence[str] | None = "20260428_0100_drop_ta"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("connectors") as batch:
        batch.drop_constraint("source", type_="check")
        batch.create_check_constraint(
            "source",
            "source IN ('built_in', 'remote_mcp', 'cli_mcp', 'python_lib', 'skill')",
        )
        batch.drop_column("credentials_ref")
        batch.add_column(
            sa.Column("secrets", sa.JSON(), nullable=False, server_default=sa.text("'{}'"))
        )
        batch.add_column(sa.Column("cached_python_callables", sa.JSON(), nullable=True))
        batch.add_column(
            sa.Column("display_name", sa.String(128), nullable=False, server_default="")
        )
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
        batch.alter_column("last_validated_at", new_column_name="validated_at")


def downgrade() -> None:
    with op.batch_alter_table("connectors") as batch:
        batch.alter_column("validated_at", new_column_name="last_validated_at")
        batch.drop_column("updated_at")
        batch.drop_column("display_name")
        batch.drop_column("cached_python_callables")
        batch.drop_column("secrets")
        batch.add_column(sa.Column("credentials_ref", sa.String(128), nullable=True))
        batch.drop_constraint("source", type_="check")
        batch.create_check_constraint(
            "source",
            "source IN ('built_in', 'remote_mcp', 'cli_mcp')",
        )
