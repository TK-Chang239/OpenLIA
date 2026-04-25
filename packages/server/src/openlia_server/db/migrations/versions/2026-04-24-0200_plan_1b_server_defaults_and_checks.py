"""Plan 1b hardening: server_defaults, DESC index.

Addresses audit items NEW-1b-02, NEW-1b-03, NEW-1b-04, NEW-1b-06:
  - is_enabled server_default=1 on mb_schedules, eu_schedules.
  - is_shipped server_default=0 on pt_presets.
  - JSON '{}' / '[]' server_defaults on PT/MR/RS config columns.
  - rs_snapshots (ticker, captured_at DESC) index replaces plain ASC index.

NEW-1b-05 (assessment_schedule enum CHECK) was retired during implementation:
the shipped scheduler stores a cron expression in that column, not the
`weekly` / `quarterly` shorthand the spec originally documented. The spec
rows in `database-design.md` §7 and `background-task-scheduling-design.md`
§Department schedule tables were amended to match the shipped reality
instead of tightening the DB with a check that would break the scheduler
service.

All operations use batch_alter_table so the migration is SQLite-safe
(which recreates the table under the hood for ALTER COLUMN).

Revision ID: 20260424_0200_defaults
Revises: 20260424_0100_rs
Create Date: 2026-04-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260424_0200_defaults"
down_revision: str | Sequence[str] | None = "20260424_0100_rs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_BOOL_COLS: list[tuple[str, str, str]] = [
    # (table, column, server_default literal)
    ("pt_presets", "is_shipped", "0"),
    ("mb_schedules", "is_enabled", "1"),
    ("eu_schedules", "is_enabled", "1"),
]

_JSON_COLS: list[tuple[str, str, str]] = [
    # (table, column, server_default literal)
    ("pt_user_configs", "panel_config", "'[]'"),
    ("pt_user_configs", "composite_settings", "'{}'"),
    ("pt_presets", "panel_config", "'[]'"),
    ("pt_presets", "composite_settings", "'{}'"),
    ("mr_dashboard_state", "view_config", "'{}'"),
    ("mr_dashboard_state", "threshold_overrides", "'{}'"),
    ("rs_user_config", "metric_settings", "'{}'"),
    ("rs_user_config", "filter_presets", "'[]'"),
]


def upgrade() -> None:
    # Boolean server_defaults.
    for table, column, default in _BOOL_COLS:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column(
                column,
                existing_type=sa.Boolean(),
                existing_nullable=False,
                server_default=sa.text(default),
            )

    # JSON server_defaults.
    for table, column, default in _JSON_COLS:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column(
                column,
                existing_type=sa.JSON(),
                existing_nullable=False,
                server_default=sa.text(default),
            )

    # rs_snapshots: replace ASC index with DESC to match spec §7.
    with op.batch_alter_table("rs_snapshots", schema=None) as batch_op:
        batch_op.drop_index("ix_rs_snapshots_ticker_captured")
        batch_op.create_index(
            "ix_rs_snapshots_ticker_captured",
            ["ticker", sa.text("captured_at DESC")],
        )


def downgrade() -> None:
    # Reverse rs_snapshots index first (FK-order not relevant here).
    with op.batch_alter_table("rs_snapshots", schema=None) as batch_op:
        batch_op.drop_index("ix_rs_snapshots_ticker_captured")
        batch_op.create_index(
            "ix_rs_snapshots_ticker_captured",
            ["ticker", "captured_at"],
        )

    for table, column, _default in _JSON_COLS:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column(
                column,
                existing_type=sa.JSON(),
                existing_nullable=False,
                server_default=None,
            )

    for table, column, _default in _BOOL_COLS:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column(
                column,
                existing_type=sa.Boolean(),
                existing_nullable=False,
                server_default=None,
            )
