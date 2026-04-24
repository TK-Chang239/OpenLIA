"""SQLAlchemy models, grouped by database-design.md category.

Each submodule below registers its models on Base.metadata. Importers
should `import openlia_server.db.models` — that loads every category so
`Base.metadata.tables` is complete.

Categories:
  auth          — §3 users, sessions, invites, policy, reset requests, events
  config        — §4 LLM + data + web-search provider config
  content       — §6 chat, reports, portfolio, watchlists
  infrastructure— §7 wizard_state, config_store
  dashboard     — §7 PT, MR, RS, FE (added in Plan 1B)
  scheduler     — §7 MB/EU schedules + job_runs + user_notifications (added in Plan 1B)
"""

from openlia_server.db.models import (
    auth,
    config,
    content,
    dashboard,
    departments,
    infrastructure,
    scheduler,
)

__all__ = [
    "auth",
    "config",
    "content",
    "dashboard",
    "departments",
    "infrastructure",
    "scheduler",
]
