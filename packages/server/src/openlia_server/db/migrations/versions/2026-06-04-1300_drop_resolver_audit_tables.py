"""Drop resolver_call_log and smoke_call_log audit tables.

These tables were written by the interactive wizard flow
(resolver/smoke audit panels). The wizard is deleted; the tables are
orphaned. ``runner_callable_specs`` is kept — the portfolio resolution
chain depends on it.

Revision ID: drop_resolver_audit_tables
Revises: drop_legacy_rs_tables
Create Date: 2026-06-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "drop_resolver_audit_tables"
down_revision: str | Sequence[str] | None = "drop_legacy_rs_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # smoke_call_log has FK → runner_callable_specs; drop it first.
    op.drop_index("ix_smoke_call_log_spec_created", table_name="smoke_call_log")
    op.drop_table("smoke_call_log")

    op.drop_index("ix_resolver_call_log_spec_created", table_name="resolver_call_log")
    op.drop_table("resolver_call_log")


def downgrade() -> None:
    # Recreate resolver_call_log with the schema from 20260502_0200_audit_orphan
    # (spec_id nullable, ON DELETE SET NULL).
    op.create_table(
        "resolver_call_log",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "spec_id",
            sa.String(length=36),
            sa.ForeignKey(
                "runner_callable_specs.id",
                ondelete="SET NULL",
                name="fk_resolver_call_log_spec_id",
            ),
            nullable=True,
        ),
        sa.Column("department_id", sa.String(length=64), nullable=False),
        sa.Column("need_id", sa.String(length=64), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("response", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_class", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('success', 'invalid_output', 'llm_error', 'timeout')",
            name="resolver_call_log_status",
        ),
    )
    op.create_index(
        "ix_resolver_call_log_spec_created",
        "resolver_call_log",
        ["spec_id", "created_at"],
    )

    # Recreate smoke_call_log with the schema from 20260502_0200_audit_orphan
    # (spec_id nullable, ON DELETE SET NULL).
    op.create_table(
        "smoke_call_log",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "spec_id",
            sa.String(length=36),
            sa.ForeignKey(
                "runner_callable_specs.id",
                ondelete="SET NULL",
                name="fk_smoke_call_log_spec_id",
            ),
            nullable=True,
        ),
        sa.Column("args", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "attempt",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("error_class", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("response_excerpt", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('success', 'auth', 'schema_miss', 'empty', 'bad_params', 'transient')",
            name="smoke_call_log_status",
        ),
    )
    op.create_index(
        "ix_smoke_call_log_spec_created",
        "smoke_call_log",
        ["spec_id", "created_at"],
    )
