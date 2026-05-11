"""Slice 9 (runtime spec) — structured columns on graph_artifact_summaries.

Adds claude-mem-style metadata fields so slice-12 retrieval can
pre-filter by cheap SQL (tone, horizon, entities_mentioned) before
running the cosine ranking pass over the embedding column. The
existing ``summary_text`` + ``embedding`` columns remain the canonical
embedded text; these new columns are purely additive.

Added columns:
- ``subject`` — the report subject (e.g. "NVDA")
- ``tagline`` — short report tagline
- ``findings_text`` — concatenated bullet findings
- ``entities_mentioned`` — JSON list of canonical entity IDs
- ``tone`` — one of bullish|bearish|neutral (nullable, CHECK)
- ``horizon`` — one of short|medium|long (nullable, CHECK)

Revision ID: 20260511_0100_graph_artifact_summary_structured
Revises: 20260511_0000_graph_extraction_runs
Create Date: 2026-05-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260511_0100_graph_artifact_summary_structured"
down_revision: str | Sequence[str] | None = "20260511_0000_graph_extraction_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("graph_artifact_summaries") as batch:
        batch.add_column(sa.Column("subject", sa.Text(), nullable=True))
        batch.add_column(sa.Column("tagline", sa.Text(), nullable=True))
        batch.add_column(sa.Column("findings_text", sa.Text(), nullable=True))
        batch.add_column(sa.Column("entities_mentioned", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("tone", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column("horizon", sa.String(length=16), nullable=True))
        batch.create_check_constraint(
            "ck_graph_artifact_summaries_tone",
            "tone IS NULL OR tone IN ('bullish','bearish','neutral')",
        )
        batch.create_check_constraint(
            "ck_graph_artifact_summaries_horizon",
            "horizon IS NULL OR horizon IN ('short','medium','long')",
        )


def downgrade() -> None:
    with op.batch_alter_table("graph_artifact_summaries") as batch:
        batch.drop_constraint("ck_graph_artifact_summaries_horizon", type_="check")
        batch.drop_constraint("ck_graph_artifact_summaries_tone", type_="check")
        batch.drop_column("horizon")
        batch.drop_column("tone")
        batch.drop_column("entities_mentioned")
        batch.drop_column("findings_text")
        batch.drop_column("tagline")
        batch.drop_column("subject")
