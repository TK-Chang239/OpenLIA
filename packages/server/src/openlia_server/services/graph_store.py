"""Cross-session memory graph — public service surface (slice 1).

Tracer-bullet API: create entity nodes, add edges between them, traverse
to neighbors. Subsequent slices add canonical ID resolution (slice 2),
edges into existing artifact tables (slice 3), UserConstruct nodes
(slice 5), and embedding-aware retrieval (slices 9-12).

All functions take an explicit ``Session`` so callers control transaction
boundaries; this module never opens its own session and never commits.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.graph import GraphEdge, GraphEntity

_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _normalize_value(kind: str, value: str) -> str:
    """Canonical form of an entity's natural key.

    * ``ticker``: uppercased, surrounding whitespace stripped. ``"nvda"`` →
      ``"NVDA"``. Tickers are case-insensitive in market data and the user
      will type either form.
    * ``sector`` / ``theme`` / ``macro_regime``: kebab-case slug. Strips
      punctuation, collapses runs of non-alphanumerics into single dashes.
      ``"AI Capex"`` → ``"ai-capex"``. Free-text labels need this so the
      same concept doesn't fork into rival nodes.
    * Other kinds: pass through trimmed. Slice 2 keeps the rule set tight;
      add new kinds here as they appear in later slices.
    """
    raw = value.strip()
    if kind == "ticker":
        return raw.upper()
    if kind in {"sector", "theme", "macro_regime"}:
        slug = _SLUG_NON_ALNUM.sub("-", raw.lower()).strip("-")
        return slug
    return raw


def _entity_pk(kind: str, value: str) -> str:
    return f"{kind}:{_normalize_value(kind, value)}"


def entity_for(
    db: Session,
    *,
    kind: str,
    value: str,
    props: dict[str, Any] | None = None,
) -> GraphEntity:
    """Idempotent canonical lookup-or-create.

    This is the public entry point callers should use anywhere they have
    an externally-supplied label (chat text, report ticker field, user
    construct's anchor entity). Two calls with equivalent inputs (case,
    whitespace, punctuation per the rules in ``_normalize_value``) return
    the same row.
    """
    return create_entity(db, kind=kind, value=value, props=props)


def create_entity(
    db: Session,
    *,
    kind: str,
    value: str,
    props: dict[str, Any] | None = None,
) -> GraphEntity:
    """Create-or-return an entity node keyed by ``(kind, value)``.

    Idempotent on the natural key: a second call with the same ``kind`` /
    ``value`` returns the existing row rather than raising. Slice 2 will
    extend this with case/alias normalization.
    """
    normalized = _normalize_value(kind, value)
    pk = f"{kind}:{normalized}"
    existing = db.get(GraphEntity, pk)
    if existing is not None:
        return existing
    row = GraphEntity(id=pk, kind=kind, value=normalized, props=props)
    db.add(row)
    db.flush()
    return row


def get_entity(db: Session, *, kind: str, value: str) -> GraphEntity | None:
    return db.get(GraphEntity, _entity_pk(kind, value))


def add_edge(
    db: Session,
    *,
    src_kind: str,
    src_id: str,
    dst_kind: str,
    dst_id: str,
    edge_type: str,
    props: dict[str, Any] | None = None,
) -> GraphEdge:
    edge = GraphEdge(
        src_kind=src_kind,
        src_id=src_id,
        dst_kind=dst_kind,
        dst_id=dst_id,
        edge_type=edge_type,
        props=props,
    )
    db.add(edge)
    db.flush()
    return edge


def mention(
    db: Session,
    *,
    entity_kind: str,
    entity_value: str,
    artifact_kind: str,
    artifact_id: str,
) -> GraphEdge:
    """Record that an artifact (report / session / snapshot) mentions an entity.

    Creates the entity node via canonical lookup (slice 2) and an
    ``entity → artifact`` ``mentions`` edge. Idempotent: a second call
    with arguments resolving to the same canonical entity returns the
    existing edge rather than inserting a duplicate. This is the contract
    the slice-4 report-finalize hook will rely on so regenerating a
    report doesn't fan out parallel edges.
    """
    entity = entity_for(db, kind=entity_kind, value=entity_value)
    stmt = select(GraphEdge).where(
        GraphEdge.src_kind == "entity",
        GraphEdge.src_id == entity.id,
        GraphEdge.dst_kind == artifact_kind,
        GraphEdge.dst_id == artifact_id,
        GraphEdge.edge_type == "mentions",
    )
    existing = db.execute(stmt).scalar_one_or_none()
    if existing is not None:
        return existing
    return add_edge(
        db,
        src_kind="entity",
        src_id=entity.id,
        dst_kind=artifact_kind,
        dst_id=artifact_id,
        edge_type="mentions",
    )


def neighbors_of(
    db: Session,
    *,
    kind: str,
    id: str,
    edge_type: str | None = None,
    direction: str = "out",
) -> list[GraphEdge]:
    """Return edges incident on the given node.

    ``direction="out"`` returns edges where the node is the source;
    ``"in"`` returns edges where the node is the destination. Optional
    ``edge_type`` filters to a single relation. Callers traverse by
    reading ``edge.dst_kind`` / ``edge.dst_id`` (or the ``src_*`` pair
    for incoming edges).
    """
    if direction == "out":
        stmt = select(GraphEdge).where(
            GraphEdge.src_kind == kind,
            GraphEdge.src_id == id,
        )
    elif direction == "in":
        stmt = select(GraphEdge).where(
            GraphEdge.dst_kind == kind,
            GraphEdge.dst_id == id,
        )
    else:
        raise ValueError(f"direction must be 'out' or 'in', got {direction!r}")
    if edge_type is not None:
        stmt = stmt.where(GraphEdge.edge_type == edge_type)
    return list(db.execute(stmt).scalars())
