"""Cache server-side extracted text on chat_attachments.

Adds two columns to ``chat_attachments``:
  - ``extracted_text``: the result of upload-time text extraction (PDFs on
    non-pdf_native providers, all Office docs, plain text decode for text
    files). NULL for image attachments and for native-PDF attachments where
    raw bytes are passed through to the provider.
  - ``extracted_at``: timestamp the extraction was performed. Lets later
    background jobs re-extract or invalidate stale rows.

Backs the materializer's ``extracted_text_cache`` shortcut and the per-row
caching policy locked in composer-attachments-design.md (Q9).

Revision ID: 20260509_2030_chat_attachment_extracted_text
Revises: 20260505_1400_user_department_model_prefs
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260509_2030_chat_attachment_extracted_text"
down_revision: str | Sequence[str] | None = "20260505_1400_user_department_model_prefs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("chat_attachments") as batch:
        batch.add_column(sa.Column("extracted_text", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column(
                "extracted_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("chat_attachments") as batch:
        batch.drop_column("extracted_at")
        batch.drop_column("extracted_text")
