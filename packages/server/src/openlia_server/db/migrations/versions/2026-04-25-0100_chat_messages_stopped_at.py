"""Phase 12 — add ``chat_messages.stopped_at`` for partial-message persistence.

When a streaming response is cancelled (client disconnect, Stop button), the
assistant row is saved with ``stopped_at`` set so the chat-history rehydration
can show "Response stopped." beneath that turn.

Revision ID: 20260425_0100_chat_stopped_at
Revises: 20260424_0400_dp_category_mcp
Create Date: 2026-04-25 01:00:00+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260425_0100_chat_stopped_at"
down_revision: str | Sequence[str] | None = "20260424_0400_dp_category_mcp"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("chat_messages") as batch:
        batch.add_column(sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chat_messages") as batch:
        batch.drop_column("stopped_at")
