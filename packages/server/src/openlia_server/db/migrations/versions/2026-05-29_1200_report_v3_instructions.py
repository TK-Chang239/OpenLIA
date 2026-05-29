"""report_v3_instructions table

Adds the ``report_v3_instructions`` table backing saved instruction
profiles — free-form analyst methodology fed verbatim into the v3
system prompt. Orthogonal to templates: a run pairs any template (or
none) with any profile. No built-ins are seeded.

Revision ID: c1e3a7d9f2b4
Revises: f9a2c5d8e7b3
Create Date: 2026-05-29 12:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c1e3a7d9f2b4"
down_revision: str | Sequence[str] | None = "f9a2c5d8e7b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_v3_instructions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("is_builtin", sa.Boolean(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("source_doc_blob", sa.LargeBinary(), nullable=True),
        sa.Column("source_doc_mime", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_report_v3_instructions"),
    )
    op.create_index(
        "ix_report_v3_instructions_user_id",
        "report_v3_instructions",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_report_v3_instructions_user_id", "report_v3_instructions")
    op.drop_table("report_v3_instructions")
