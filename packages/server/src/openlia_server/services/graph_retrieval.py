"""Cross-session memory retrieval (slice 11).

Deterministic, no-LLM entity extraction + 1-hop graph traversal that
produces the memory block injected into the Secretary system prompt
(slice 13). Designed to be cheap enough to run on every chat turn:

1. Tokenize the user's message; collect uppercase 1-5 letter candidates.
2. Filter against ``graph_entities`` so unknown tokens (``FYI``,
   ``TODO``) don't trigger empty traversals.
3. Pull every confirmed ``UserConstruct`` whose ``entity_id`` matches.
4. Render under a token-rough character budget so the system prompt
   doesn't balloon when a user has hundreds of beliefs about one ticker.

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


def extract_entity_ids(
    db: Session,
    *,
    user_id: str,
    text: str,
) -> list[str]:
    """Return canonical entity IDs (e.g. ``"ticker:NVDA"``) referenced
    in ``text``. Filters against the graph so unknown uppercase tokens
    don't trigger downstream traversals.

    ``user_id`` is reserved for future filtering (e.g. private themes
    shouldn't trigger from other users' chat); today it's accepted but
    not used since entities are global.
    """
    _ = user_id
    raw_candidates: set[str] = set()
    for match in _TICKER_CANDIDATE.findall(text):
        raw_candidates.add(match.lstrip("$").upper())
    if not raw_candidates:
        return []

    stmt = select(GraphEntity.id).where(
        GraphEntity.kind == "ticker",
        GraphEntity.value.in_(raw_candidates),
    )
    return sorted(db.execute(stmt).scalars())


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
