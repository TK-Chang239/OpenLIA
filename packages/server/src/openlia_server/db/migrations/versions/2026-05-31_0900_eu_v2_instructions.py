"""eu v2 instruction profiles

Adds the ``report_eu_instructions`` table backing free-form analyst
methodology profiles for the v2 Earnings Update engine, and a nullable
``instructions_id`` column on ``eu_v2_settings`` so a user can pin a
default profile. The table mirrors ``report_eu_templates`` for parity
(nullable ``user_id`` + ``is_builtin``) but stores free-form prose
(``body_text``) instead of a structured template spec.

Revision ID: 7f2a9c4be103
Revises: eae15acd2745
Create Date: 2026-05-31 09:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7f2a9c4be103"
down_revision: str | Sequence[str] | None = "eae15acd2745"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_eu_instructions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("source_doc_blob", sa.LargeBinary(), nullable=True),
        sa.Column("source_doc_mime", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_report_eu_instructions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_report_eu_instructions"),
    )
    op.create_index(
        "ix_report_eu_instructions_user_id",
        "report_eu_instructions",
        ["user_id"],
    )

    with op.batch_alter_table("eu_v2_settings") as batch_op:
        batch_op.add_column(
            sa.Column("instructions_id", sa.String(length=64), nullable=True),
        )


def downgrade() -> None:
    with op.batch_alter_table("eu_v2_settings") as batch_op:
        batch_op.drop_column("instructions_id")

    op.drop_index(
        "ix_report_eu_instructions_user_id",
        table_name="report_eu_instructions",
    )
    op.drop_table("report_eu_instructions")
