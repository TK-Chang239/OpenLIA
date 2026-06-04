"""Drop legacy retail-sentiment per-post pipeline tables.

Removes ``rs_snapshots`` and ``rs_classification_log``, which were written by
the inert ``RsRunner`` / ``LlmClassifier`` pipeline. The new dashboard engine
(``report_dash_rs``) writes only to ``rs_dashboard_cache``; these tables are
no longer populated or read by any live code.

Revision ID: drop_legacy_rs_tables
Revises: rs_dashboard_cache
Create Date: 2026-06-04 00:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "drop_legacy_rs_tables"
down_revision: str | Sequence[str] | None = "rs_dashboard_cache"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop rs_snapshots index then table.
    with op.batch_alter_table("rs_snapshots", schema=None) as batch_op:
        batch_op.drop_index("ix_rs_snapshots_ticker_captured")
    op.drop_table("rs_snapshots")

    # Drop rs_classification_log indexes then table.
    op.drop_index("ix_rs_classification_log_ticker_created", table_name="rs_classification_log")
    op.drop_index("ix_rs_classification_log_batch", table_name="rs_classification_log")
    op.drop_table("rs_classification_log")


def downgrade() -> None:
    # Recreate rs_classification_log.
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

    # Recreate rs_snapshots.
    op.create_table(
        "rs_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("snapshot_data", sa.JSON(), nullable=False),
        sa.Column("source_breakdown", sa.JSON(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rs_snapshots")),
    )
    with op.batch_alter_table("rs_snapshots", schema=None) as batch_op:
        batch_op.create_index(
            "ix_rs_snapshots_ticker_captured",
            ["ticker", "captured_at"],
            unique=False,
        )
