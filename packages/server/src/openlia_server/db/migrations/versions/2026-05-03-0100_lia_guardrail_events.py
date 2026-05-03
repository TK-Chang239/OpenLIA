"""Lia Safety & Compliance Guardrails: lia_guardrail_events + user_disclaimer_acceptance.

Components E (audit log) and C (compliance disclaimer) — see
docs/superpowers/specs/2026-05-02-lia-safety-and-compliance-guardrails-design.md.

Revision ID: 20260503_0100_lia_guardrails
Revises: 20260502_0300_pending_default
Create Date: 2026-05-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260503_0100_lia_guardrails"
down_revision: str | Sequence[str] | None = "20260502_0300_pending_default"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lia_guardrail_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("department_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("action_taken", sa.String(length=16), nullable=False),
        sa.Column("user_input_hash", sa.String(length=64), nullable=False),
        sa.Column("response_excerpt", sa.Text(), nullable=False),
        sa.Column("tripwire_pattern", sa.Text(), nullable=True),
        sa.Column("model_ref", sa.String(length=128), nullable=True),
        sa.CheckConstraint(
            "event_type IN ('persona_refusal', 'tripwire_flag')",
            name="ck_lia_guardrail_events_event_type",
        ),
        sa.CheckConstraint(
            "action_taken IN ('replaced', 'warned', 'logged')",
            name="ck_lia_guardrail_events_action_taken",
        ),
    )
    op.create_index(
        "idx_lia_guardrail_events_created_at",
        "lia_guardrail_events",
        [sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_lia_guardrail_events_category",
        "lia_guardrail_events",
        ["category"],
    )
    op.create_index(
        "idx_lia_guardrail_events_session",
        "lia_guardrail_events",
        ["session_id"],
    )

    op.create_table(
        "user_disclaimer_acceptance",
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("disclaimer_version", sa.String(length=32), nullable=False),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("user_id", "disclaimer_version"),
    )


def downgrade() -> None:
    op.drop_table("user_disclaimer_acceptance")
    op.drop_index("idx_lia_guardrail_events_session", table_name="lia_guardrail_events")
    op.drop_index("idx_lia_guardrail_events_category", table_name="lia_guardrail_events")
    op.drop_index("idx_lia_guardrail_events_created_at", table_name="lia_guardrail_events")
    op.drop_table("lia_guardrail_events")
