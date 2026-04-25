"""Plan 1a P1-1a-01 — spec-mandated CHECK constraints (conservative slice).

Adds CHECK constraints for the columns whose value sets are tightly defined
by the spec and whose existing test suites already use only spec values:

  - users.failed_login_attempts >= 0
  - signup_policy.mode IN ('invite_only', 'closed', 'open')
  - wizard_state.status IN ('not_started', 'in_progress', 'completed')
  - llm_models.tier IN ('thinking', 'everyday', 'quick')
  - user_llm_preferences.tier IN ('thinking', 'everyday', 'quick')

Deferred (not added in this migration; flagged in master tracker for a
future per-table audit):

  - llm_providers / data_providers / web_search_providers credential XOR
    constraint (multi-column, has the ollama-no-creds carve-out).
  - chat_sessions.department, chat_messages.role,
    password_reset_requests.status, auth_events.event_type — wider value
    sets that need a careful per-implementation audit before locking the
    DB.

All operations use batch_alter_table so the migration is SQLite-safe.

Revision ID: 20260424_0300_checks
Revises: 20260424_0200_defaults
Create Date: 2026-04-24
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260424_0300_checks"
down_revision: str | Sequence[str] | None = "20260424_0200_defaults"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CHECKS: list[tuple[str, str, str]] = [
    # (table, short_name, expression). The shipped name follows the project
    # naming convention: `ck_<table>_<short_name>`.
    ("users", "failed_login_attempts_nonneg", "failed_login_attempts >= 0"),
    ("signup_policy", "mode_enum", "mode IN ('invite_only', 'closed', 'open')"),
    (
        "wizard_state",
        "status_enum",
        "status IN ('not_started', 'in_progress', 'completed')",
    ),
    ("llm_models", "tier_enum", "tier IN ('thinking', 'everyday', 'quick')"),
    (
        "user_llm_preferences",
        "tier_enum",
        "tier IN ('thinking', 'everyday', 'quick')",
    ),
]


def upgrade() -> None:
    for table, name, expression in _CHECKS:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.create_check_constraint(name, expression)


def downgrade() -> None:
    for table, name, _expression in reversed(_CHECKS):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_constraint(name, type_="check")
