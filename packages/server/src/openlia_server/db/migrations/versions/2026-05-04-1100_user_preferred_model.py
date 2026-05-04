"""User-level preferred LLM model.

Adds ``user_prefs.preferred_model_id`` (nullable FK to ``llm_models.id``)
so a user can pick a model once that applies across every chat session
and department. Null = fall back to tier resolution. ``ondelete=SET NULL``
preserves the user pref row if a model is removed from the catalog.

Revision ID: 20260504_1100_user_preferred_model
Revises: 20260504_0900_chat_session_model
Create Date: 2026-05-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260504_1100_user_preferred_model"
down_revision: str | Sequence[str] | None = "20260504_0900_chat_session_model"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("user_prefs") as batch:
        batch.add_column(sa.Column("preferred_model_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_user_prefs_preferred_model_id_llm_models",
            "llm_models",
            ["preferred_model_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("user_prefs") as batch:
        batch.drop_constraint("fk_user_prefs_preferred_model_id_llm_models", type_="foreignkey")
        batch.drop_column("preferred_model_id")
