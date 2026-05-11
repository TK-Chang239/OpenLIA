"""Slice 13 — add ``is_trigger_disabled`` to ``graph_entities``.

Per-entity opt-out for the substring-match trigger introduced in
slice 13. Lets the user silence over-eager matchers (e.g. an ``ai``
theme that hits every chat) without deleting the entity or its
anchored constructs.

Revision ID: 20260510_2400_entity_trigger_flag
Revises: 20260510_2330_user_timezone
Create Date: 2026-05-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260510_2400_entity_trigger_flag"
down_revision: str | Sequence[str] | None = "20260510_2330_user_timezone"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("graph_entities") as batch:
        batch.add_column(
            sa.Column(
                "is_trigger_disabled",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("graph_entities") as batch:
        batch.drop_column("is_trigger_disabled")
