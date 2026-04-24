"""rs_classification_log audit table

Revision ID: 20260424_0100_rs
Revises: 20260424_0001_mr
Create Date: 2026-04-24 01:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260424_0100_rs"
down_revision: str | Sequence[str] | None = "20260424_0001_mr"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rs_classification_log",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("batch_id", sa.String(length=36), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("model_ref", sa.String(length=128), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_rs_classification_log_ticker_created",
        "rs_classification_log",
        ["ticker", "created_at"],
    )
    op.create_index(
        "ix_rs_classification_log_batch",
        "rs_classification_log",
        ["batch_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_rs_classification_log_batch", table_name="rs_classification_log")
    op.drop_index("ix_rs_classification_log_ticker_created", table_name="rs_classification_log")
    op.drop_table("rs_classification_log")
