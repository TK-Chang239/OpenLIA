"""Per-session response-length picker storage.

Adds ``chat_sessions.response_length`` (TEXT, nullable) to back the
Secretary composer's response-length picker (concise / normal / detailed).
``NULL`` keeps existing sessions on the model's default discipline; the
runtime injects an explicit length directive into the system prompt
only for ``"concise"`` or ``"detailed"``.

Revision ID: 20260510_1100_chat_session_response_length
Revises: 20260509_2030_chat_attachment_extracted_text
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260510_1100_chat_session_response_length"
down_revision: str | Sequence[str] | None = "20260509_2030_chat_attachment_extracted_text"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("chat_sessions") as batch:
        batch.add_column(
            sa.Column(
                "response_length",
                sa.String(length=16),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("chat_sessions") as batch:
        batch.drop_column("response_length")
