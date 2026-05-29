"""Plan 1a ORM surface — auth, config, content, infrastructure.

This package's public `__all__` is intentionally the Plan 1a set only. Modules
owned by later plans (Plan 1b dashboard/scheduler, Plans 11/14/15/16
department tables, the Plan 12 repo_items model) live as sibling submodules
and register themselves on `Base.metadata` when imported, but they are NOT
re-exported here — each plan owns its own surface.

To register every shipped model for `Base.metadata.create_all` or Alembic
autogenerate, import the side-effect shim:

    import openlia_server.db.models.register_all  # noqa: F401

`env.py` and the test-suite conftest do exactly that. See
`planning/specs/systems/database-design.md` §7 and Plan 1a Task 8 Step 3.

Categories re-exported here:
  auth          — §3 users, sessions, invites, policy, reset requests, events
  config        — §4 LLM + data + web-search provider config
  content       — §6 chat, reports, portfolio, watchlists
  infrastructure— §7 wizard_state, config_store
"""

from openlia_server.db.models import (
    auth,
    config,
    content,
    infrastructure,
    report_eu,
)
from openlia_server.db.models.report_eu import (
    EuV2EarningsSchedule,
    EuV2Settings,
    EuV2WatchlistEntry,
    ReportEu,
    ReportEuChart,
    ReportEuCitation,
    ReportEuSection,
    ReportEuTemplate,
    ReportEuToolCallLog,
)

__all__ = [
    "EuV2EarningsSchedule",
    "EuV2Settings",
    "EuV2WatchlistEntry",
    "ReportEu",
    "ReportEuChart",
    "ReportEuCitation",
    "ReportEuSection",
    "ReportEuTemplate",
    "ReportEuToolCallLog",
    "auth",
    "config",
    "content",
    "infrastructure",
    "report_eu",
]
