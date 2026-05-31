"""report_v3_revisions table + section/chart versioning

Adds the versioning columns to ``report_v3_sections`` and
``report_v3_charts`` (``revision_id`` FK + ``version``), creates the
new ``report_v3_revisions`` table, and replaces the old
``(report_id, section_id)`` / ``(report_id, chart_id)`` unique
constraints with the new ``(report_id, section_id, version)`` /
``(report_id, chart_id, version)`` versions.

Existing data is backfilled with ``version=1`` and ``revision_id=NULL``
so any v3 reports already in the DB keep rendering exactly the same
way.

Revision ID: c7e3a5b9d4f1
Revises: b8d2f4e6c1a9
Create Date: 2026-05-27 23:30:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7e3a5b9d4f1"
down_revision: str | Sequence[str] | None = "b8d2f4e6c1a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Revisions table first so the FK from sections/charts has a target.
    op.create_table(
        "report_v3_revisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("revision_index", sa.Integer(), nullable=False),
        sa.Column("request", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["report_id"], ["report_v3.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_report_v3_revisions"),
        sa.UniqueConstraint(
            "report_id",
            "revision_index",
            name="uq_report_v3_revisions_report_id_revision_index",
        ),
    )
    op.create_index(
        "ix_report_v3_revisions_report_id_created_at",
        "report_v3_revisions",
        ["report_id", "created_at"],
    )
    op.create_index(
        "ix_report_v3_revisions_report_id_status",
        "report_v3_revisions",
        ["report_id", "status"],
    )

    # Sections: add columns, drop old unique, add new unique + index.
    # SQLite doesn't support DROP CONSTRAINT directly — use batch mode
    # so Alembic generates the table-rebuild dance.
    with op.batch_alter_table("report_v3_sections") as batch:
        batch.add_column(
            sa.Column(
                "revision_id",
                sa.String(length=36),
                sa.ForeignKey("report_v3_revisions.id", ondelete="CASCADE"),
                nullable=True,
            )
        )
        batch.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch.drop_constraint(
            "uq_report_v3_sections_report_id_section_id",
            type_="unique",
        )
        batch.create_unique_constraint(
            "uq_report_v3_sections_report_id_section_id_version",
            ["report_id", "section_id", "version"],
        )
    op.create_index(
        "ix_report_v3_sections_report_id_section_id_version",
        "report_v3_sections",
        ["report_id", "section_id", "version"],
    )

    # Charts: same migration shape as sections.
    with op.batch_alter_table("report_v3_charts") as batch:
        batch.add_column(
            sa.Column(
                "revision_id",
                sa.String(length=36),
                sa.ForeignKey("report_v3_revisions.id", ondelete="CASCADE"),
                nullable=True,
            )
        )
        batch.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch.drop_constraint(
            "uq_report_v3_charts_report_id_chart_id",
            type_="unique",
        )
        batch.create_unique_constraint(
            "uq_report_v3_charts_report_id_chart_id_version",
            ["report_id", "chart_id", "version"],
        )
    op.create_index(
        "ix_report_v3_charts_report_id_chart_id_version",
        "report_v3_charts",
        ["report_id", "chart_id", "version"],
    )


def downgrade() -> None:
    with op.batch_alter_table("report_v3_charts") as batch:
        batch.drop_constraint(
            "uq_report_v3_charts_report_id_chart_id_version",
            type_="unique",
        )
        batch.create_unique_constraint(
            "uq_report_v3_charts_report_id_chart_id",
            ["report_id", "chart_id"],
        )
        batch.drop_column("version")
        batch.drop_column("revision_id")
    op.drop_index(
        "ix_report_v3_charts_report_id_chart_id_version",
        table_name="report_v3_charts",
    )

    with op.batch_alter_table("report_v3_sections") as batch:
        batch.drop_constraint(
            "uq_report_v3_sections_report_id_section_id_version",
            type_="unique",
        )
        batch.create_unique_constraint(
            "uq_report_v3_sections_report_id_section_id",
            ["report_id", "section_id"],
        )
        batch.drop_column("version")
        batch.drop_column("revision_id")
    op.drop_index(
        "ix_report_v3_sections_report_id_section_id_version",
        table_name="report_v3_sections",
    )

    op.drop_index(
        "ix_report_v3_revisions_report_id_status",
        table_name="report_v3_revisions",
    )
    op.drop_index(
        "ix_report_v3_revisions_report_id_created_at",
        table_name="report_v3_revisions",
    )
    op.drop_table("report_v3_revisions")
