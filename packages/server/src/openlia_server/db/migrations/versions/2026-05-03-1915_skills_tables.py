"""Skills tables: skills, skill_user_overrides; extend lia_guardrail_events for skill events.

Adds the `skills` and `skill_user_overrides` tables for the user-installable skills system.
Extends `lia_guardrail_events`: drops the narrow event_type CHECK and replaces it with one
that includes skill lifecycle events; relaxes five previously NOT NULL columns to nullable;
adds `payload_json` for structured skill event metadata.

Revision ID: 9b6c0eb8b946
Revises: 20260503_0100_lia_guardrails
Create Date: 2026-05-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9b6c0eb8b946"
down_revision: str | Sequence[str] | None = "20260503_0100_lia_guardrails"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "skill_user_overrides",
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("skill_id", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "skill_id", name=op.f("pk_skill_user_overrides")),
    )

    op.create_table(
        "skills",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("skill_id", sa.String(length=64), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("frontmatter", sa.JSON(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "installed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=256), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.CheckConstraint("scope IN ('system', 'user')", name=op.f("ck_skills_ck_skills_scope")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_skills")),
    )
    with op.batch_alter_table("skills", schema=None) as batch_op:
        batch_op.create_index("idx_skills_scope_skill_id", ["scope", "skill_id"], unique=False)
        batch_op.create_index("idx_skills_user_id", ["user_id"], unique=False)

    # Extend lia_guardrail_events: relax nullability, add payload_json, and
    # replace the narrow event_type CHECK with one that includes skill events.
    # SQLite cannot drop/recreate constraints in-place — batch_alter_table is required.
    with op.batch_alter_table("lia_guardrail_events", schema=None) as batch_op:
        batch_op.add_column(sa.Column("payload_json", sa.JSON(), nullable=True))
        batch_op.alter_column(
            "session_id", existing_type=sa.VARCHAR(length=128), nullable=True
        )
        batch_op.alter_column(
            "department_id", existing_type=sa.VARCHAR(length=64), nullable=True
        )
        batch_op.alter_column(
            "category", existing_type=sa.VARCHAR(length=64), nullable=True
        )
        batch_op.alter_column(
            "user_input_hash", existing_type=sa.VARCHAR(length=64), nullable=True
        )
        batch_op.alter_column(
            "response_excerpt", existing_type=sa.TEXT(), nullable=True
        )
        batch_op.drop_constraint(
            "ck_lia_guardrail_events_event_type", type_="check"
        )
        batch_op.create_check_constraint(
            "ck_lia_guardrail_events_event_type",
            "event_type IN ('persona_refusal', 'tripwire_flag', 'skill_installed', "
            "'skill_uninstalled', 'skill_enabled', 'skill_disabled', 'skill_loaded')",
        )


def downgrade() -> None:
    # Restore lia_guardrail_events to its original shape.
    with op.batch_alter_table("lia_guardrail_events", schema=None) as batch_op:
        batch_op.drop_constraint(
            "ck_lia_guardrail_events_event_type", type_="check"
        )
        batch_op.create_check_constraint(
            "ck_lia_guardrail_events_event_type",
            "event_type IN ('persona_refusal', 'tripwire_flag')",
        )
        batch_op.alter_column(
            "response_excerpt", existing_type=sa.TEXT(), nullable=False
        )
        batch_op.alter_column(
            "user_input_hash", existing_type=sa.VARCHAR(length=64), nullable=False
        )
        batch_op.alter_column(
            "category", existing_type=sa.VARCHAR(length=64), nullable=False
        )
        batch_op.alter_column(
            "department_id", existing_type=sa.VARCHAR(length=64), nullable=False
        )
        batch_op.alter_column(
            "session_id", existing_type=sa.VARCHAR(length=128), nullable=False
        )
        batch_op.drop_column("payload_json")

    with op.batch_alter_table("skills", schema=None) as batch_op:
        batch_op.drop_index("idx_skills_user_id")
        batch_op.drop_index("idx_skills_scope_skill_id")

    op.drop_table("skills")
    op.drop_table("skill_user_overrides")
