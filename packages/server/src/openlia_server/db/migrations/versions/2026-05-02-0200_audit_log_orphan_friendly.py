"""Resolver redesign Phase 10: make audit log spec_id nullable + non-cascading.

The save flow must persist a SmokeCallLog row even when smoke fails and
no live RunnerCallableSpec is created. Phase 1 wired the audit tables'
``spec_id`` as ``NOT NULL`` with ``ON DELETE CASCADE``, which forced
either a placeholder spec row (which would survive after a smoke
failure) or cascade-deletes the audit history. Both are wrong: we want
durable logs that can outlive the spec row.

This migration relaxes ``spec_id`` to nullable and changes the FK
ON DELETE behavior to ``SET NULL`` so deleting a spec preserves its
audit trail.

Revision ID: 20260502_0200_audit_orphan
Revises: 20260502_0100_rrd_p1
Create Date: 2026-05-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260502_0200_audit_orphan"
down_revision: str | Sequence[str] | None = "20260502_0100_rrd_p1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("resolver_call_log") as batch:
        batch.alter_column("spec_id", existing_type=sa.String(length=36), nullable=True)
        batch.drop_constraint("fk_resolver_call_log_spec_id", type_="foreignkey")
        batch.create_foreign_key(
            "fk_resolver_call_log_spec_id",
            "runner_callable_specs",
            ["spec_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("smoke_call_log") as batch:
        batch.alter_column("spec_id", existing_type=sa.String(length=36), nullable=True)
        batch.drop_constraint("fk_smoke_call_log_spec_id", type_="foreignkey")
        batch.create_foreign_key(
            "fk_smoke_call_log_spec_id",
            "runner_callable_specs",
            ["spec_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("smoke_call_log") as batch:
        batch.drop_constraint("fk_smoke_call_log_spec_id", type_="foreignkey")
        batch.create_foreign_key(
            "fk_smoke_call_log_spec_id",
            "runner_callable_specs",
            ["spec_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.alter_column("spec_id", existing_type=sa.String(length=36), nullable=False)

    with op.batch_alter_table("resolver_call_log") as batch:
        batch.drop_constraint("fk_resolver_call_log_spec_id", type_="foreignkey")
        batch.create_foreign_key(
            "fk_resolver_call_log_spec_id",
            "runner_callable_specs",
            ["spec_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch.alter_column("spec_id", existing_type=sa.String(length=36), nullable=False)
