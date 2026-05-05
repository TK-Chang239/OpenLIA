"""Per-session connector + skill toggle storage.

Adds ``chat_sessions.disabled_connector_ids`` and
``chat_sessions.disabled_skill_ids`` (JSON arrays, default ``[]``) to
back the chat-input "Tools" dropdown. Empty lists keep existing
sessions on the all-on baseline; the dispatcher and skill registry
filter at the source so disabled entries never reach the router or
the model.

Revision ID: 20260504_1930_chat_session_disabled_lists
Revises: 20260504_1100_user_preferred_model
Create Date: 2026-05-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260504_1930_chat_session_disabled_lists"
down_revision: str | Sequence[str] | None = "20260504_1100_user_preferred_model"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("chat_sessions") as batch:
        batch.add_column(
            sa.Column(
                "disabled_connector_ids",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )
        batch.add_column(
            sa.Column(
                "disabled_skill_ids",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("chat_sessions") as batch:
        batch.drop_column("disabled_skill_ids")
        batch.drop_column("disabled_connector_ids")
