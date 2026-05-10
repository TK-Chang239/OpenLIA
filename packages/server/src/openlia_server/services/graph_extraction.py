"""LLM-driven graph extraction (slice 6).

Reads a chat session's transcript, asks an LLM-shaped ``extract_fn``
what user constructs and entity mentions it observed, and persists each
result as a ``pending`` proposal in ``graph_extraction_proposals``.

The LLM is injected as a callable so this module stays unit-testable
without a live model and so the production wiring (slice 8) can pick
the model from user prefs / config without coupling extraction logic
to the runtime layer.

A statement that previously surfaced as a ``dismissed`` proposal is
silently skipped — otherwise the review queue becomes a treadmill.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.content import ChatMessage, ChatSession
from openlia_server.db.models.graph import (
    GraphExtractionProposal,
    GraphUserConstruct,
)

ExtractFn = Callable[[list[ChatMessage]], list[dict[str, Any]]]

_VALID_KINDS: frozenset[str] = frozenset({"user_construct", "mention"})
_VALID_STATUSES: frozenset[str] = frozenset({"pending", "accepted", "dismissed"})


def extract_proposals_from_session(
    db: Session,
    *,
    session_id: str,
    user_id: str,
    extract_fn: ExtractFn,
) -> list[GraphExtractionProposal]:
    """Run extraction over a session and persist new proposals.

    Returns the proposals actually inserted (skipping tombstoned
    duplicates). The session is read fresh from the DB so callers can
    invoke this from a background job that has only the session ID.
    """
    session = db.get(ChatSession, session_id)
    if session is None or session.user_id != user_id:
        return []

    messages = list(
        db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at)
        ).scalars()
    )

    candidates = extract_fn(messages)
    inserted: list[GraphExtractionProposal] = []
    for spec in candidates:
        kind = spec.get("kind")
        payload = spec.get("payload", {})
        if kind not in _VALID_KINDS:
            continue
        h = _statement_hash(payload)
        if _has_tombstone(db, user_id=user_id, statement_hash=h):
            continue
        row = record_proposal(
            db,
            user_id=user_id,
            source_kind="session",
            source_id=session_id,
            kind=kind,
            payload=payload,
        )
        inserted.append(row)
    return inserted


def record_proposal(
    db: Session,
    *,
    user_id: str,
    source_kind: str,
    source_id: str,
    kind: str,
    payload: dict[str, Any],
    status: str = "pending",
) -> GraphExtractionProposal:
    """Insert a proposal directly. Used by the extractor and by tests
    seeding tombstones.
    """
    if kind not in _VALID_KINDS:
        raise ValueError(f"unknown proposal kind: {kind!r}")
    if status not in _VALID_STATUSES:
        raise ValueError(f"unknown proposal status: {status!r}")
    row = GraphExtractionProposal(
        id=str(uuid.uuid4()),
        user_id=user_id,
        source_kind=source_kind,
        source_id=source_id,
        kind=kind,
        payload=dict(payload),
        statement_hash=_statement_hash(payload),
        status=status,
    )
    db.add(row)
    db.flush()
    return row


def accept_proposal(
    db: Session,
    *,
    proposal_id: str,
    user_id: str,
) -> GraphUserConstruct | None:
    """Materialize a pending proposal into the graph.

    For ``user_construct`` proposals: creates a ``confirmed`` construct
    (with ``about`` edge) and returns the row. For ``mention`` proposals:
    emits the ``entity → artifact`` ``mentions`` edge and returns
    ``None`` (mentions are edges, not nodes). The proposal's status flips
    to ``accepted`` either way.

    Returns ``None`` (without side effects) when the proposal doesn't
    belong to ``user_id`` or is already resolved — defensive against
    cross-tenant access through a guessed ID.
    """
    from openlia_server.services import graph_store, user_constructs

    p = db.get(GraphExtractionProposal, proposal_id)
    if p is None or p.user_id != user_id or p.status != "pending":
        return None

    if p.kind == "user_construct":
        construct = user_constructs.create_construct(
            db,
            user_id=user_id,
            kind=p.payload["construct_kind"],
            statement=p.payload["statement"],
            entity_kind=p.payload["entity_kind"],
            entity_value=p.payload["entity_value"],
            status="confirmed",
            provenance={
                "proposal_id": p.id,
                "source_kind": p.source_kind,
                "source_id": p.source_id,
                "source_excerpt": p.payload.get("source_excerpt"),
            },
        )
        p.status = "accepted"
        db.flush()
        return construct

    if p.kind == "mention":
        graph_store.mention(
            db,
            entity_kind=p.payload["entity_kind"],
            entity_value=p.payload["entity_value"],
            artifact_kind=p.payload["artifact_kind"],
            artifact_id=p.payload["artifact_id"],
        )
        p.status = "accepted"
        db.flush()
        return None

    return None


def dismiss_proposal(
    db: Session,
    *,
    proposal_id: str,
    user_id: str,
) -> None:
    """Mark a proposal dismissed. Acts as a tombstone for future
    extractions (see ``_has_tombstone``)."""
    p = db.get(GraphExtractionProposal, proposal_id)
    if p is None or p.user_id != user_id or p.status != "pending":
        return
    p.status = "dismissed"
    db.flush()


def _statement_hash(payload: dict[str, Any]) -> str:
    """Stable dedup key. For user_construct we hash the canonical
    statement plus the anchor entity so the same belief about different
    tickers stays distinct. For mentions we hash the (entity, artifact)
    pair.
    """
    if "statement" in payload:
        material = (
            f"{payload.get('construct_kind', '')}|"
            f"{payload.get('entity_kind', '')}|"
            f"{payload.get('entity_value', '').strip().lower()}|"
            f"{payload['statement'].strip().lower()}"
        )
    else:
        material = (
            f"mention|"
            f"{payload.get('entity_kind', '')}|"
            f"{payload.get('entity_value', '').strip().lower()}|"
            f"{payload.get('artifact_kind', '')}|"
            f"{payload.get('artifact_id', '')}"
        )
    return hashlib.sha256(material.encode()).hexdigest()


def _has_tombstone(db: Session, *, user_id: str, statement_hash: str) -> bool:
    stmt = select(GraphExtractionProposal.id).where(
        GraphExtractionProposal.user_id == user_id,
        GraphExtractionProposal.statement_hash == statement_hash,
        GraphExtractionProposal.status == "dismissed",
    )
    return db.execute(stmt).first() is not None
