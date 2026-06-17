"""Drop dead mr_dashboard_state config columns: view_config, threshold_overrides

Both columns were write-only: the report_dash_mr engine never read them
(run_to_cache -> build_run_request never touches them) and the UI no longer
edits them. The table itself stays — assessment_schedule (the per-user cron)
remains load-bearing for the scheduler.

Revision ID: drop_mr_dash_config_cols
Revises: drop_resolver_audit_tables
Create Date: 2026-06-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "drop_mr_dash_config_cols"
down_revision: str = "drop_resolver_audit_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("mr_dashboard_state", schema=None) as batch_op:
        batch_op.drop_column("threshold_overrides")
        batch_op.drop_column("view_config")


def downgrade() -> None:
    with op.batch_alter_table("mr_dashboard_state", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "view_config",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "threshold_overrides",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )
