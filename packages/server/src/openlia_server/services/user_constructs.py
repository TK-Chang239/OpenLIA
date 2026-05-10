"""User-construct service surface (slice 5).

UserConstructs are positions, theses, concerns, and watchlist items the
user has stated. Each construct is anchored to an entity (canonical
``"kind:value"`` ID) and is reachable from that entity via an
``about`` edge so slice-11 retrieval can find it with a single 1-hop
graph query — not a column scan.

Status lifecycle:
* ``proposed``: produced by slice-6 LLM extraction, awaiting review.
* ``confirmed``: visible to retrieval. Direct creates default here.
* ``rejected``: tombstone so the same statement isn't re-proposed.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.graph import GraphUserConstruct
from openlia_server.services import graph_store

_VALID_KINDS: frozenset[str] = frozenset({"position", "thesis", "concern", "watchlist_item"})
_VALID_STATUSES: frozenset[str] = frozenset({"proposed", "confirmed", "rejected"})


def create_construct(
    db: Session,
    *,
    user_id: str,
    kind: str,
    statement: str,
    entity_kind: str,
    entity_value: str,
    status: str = "confirmed",
    provenance: dict[str, Any] | None = None,
) -> GraphUserConstruct:
    """Create a UserConstruct anchored to a canonical entity.

    The entity is resolved (or created) via ``graph_store.entity_for`` so
    callers don't need to think about case/alias normalization. An
    ``about`` edge is added in the same transaction so the construct is
    reachable from a graph traversal of the entity.
    """
    if kind not in _VALID_KINDS:
        raise ValueError(f"unknown construct kind: {kind!r}")
    if status not in _VALID_STATUSES:
        raise ValueError(f"unknown construct status: {status!r}")

    entity = graph_store.entity_for(db, kind=entity_kind, value=entity_value)
    construct_id = str(uuid.uuid4())
    row = GraphUserConstruct(
        id=construct_id,
        user_id=user_id,
        kind=kind,
        status=status,
        statement=statement,
        entity_id=entity.id,
        provenance=provenance,
    )
    db.add(row)
    db.flush()

    graph_store.add_edge(
        db,
        src_kind="construct",
        src_id=construct_id,
        dst_kind="entity",
        dst_id=entity.id,
        edge_type="about",
    )
    return row


def list_constructs(
    db: Session,
    *,
    user_id: str,
    status: str | None = None,
    entity_id: str | None = None,
) -> list[GraphUserConstruct]:
    stmt = select(GraphUserConstruct).where(GraphUserConstruct.user_id == user_id)
    if status is not None:
        stmt = stmt.where(GraphUserConstruct.status == status)
    if entity_id is not None:
        stmt = stmt.where(GraphUserConstruct.entity_id == entity_id)
    return list(db.execute(stmt).scalars())
