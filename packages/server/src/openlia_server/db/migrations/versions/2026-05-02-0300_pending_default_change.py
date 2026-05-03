"""Resolver redesign Phase 11: pending_default_change column.

Adds a JSON column on ``runner_callable_specs`` so a catalog reinstall /
upgrade can stash the would-be-new template spec without clobbering an
existing user override. The admin panel reads the column to surface a
non-blocking "pending default change" notice; the user can revert to
the new default with a single click.

Revision ID: 20260502_0300_pending_default
Revises: 20260502_0200_audit_orphan
Create Date: 2026-05-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260502_0300_pending_default"
down_revision: str | Sequence[str] | None = "20260502_0200_audit_orphan"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("runner_callable_specs") as batch:
        batch.add_column(sa.Column("pending_default_change", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("runner_callable_specs") as batch:
        batch.drop_column("pending_default_change")
