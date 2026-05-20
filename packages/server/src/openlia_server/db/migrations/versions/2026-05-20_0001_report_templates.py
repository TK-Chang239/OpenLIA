"""Add report_templates table for user-uploaded templates.

Stores per-user TemplateSpec JSON plus the original source document so the
review UI can re-parse boundaries on demand.

Revision ID: 20260520_0001_report_templates
Revises: 20260517_0002_reports_failure_reason
Create Date: 2026-05-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260520_0001_report_templates"
down_revision: str | Sequence[str] | None = "20260517_0002_reports_failure_reason"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("template_spec_json", sa.JSON, nullable=False),
        sa.Column("source_markdown", sa.Text, nullable=True),
        sa.Column("source_doc_blob", sa.LargeBinary, nullable=True),
        sa.Column("source_doc_mime", sa.String(128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_report_templates_user_id",
        "report_templates",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_report_templates_user_id", table_name="report_templates")
    op.drop_table("report_templates")
