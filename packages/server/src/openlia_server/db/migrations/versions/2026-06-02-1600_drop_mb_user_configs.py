"""drop mb_user_configs

Removes the obsolete per-user ``mb_user_configs`` table. The v2 Morning
Briefing engine binds all run configuration per-schedule (``mb_schedules``
plus the ``report_mb_templates`` / ``report_mb_instructions`` profiles),
so the legacy single-row-per-user config table and its ``MbUserConfig``
ORM model are removed together. This drop is deliberately split from the
``morning_briefing_v2`` migration (Phase 6) so it lands atomically with
the deletion of the ORM model and the legacy MB service stack, keeping
``Base.metadata`` and the alembic head in sync.

``downgrade`` recreates the table with its original shape (copied from the
``20260423_2100_mb`` migration) for a clean round-trip.

Revision ID: drop_mb_user_configs
Revises: morning_briefing_v2
Create Date: 2026-06-02 16:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "drop_mb_user_configs"
down_revision: str | Sequence[str] | None = "morning_briefing_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("mb_user_configs")


def downgrade() -> None:
    op.create_table(
        "mb_user_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "report_length",
            sa.String(16),
            nullable=False,
            server_default="normal",
        ),
        sa.Column(
            "enabled_section_ids",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "section_topics",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "custom_sections",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "reference_portfolio",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
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
        sa.CheckConstraint(
            "report_length IN ('concise', 'normal', 'elaborative')",
            name="ck_mb_user_configs_length",
        ),
    )
