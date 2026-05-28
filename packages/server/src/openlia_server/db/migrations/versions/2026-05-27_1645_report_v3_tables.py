"""report_v3 tables

Adds the five normalized tables that persist a v3 equity-research
run: the top-level run row, the written sections, the emitted charts,
the bibliography roll-up, and the per-tool-call audit log. v2.3
tables are not touched.

Revision ID: a5b7c9d1e3f0
Revises: c2d4e5f6a7b8
Create Date: 2026-05-27 16:45:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a5b7c9d1e3f0"
down_revision: str | Sequence[str] | None = "c2d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_v3",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("subject", sa.String(length=256), nullable=False),
        sa.Column("template_id", sa.String(length=128), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("length", sa.String(length=16), nullable=False),
        sa.Column("provider_kind", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_report_v3_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_report_v3"),
    )
    op.create_index(
        "ix_report_v3_user_id_created_at",
        "report_v3",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_report_v3_user_id_status",
        "report_v3",
        ["user_id", "status"],
    )

    op.create_table(
        "report_v3_sections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("section_id", sa.String(length=128), nullable=False),
        sa.Column("section_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["report_v3.id"],
            name=op.f("fk_report_v3_sections_report_id_report_v3"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_report_v3_sections"),
        sa.UniqueConstraint(
            "report_id",
            "section_id",
            name="uq_report_v3_sections_report_id_section_id",
        ),
    )
    op.create_index(
        "ix_report_v3_sections_report_id",
        "report_v3_sections",
        ["report_id"],
    )

    op.create_table(
        "report_v3_charts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("chart_id", sa.String(length=128), nullable=False),
        sa.Column("chart_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("spec_json", sa.Text(), nullable=False),
        sa.Column("rendered_url", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["report_v3.id"],
            name=op.f("fk_report_v3_charts_report_id_report_v3"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_report_v3_charts"),
        sa.UniqueConstraint(
            "report_id",
            "chart_id",
            name="uq_report_v3_charts_report_id_chart_id",
        ),
    )
    op.create_index(
        "ix_report_v3_charts_report_id",
        "report_v3_charts",
        ["report_id"],
    )

    op.create_table(
        "report_v3_citations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("display_index", sa.Integer(), nullable=True),
        sa.Column("provenance_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["report_v3.id"],
            name=op.f("fk_report_v3_citations_report_id_report_v3"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_report_v3_citations"),
        sa.UniqueConstraint(
            "report_id",
            "source_id",
            name="uq_report_v3_citations_report_id_source_id",
        ),
    )
    op.create_index(
        "ix_report_v3_citations_report_id",
        "report_v3_citations",
        ["report_id"],
    )

    op.create_table(
        "report_v3_tool_call_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("arguments_json", sa.Text(), nullable=False),
        sa.Column("result_summary", sa.Text(), nullable=False),
        sa.Column("provenance_json", sa.Text(), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wall_time_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["report_v3.id"],
            name=op.f("fk_report_v3_tool_call_log_report_id_report_v3"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_report_v3_tool_call_log"),
    )
    op.create_index(
        "ix_report_v3_tool_call_log_report_id_turn_index",
        "report_v3_tool_call_log",
        ["report_id", "turn_index"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_report_v3_tool_call_log_report_id_turn_index",
        table_name="report_v3_tool_call_log",
    )
    op.drop_table("report_v3_tool_call_log")

    op.drop_index("ix_report_v3_citations_report_id", table_name="report_v3_citations")
    op.drop_table("report_v3_citations")

    op.drop_index("ix_report_v3_charts_report_id", table_name="report_v3_charts")
    op.drop_table("report_v3_charts")

    op.drop_index("ix_report_v3_sections_report_id", table_name="report_v3_sections")
    op.drop_table("report_v3_sections")

    op.drop_index("ix_report_v3_user_id_status", table_name="report_v3")
    op.drop_index("ix_report_v3_user_id_created_at", table_name="report_v3")
    op.drop_table("report_v3")
