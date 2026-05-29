"""earnings update v2 tables

Adds the nine tables that back the v2 Earnings Update engine: the six
``report_eu*`` artifact/template tables (forked from ``report_v3*`` with
the earnings deltas and no revision flow) and the three ``eu_v2_*``
control tables (watchlist, earnings schedule, per-user settings). Seeds
the single built-in ``eu_default`` template into ``report_eu_templates``.
No existing tables are touched.

Revision ID: eae15acd2745
Revises: c1e3a7d9f2b4
Create Date: 2026-05-29 23:55:23.466737+00:00
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.sqlite import JSON

# revision identifiers, used by Alembic.
revision: str = "eae15acd2745"
down_revision: str | Sequence[str] | None = "c1e3a7d9f2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_eu",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("subject", sa.String(length=256), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("trigger_kind", sa.String(length=16), nullable=False),
        sa.Column("fiscal_date", sa.String(length=32), nullable=True),
        sa.Column("template_id", sa.String(length=128), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("length", sa.String(length=16), nullable=False),
        sa.Column("provider_kind", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cover_json", sa.Text(), nullable=True),
        sa.Column("reasoning_effort", sa.String(length=16), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_report_eu_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_report_eu"),
    )
    op.create_index(
        "ix_report_eu_user_id_created_at",
        "report_eu",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_report_eu_user_id_status",
        "report_eu",
        ["user_id", "status"],
    )

    op.create_table(
        "report_eu_sections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("section_id", sa.String(length=128), nullable=False),
        sa.Column("section_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["report_eu.id"],
            name=op.f("fk_report_eu_sections_report_id_report_eu"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_report_eu_sections"),
        sa.UniqueConstraint(
            "report_id",
            "section_id",
            "version",
            name="uq_report_eu_sections_report_id_section_id_version",
        ),
    )
    op.create_index(
        "ix_report_eu_sections_report_id",
        "report_eu_sections",
        ["report_id"],
    )
    op.create_index(
        "ix_report_eu_sections_report_id_section_id_version",
        "report_eu_sections",
        ["report_id", "section_id", "version"],
    )

    op.create_table(
        "report_eu_charts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("chart_id", sa.String(length=128), nullable=False),
        sa.Column("chart_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("spec_json", sa.Text(), nullable=False),
        sa.Column("rendered_url", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["report_eu.id"],
            name=op.f("fk_report_eu_charts_report_id_report_eu"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_report_eu_charts"),
        sa.UniqueConstraint(
            "report_id",
            "chart_id",
            "version",
            name="uq_report_eu_charts_report_id_chart_id_version",
        ),
    )
    op.create_index(
        "ix_report_eu_charts_report_id",
        "report_eu_charts",
        ["report_id"],
    )
    op.create_index(
        "ix_report_eu_charts_report_id_chart_id_version",
        "report_eu_charts",
        ["report_id", "chart_id", "version"],
    )

    op.create_table(
        "report_eu_citations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("display_index", sa.Integer(), nullable=True),
        sa.Column("provenance_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["report_eu.id"],
            name=op.f("fk_report_eu_citations_report_id_report_eu"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_report_eu_citations"),
        sa.UniqueConstraint(
            "report_id",
            "source_id",
            name="uq_report_eu_citations_report_id_source_id",
        ),
    )
    op.create_index(
        "ix_report_eu_citations_report_id",
        "report_eu_citations",
        ["report_id"],
    )

    op.create_table(
        "report_eu_tool_call_log",
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
            ["report_eu.id"],
            name=op.f("fk_report_eu_tool_call_log_report_id_report_eu"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_report_eu_tool_call_log"),
    )
    op.create_index(
        "ix_report_eu_tool_call_log_report_id_turn_index",
        "report_eu_tool_call_log",
        ["report_id", "turn_index"],
    )

    op.create_table(
        "report_eu_templates",
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_report_eu_templates_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_report_eu_templates"),
    )
    op.create_index(
        "ix_report_eu_templates_user_id",
        "report_eu_templates",
        ["user_id"],
    )

    op.create_table(
        "eu_v2_watchlist",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("company_name", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_eu_v2_watchlist_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_eu_v2_watchlist"),
        sa.UniqueConstraint("user_id", "ticker", name="uq_eu_v2_watchlist_user_ticker"),
    )
    op.create_index(
        "ix_eu_v2_watchlist_user_id",
        "eu_v2_watchlist",
        ["user_id"],
    )

    op.create_table(
        "eu_v2_earnings_schedule",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("fiscal_date", sa.String(length=32), nullable=False),
        sa.Column("release_timing", sa.String(length=16), nullable=True),
        sa.Column("eps_estimate", sa.String(length=32), nullable=True),
        sa.Column("revenue_estimate", sa.String(length=32), nullable=True),
        sa.Column("scheduled_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("report_id", sa.String(length=36), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_eu_v2_earnings_schedule_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_eu_v2_earnings_schedule"),
        sa.UniqueConstraint(
            "user_id",
            "ticker",
            "fiscal_date",
            name="uq_eu_v2_earnings_schedule_user_ticker_fiscal",
        ),
    )
    op.create_index(
        "ix_eu_v2_earnings_schedule_status_run_at",
        "eu_v2_earnings_schedule",
        ["status", "scheduled_run_at"],
    )
    op.create_index(
        "ix_eu_v2_earnings_schedule_user_id",
        "eu_v2_earnings_schedule",
        ["user_id"],
    )

    op.create_table(
        "eu_v2_settings",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("provider_kind", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("template_id", sa.String(length=64), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False, server_default="en"),
        sa.Column("length", sa.String(length=16), nullable=False, server_default="normal"),
        sa.Column("reasoning_effort", sa.String(length=16), nullable=True),
        sa.Column("financial_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("calendar_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "web_search_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_eu_v2_settings_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_eu_v2_settings"),
    )

    # Seed the single built-in default template by importing the in-code
    # TemplateSpec builder at migration time, mirroring the v3 templates
    # migration. Keeps the seed adjacent to the code that defines it.
    from openlia.llm.runtime.report_eu.default_template import build_default_template

    spec = build_default_template()
    now = datetime.now(UTC)
    templates_table = sa.table(
        "report_eu_templates",
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
    op.bulk_insert(
        templates_table,
        [
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
        ],
    )


def downgrade() -> None:
    op.drop_table("eu_v2_settings")

    op.drop_index(
        "ix_eu_v2_earnings_schedule_user_id",
        table_name="eu_v2_earnings_schedule",
    )
    op.drop_index(
        "ix_eu_v2_earnings_schedule_status_run_at",
        table_name="eu_v2_earnings_schedule",
    )
    op.drop_table("eu_v2_earnings_schedule")

    op.drop_index("ix_eu_v2_watchlist_user_id", table_name="eu_v2_watchlist")
    op.drop_table("eu_v2_watchlist")

    op.drop_index("ix_report_eu_templates_user_id", table_name="report_eu_templates")
    op.drop_table("report_eu_templates")

    op.drop_index(
        "ix_report_eu_tool_call_log_report_id_turn_index",
        table_name="report_eu_tool_call_log",
    )
    op.drop_table("report_eu_tool_call_log")

    op.drop_index("ix_report_eu_citations_report_id", table_name="report_eu_citations")
    op.drop_table("report_eu_citations")

    op.drop_index(
        "ix_report_eu_charts_report_id_chart_id_version",
        table_name="report_eu_charts",
    )
    op.drop_index("ix_report_eu_charts_report_id", table_name="report_eu_charts")
    op.drop_table("report_eu_charts")

    op.drop_index(
        "ix_report_eu_sections_report_id_section_id_version",
        table_name="report_eu_sections",
    )
    op.drop_index("ix_report_eu_sections_report_id", table_name="report_eu_sections")
    op.drop_table("report_eu_sections")

    op.drop_index("ix_report_eu_user_id_status", table_name="report_eu")
    op.drop_index("ix_report_eu_user_id_created_at", table_name="report_eu")
    op.drop_table("report_eu")
