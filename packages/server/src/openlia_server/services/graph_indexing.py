"""Deterministic graph indexing of structured artifacts (slice 4).

The cross-session memory graph fills two ways: deterministically (this
module — for artifacts whose entities are already structured fields), and
async via LLM extraction (slices 6-8 — for free-form chat text).

Today's deterministic surface is a single hook: when a report is
finalized, its ``subject`` field gets translated into an
``entity → report`` ``mentions`` edge. The hook is idempotent and safe to
re-run on regenerate (slice 3's ``mention()`` enforces edge-level
idempotency on top of slice 2's canonical entity lookup).

Future structured artifacts (dashboard snapshots, briefing docs) can
register their own indexers here without touching the graph store.
"""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from openlia_server.db.models.content import Report
from openlia_server.services import graph_store

# Equity-research stock reports use the ticker as ``subject``. Pattern is
# 1-5 letters with optional ``.`` or ``-`` suffix (e.g. ``BRK.B``,
# ``RDS-A``). Anything that doesn't match is treated as a free-form
# theme/sector label by ``entity_for``'s slug normalization.
_TICKER_PATTERN = re.compile(r"^[A-Za-z]{1,5}(?:[.\-][A-Za-z0-9]{1,3})?$")

# Departments whose ``subject`` field is a ticker by convention. Any
# other department's subject (when present) is treated as a theme.
_TICKER_SUBJECT_DEPARTMENTS = frozenset(
    {
        "equity_research",
        "earnings_update",
    }
)


def index_report(db: Session, report: Report) -> None:
    """Emit graph edges derived from a report's structured fields.

    No-op for reports without a usable ``subject`` (e.g. macro batches).
    Idempotent: safe to call from multiple write seams or on regenerate.
    """
    subject = (report.subject or "").strip()
    if not subject:
        return

    if report.department in _TICKER_SUBJECT_DEPARTMENTS and _TICKER_PATTERN.match(subject):
        graph_store.mention(
            db,
            entity_kind="ticker",
            entity_value=subject,
            artifact_kind="report",
            artifact_id=report.id,
        )
        return

    graph_store.mention(
        db,
        entity_kind="theme",
        entity_value=subject,
        artifact_kind="report",
        artifact_id=report.id,
    )
