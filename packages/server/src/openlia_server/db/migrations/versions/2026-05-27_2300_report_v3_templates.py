"""report_v3_templates table + builtin seed

Adds the ``report_v3_templates`` table v3 reads when resolving the
template a run should follow. Seeds the three built-in templates
(initiation_default, update_default, sector_research_default) by
serializing the in-code ``TemplateSpec`` definitions so the runtime
goes through the same code path for built-ins and user uploads.

Revision ID: b8d2f4e6c1a9
Revises: a5b7c9d1e3f0
Create Date: 2026-05-27 23:00:00.000000+00:00
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.sqlite import JSON

revision: str = "b8d2f4e6c1a9"
down_revision: str | Sequence[str] | None = "a5b7c9d1e3f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_v3_templates",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("is_builtin", sa.Boolean(), nullable=False),
        sa.Column("template_spec_json", JSON(), nullable=False),
        sa.Column("source_markdown", sa.Text(), nullable=True),
        sa.Column("source_doc_blob", sa.LargeBinary(), nullable=True),
        sa.Column("source_doc_mime", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_report_v3_templates"),
    )
    op.create_index(
        "ix_report_v3_templates_user_id",
        "report_v3_templates",
        ["user_id"],
    )

    # Seed builtins by importing the in-code TemplateSpec definitions at
    # migration time. Keeping the seed adjacent to the code that defines
    # the builtins avoids hand-maintaining a duplicate JSON blob here.
    from openlia.llm.runtime.report_v2_3.schemas import ReportType
    from openlia.llm.runtime.report_v2_3.templates.builtins import BUILTIN_TEMPLATES

    now = datetime.now(UTC)
    templates_table = sa.table(
        "report_v3_templates",
        sa.column("id", sa.String),
        sa.column("user_id", sa.String),
        sa.column("name", sa.String),
        sa.column("is_builtin", sa.Boolean),
        sa.column("template_spec_json", JSON),
        sa.column("source_markdown", sa.Text),
        sa.column("source_doc_blob", sa.LargeBinary),
        sa.column("source_doc_mime", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("deleted_at", sa.DateTime(timezone=True)),
    )
    rows = []
    for report_type in (
        ReportType.INITIATION,
        ReportType.UPDATE,
        ReportType.SECTOR_RESEARCH,
    ):
        spec = BUILTIN_TEMPLATES[report_type]
        rows.append(
            {
                "id": spec.template_id,
                "user_id": None,
                "name": spec.name,
                "is_builtin": True,
                "template_spec_json": json.loads(spec.model_dump_json()),
                "source_markdown": None,
                "source_doc_blob": None,
                "source_doc_mime": None,
                "created_at": now,
                "updated_at": now,
                "deleted_at": None,
            }
        )
    op.bulk_insert(templates_table, rows)


def downgrade() -> None:
    op.drop_index("ix_report_v3_templates_user_id", "report_v3_templates")
    op.drop_table("report_v3_templates")
