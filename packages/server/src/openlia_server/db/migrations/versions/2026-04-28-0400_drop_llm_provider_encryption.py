"""Drop encryption from llm_providers and web_search_providers.

Per spec §3.2 (post-Q3 edit): admin-hosted single-tenant threat model
makes column-level encryption pointless. Replace `api_key_encrypted`
with plaintext `api_key`.

Revision ID: 20260428_0400_plain
Revises: 20260428_0300_rcs
Create Date: 2026-04-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260428_0400_plain"
down_revision: str | Sequence[str] | None = "20260428_0300_rcs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("llm_providers") as batch:
        batch.alter_column("api_key_encrypted", new_column_name="api_key")
    with op.batch_alter_table("web_search_providers") as batch:
        batch.alter_column("api_key_encrypted", new_column_name="api_key")


def downgrade() -> None:
    with op.batch_alter_table("web_search_providers") as batch:
        batch.alter_column("api_key", new_column_name="api_key_encrypted")
    with op.batch_alter_table("llm_providers") as batch:
        batch.alter_column("api_key", new_column_name="api_key_encrypted")
