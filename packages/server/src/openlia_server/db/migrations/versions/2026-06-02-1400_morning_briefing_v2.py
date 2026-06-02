"""morning briefing v2 schema

Adds the seven ``report_mb*`` tables backing the v2 Morning Briefing
engine (forked from ``report_eu*`` with the MB deltas: no ticker /
fiscal_date, plus ``trigger_kind`` / ``schedule_id`` /
``instructions_id``), extends ``mb_schedules`` with per-schedule config
binding, adds the ``repo_items.mb_v2_report_id`` polymorphic target, and
seeds the single built-in ``mb_default`` template. Drops the obsolete
per-user ``mb_user_configs`` table — MB v2 is fully
template/instructions-driven and schedule-bound, so there is no longer a
single per-user config row.

Revision ID: morning_briefing_v2
Revises: eu_batch_state_0602
Create Date: 2026-06-02 14:00:00.000000+00:00
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.sqlite import JSON

# revision identifiers, used by Alembic.
revision: str = "morning_briefing_v2"
down_revision: str | Sequence[str] | None = "eu_batch_state_0602"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- 1. report_mb* artifact / config tables -------------------------
    op.create_table(
        "report_mb",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("subject", sa.String(length=256), nullable=False),
        sa.Column("trigger_kind", sa.String(length=16), nullable=False),
        sa.Column("schedule_id", sa.String(length=36), nullable=True),
        sa.Column("template_id", sa.String(length=128), nullable=False),
        sa.Column("instructions_id", sa.String(length=128), nullable=True),
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
            name=op.f("fk_report_mb_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["mb_schedules.id"],
            name=op.f("fk_report_mb_schedule_id_mb_schedules"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_report_mb"),
    )
    op.create_index(
        "ix_report_mb_user_id_created_at",
        "report_mb",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_report_mb_user_id_status",
        "report_mb",
        ["user_id", "status"],
    )

    op.create_table(
        "report_mb_sections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("section_id", sa.String(length=128), nullable=False),
        sa.Column("section_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["report_mb.id"],
            name=op.f("fk_report_mb_sections_report_id_report_mb"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_report_mb_sections"),
        sa.UniqueConstraint(
            "report_id",
            "section_id",
            "version",
            name="uq_report_mb_sections_report_id_section_id_version",
        ),
    )
    op.create_index(
        "ix_report_mb_sections_report_id",
        "report_mb_sections",
        ["report_id"],
    )
    op.create_index(
        "ix_report_mb_sections_report_id_section_id_version",
        "report_mb_sections",
        ["report_id", "section_id", "version"],
    )

    op.create_table(
        "report_mb_charts",
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
            ["report_mb.id"],
            name=op.f("fk_report_mb_charts_report_id_report_mb"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_report_mb_charts"),
        sa.UniqueConstraint(
            "report_id",
            "chart_id",
            "version",
            name="uq_report_mb_charts_report_id_chart_id_version",
        ),
    )
    op.create_index(
        "ix_report_mb_charts_report_id",
        "report_mb_charts",
        ["report_id"],
    )
    op.create_index(
        "ix_report_mb_charts_report_id_chart_id_version",
        "report_mb_charts",
        ["report_id", "chart_id", "version"],
    )

    op.create_table(
        "report_mb_citations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("display_index", sa.Integer(), nullable=True),
        sa.Column("provenance_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["report_mb.id"],
            name=op.f("fk_report_mb_citations_report_id_report_mb"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_report_mb_citations"),
        sa.UniqueConstraint(
            "report_id",
            "source_id",
            name="uq_report_mb_citations_report_id_source_id",
        ),
    )
    op.create_index(
        "ix_report_mb_citations_report_id",
        "report_mb_citations",
        ["report_id"],
    )

    op.create_table(
        "report_mb_tool_call_log",
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
            ["report_mb.id"],
            name=op.f("fk_report_mb_tool_call_log_report_id_report_mb"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_report_mb_tool_call_log"),
    )
    op.create_index(
        "ix_report_mb_tool_call_log_report_id_turn_index",
        "report_mb_tool_call_log",
        ["report_id", "turn_index"],
    )

    op.create_table(
        "report_mb_templates",
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
            name=op.f("fk_report_mb_templates_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_report_mb_templates"),
    )
    op.create_index(
        "ix_report_mb_templates_user_id",
        "report_mb_templates",
        ["user_id"],
    )

    op.create_table(
        "report_mb_instructions",
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
            name=op.f("fk_report_mb_instructions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_report_mb_instructions"),
    )
    op.create_index(
        "ix_report_mb_instructions_user_id",
        "report_mb_instructions",
        ["user_id"],
    )

    # --- 2. mb_schedules per-schedule config binding --------------------
    with op.batch_alter_table("mb_schedules", schema=None) as batch_op:
        batch_op.add_column(sa.Column("template_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("instructions_id", sa.String(length=36), nullable=True))
        batch_op.add_column(
            sa.Column(
                "enabled_connectors",
                JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )
        batch_op.add_column(sa.Column("provider_kind", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("model", sa.String(length=128), nullable=True))
        batch_op.add_column(
            sa.Column("language", sa.String(length=8), nullable=False, server_default="en")
        )
        batch_op.add_column(
            sa.Column("length", sa.String(length=16), nullable=False, server_default="normal")
        )
        batch_op.add_column(sa.Column("reasoning_effort", sa.String(length=16), nullable=True))
        batch_op.add_column(
            sa.Column("web_search", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    # --- 3. repo_items.mb_v2_report_id polymorphic target ---------------
    with op.batch_alter_table("repo_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("mb_v2_report_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_repo_items_mb_v2_report_id",
            "report_mb",
            ["mb_v2_report_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_unique_constraint(
            "uq_repo_items_user_mb_report", ["user_id", "mb_v2_report_id"]
        )
        batch_op.drop_constraint("ck_repo_items_exactly_one_target", type_="check")
        batch_op.create_check_constraint(
            "ck_repo_items_exactly_one_target",
            "((CASE WHEN report_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN pipeline_run_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN v3_report_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN eu_v2_report_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN mb_v2_report_id IS NOT NULL THEN 1 ELSE 0 END)) = 1",
        )

    # --- 4. seed the built-in mb_default template -----------------------
    from openlia.llm.runtime.report_mb.default_template import build_default_template

    spec = build_default_template()
    now = datetime.now(UTC)
    templates_table = sa.table(
        "report_mb_templates",
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

    # --- 5. drop the obsolete per-user config table ---------------------
    op.drop_table("mb_user_configs")


def downgrade() -> None:
    # --- 5. recreate mb_user_configs (original shape) -------------------
    op.create_table(
        "mb_user_configs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("report_length", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("enabled_section_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("section_topics", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("custom_sections", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("reference_portfolio", sa.Boolean(), nullable=False, server_default=sa.false()),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_mb_user_configs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_mb_user_configs"),
        sa.UniqueConstraint("user_id", name="uq_mb_user_configs_user_id"),
        sa.CheckConstraint(
            "report_length IN ('concise', 'normal', 'elaborative')",
            name="ck_mb_user_configs_length",
        ),
    )

    # --- 3. drop repo_items.mb_v2_report_id target ----------------------
    with op.batch_alter_table("repo_items", schema=None) as batch_op:
        batch_op.drop_constraint("ck_repo_items_exactly_one_target", type_="check")
        batch_op.drop_constraint("uq_repo_items_user_mb_report", type_="unique")
        batch_op.drop_constraint("fk_repo_items_mb_v2_report_id", type_="foreignkey")
        batch_op.drop_column("mb_v2_report_id")
        batch_op.create_check_constraint(
            "ck_repo_items_exactly_one_target",
            "((CASE WHEN report_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN pipeline_run_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN v3_report_id IS NOT NULL THEN 1 ELSE 0 END) + "
            "(CASE WHEN eu_v2_report_id IS NOT NULL THEN 1 ELSE 0 END)) = 1",
        )

    # --- 2. drop mb_schedules config-binding columns --------------------
    with op.batch_alter_table("mb_schedules", schema=None) as batch_op:
        batch_op.drop_column("web_search")
        batch_op.drop_column("reasoning_effort")
        batch_op.drop_column("length")
        batch_op.drop_column("language")
        batch_op.drop_column("model")
        batch_op.drop_column("provider_kind")
        batch_op.drop_column("enabled_connectors")
        batch_op.drop_column("instructions_id")
        batch_op.drop_column("template_id")

    # --- 1. drop the report_mb* tables ----------------------------------
    op.drop_index(
        "ix_report_mb_instructions_user_id",
        table_name="report_mb_instructions",
    )
    op.drop_table("report_mb_instructions")

    op.drop_index("ix_report_mb_templates_user_id", table_name="report_mb_templates")
    op.drop_table("report_mb_templates")

    op.drop_index(
        "ix_report_mb_tool_call_log_report_id_turn_index",
        table_name="report_mb_tool_call_log",
    )
    op.drop_table("report_mb_tool_call_log")

    op.drop_index("ix_report_mb_citations_report_id", table_name="report_mb_citations")
    op.drop_table("report_mb_citations")

    op.drop_index(
        "ix_report_mb_charts_report_id_chart_id_version",
        table_name="report_mb_charts",
    )
    op.drop_index("ix_report_mb_charts_report_id", table_name="report_mb_charts")
    op.drop_table("report_mb_charts")

    op.drop_index(
        "ix_report_mb_sections_report_id_section_id_version",
        table_name="report_mb_sections",
    )
    op.drop_index("ix_report_mb_sections_report_id", table_name="report_mb_sections")
    op.drop_table("report_mb_sections")

    op.drop_index("ix_report_mb_user_id_status", table_name="report_mb")
    op.drop_index("ix_report_mb_user_id_created_at", table_name="report_mb")
    op.drop_table("report_mb")
