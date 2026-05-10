"""Cross-session memory retrieval (slices 11, 13).

Deterministic, no-LLM entity extraction + 1-hop graph traversal that
produces the memory block injected into the Secretary system prompt.
Designed to be cheap enough to run on every chat turn.

Two extraction paths:

1. **Construct-anchored substring match (primary, slice 13)** —
   for every entity the caller has at least one ``confirmed``
   UserConstruct against, case-insensitive substring match against the
   message. Skips entities with ``value`` ≤3 chars (false-positive
   floor) and entities flagged ``is_trigger_disabled`` (user opt-out
   for over-eager matchers like an ``ai`` theme).
2. **Uppercase ticker regex (fallback, slice 11)** — preserved so the
   first-ever mention of a known ticker still resolves even when the
   user has no construct anchored to it yet.

Vector recall (slice 12) is a separate entry point and is invoked by
the model via a tool — not here on the hot path.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.graph import GraphEntity, GraphUserConstruct

_TICKER_CANDIDATE = re.compile(r"\$?[A-Z][A-Z0-9]{0,4}\b")
_MAX_CHARS = 1500
_MAX_CONSTRUCTS_PER_ENTITY = 3
_MIN_VALUE_LEN = 4  # values <= 3 chars false-positive everywhere


def extract_entity_ids(
    db: Session,
    *,
    user_id: str,
    text: str,
) -> list[str]:
    """Return canonical entity IDs (e.g. ``"ticker:NVDA"``,
    ``"theme:ai-capex"``) referenced in ``text``.

    Primary path: case-insensitive substring match against every entity
    the caller has a confirmed UserConstruct against. Secondary path:
    uppercase-ticker regex against all ticker entities for the
    no-construct case (keeps slice-11 behavior for first-ever mentions).
    Results are deduplicated and sorted.
    """
    text_lower = text.lower()
    matched: set[str] = set()

    # Primary: substring match against construct-anchored entities for
    # this user. ``distinct`` avoids returning the same entity once per
    # construct.
    anchored_stmt = (
        select(GraphEntity.id, GraphEntity.value, GraphEntity.is_trigger_disabled)
        .join(GraphUserConstruct, GraphUserConstruct.entity_id == GraphEntity.id)
        .where(
            GraphUserConstruct.user_id == user_id,
            GraphUserConstruct.status == "confirmed",
        )
        .distinct()
    )
    for entity_id, value, trigger_disabled in db.execute(anchored_stmt):
        if trigger_disabled:
            continue
        if len(value) < _MIN_VALUE_LEN:
            continue
        if value.lower() in text_lower:
            matched.add(entity_id)

    # Fallback: uppercase ticker regex. Keeps the slice-11 behavior so a
    # user's first-ever ``NVDA`` mention resolves even without an
    # anchored construct yet.
    raw_candidates: set[str] = set()
    for match in _TICKER_CANDIDATE.findall(text):
        raw_candidates.add(match.lstrip("$").upper())
    if raw_candidates:
        ticker_stmt = select(GraphEntity.id).where(
            GraphEntity.kind == "ticker",
            GraphEntity.value.in_(raw_candidates),
            GraphEntity.is_trigger_disabled.is_(False),
        )
        for entity_id in db.execute(ticker_stmt).scalars():
            matched.add(entity_id)

    return sorted(matched)


def retrieve_memory_block(
    db: Session,
    *,
    user_id: str,
    message: str,
) -> str | None:
    """Build the memory block to inject into the system prompt.

    Returns ``None`` when there's nothing to inject (no matched entity
    or no confirmed constructs for the matched entities) so callers can
    skip the section entirely rather than emit an empty header.
    """
    entity_ids = extract_entity_ids(db, user_id=user_id, text=message)
    if not entity_ids:
        return None

    lines: list[str] = []
    used = 0
    for entity_id in entity_ids:
        constructs = list(
            db.execute(
                select(GraphUserConstruct)
                .where(
                    GraphUserConstruct.user_id == user_id,
                    GraphUserConstruct.entity_id == entity_id,
                    GraphUserConstruct.status == "confirmed",
                )
                .order_by(GraphUserConstruct.updated_at.desc())
                .limit(_MAX_CONSTRUCTS_PER_ENTITY)
            ).scalars()
        )
        if not constructs:
            continue
        # Show entity value (not full id) for readability.
        _, label = entity_id.split(":", 1)
        lines.append(f"- {label}:")
        for c in constructs:
            entry = f"  - ({c.kind}) {c.statement}"
            if used + len(entry) > _MAX_CHARS:
                lines.append("  - ... (truncated)")
                break
            lines.append(entry)
            used += len(entry)
        else:
            continue
        break

    if not lines:
        return None
    header = "## Memory (your beliefs anchored to entities in this message)"
    return header + "\n" + "\n".join(lines)
