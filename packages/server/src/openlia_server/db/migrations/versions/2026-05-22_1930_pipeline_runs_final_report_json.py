"""pipeline_runs.final_html → final_report_json

Switches v2.2 completed-run storage from a rendered HTML string to the
structured ReportV2 JSON payload. The HTML form was a one-way collapse of
the typed-block dicts; the frontend can't reconstruct charts or branded
components from it, so v2 reports rendered as a plain wall of text. JSON
keeps the typed blocks intact so the v1 React renderer can take over.

Revision ID: e5f7a9b1c2d4
Revises: d3e5f7a9b1c2
Create Date: 2026-05-22 19:30:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f7a9b1c2d4"
down_revision: str | Sequence[str] | None = "d3e5f7a9b1c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("pipeline_runs", schema=None) as batch_op:
        batch_op.drop_column("final_html_at")
        batch_op.drop_column("final_html")
        batch_op.add_column(sa.Column("final_report_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("final_report_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("pipeline_runs", schema=None) as batch_op:
        batch_op.drop_column("final_report_at")
        batch_op.drop_column("final_report_json")
        batch_op.add_column(sa.Column("final_html", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("final_html_at", sa.DateTime(timezone=True), nullable=True))
