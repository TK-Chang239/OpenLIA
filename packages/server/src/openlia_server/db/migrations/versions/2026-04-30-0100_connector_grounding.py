"""Add grounding fields to connectors.

Per docs/superpowers/plans/2026-04-30-adapter-resolver-grounding.md §1.
User-supplied URLs (GitHub repo + revision, OpenAPI spec) feed the
agentic adapter resolver. OpenLIA shallow-clones repos locally and
caches the OpenAPI spec; status + timestamp track grounding freshness.

Revision ID: 20260430_0100_grounding
Revises: 20260428_0400_plain
Create Date: 2026-04-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260430_0100_grounding"
down_revision: str | Sequence[str] | None = "20260428_0400_plain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("connectors") as batch:
        batch.add_column(sa.Column("source_repo_url", sa.String(512), nullable=True))
        batch.add_column(sa.Column("source_repo_revision", sa.String(128), nullable=True))
        batch.add_column(sa.Column("openapi_url", sa.String(512), nullable=True))
        batch.add_column(sa.Column("cached_repo_commit_sha", sa.String(40), nullable=True))
        batch.add_column(sa.Column("cached_openapi", sa.JSON(), nullable=True))
        batch.add_column(
            sa.Column(
                "grounding_status",
                sa.String(16),
                nullable=False,
                server_default="none",
            )
        )
        batch.add_column(
            sa.Column("grounding_fetched_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.create_check_constraint(
            "grounding_status",
            "grounding_status IN ('none', 'pending', 'ready', 'failed')",
        )


def downgrade() -> None:
    with op.batch_alter_table("connectors") as batch:
        batch.drop_constraint("grounding_status", type_="check")
        batch.drop_column("grounding_fetched_at")
        batch.drop_column("grounding_status")
        batch.drop_column("cached_openapi")
        batch.drop_column("cached_repo_commit_sha")
        batch.drop_column("openapi_url")
        batch.drop_column("source_repo_revision")
        batch.drop_column("source_repo_url")
