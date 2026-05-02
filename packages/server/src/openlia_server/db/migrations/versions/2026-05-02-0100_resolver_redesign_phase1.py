"""Resolver redesign Phase 1: new spec columns + audit tables.

Adds the manual-pick redesign storage to ``runner_callable_specs``:
``resolution_mode``, ``user_inputs``, ``llm_warning``, ``manually_overridden``,
``last_smoke_at``. Creates ``resolver_call_log`` and ``smoke_call_log``
audit tables with ``(spec_id, created_at)`` indexes for the admin panel
history view.

See docs/superpowers/specsv2/2026-05-02-resolver-redesign-manual-pick.md §10.

Revision ID: 20260502_0100_rrd_p1
Revises: 20260501_0100_grounding_paths
Create Date: 2026-05-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260502_0100_rrd_p1"
down_revision: str | Sequence[str] | None = "20260501_0100_grounding_paths"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("runner_callable_specs") as batch:
        batch.add_column(
            sa.Column(
                "resolution_mode",
                sa.String(length=16),
                nullable=False,
                server_default="catalog",
            )
        )
        batch.add_column(sa.Column("user_inputs", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("llm_warning", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column(
                "manually_overridden",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch.add_column(sa.Column("last_smoke_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_check_constraint(
            "resolution_mode",
            "resolution_mode IN ('catalog', 'manual_endpoint', 'websearch')",
        )

    op.create_table(
        "resolver_call_log",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "spec_id",
            sa.String(length=36),
            sa.ForeignKey("runner_callable_specs.id", ondelete="CASCADE"),
            nullable=False,
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

    op.create_table(
        "smoke_call_log",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "spec_id",
            sa.String(length=36),
            sa.ForeignKey("runner_callable_specs.id", ondelete="CASCADE"),
            nullable=False,
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


def downgrade() -> None:
    op.drop_index("ix_smoke_call_log_spec_created", table_name="smoke_call_log")
    op.drop_table("smoke_call_log")
    op.drop_index("ix_resolver_call_log_spec_created", table_name="resolver_call_log")
    op.drop_table("resolver_call_log")

    with op.batch_alter_table("runner_callable_specs") as batch:
        batch.drop_constraint("resolution_mode", type_="check")
        batch.drop_column("last_smoke_at")
        batch.drop_column("manually_overridden")
        batch.drop_column("llm_warning")
        batch.drop_column("user_inputs")
        batch.drop_column("resolution_mode")
