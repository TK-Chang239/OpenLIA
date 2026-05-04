"""Per-session model override.

Adds ``chat_sessions.model_id`` (nullable FK to ``llm_models.id``) so a user
can pick which LLM a given chat session runs against. Null = fall back to
the tier-based resolver chain. ``ondelete=SET NULL`` so removing a model
from the catalog leaves the session intact and reverts to the tier default.

Revision ID: 20260504_0900_chat_session_model
Revises: 9b6c0eb8b946
Create Date: 2026-05-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260504_0900_chat_session_model"
down_revision: str | Sequence[str] | None = "9b6c0eb8b946"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("chat_sessions") as batch:
        batch.add_column(sa.Column("model_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_chat_sessions_model_id_llm_models",
            "llm_models",
            ["model_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("chat_sessions") as batch:
        batch.drop_constraint("fk_chat_sessions_model_id_llm_models", type_="foreignkey")
        batch.drop_column("model_id")
