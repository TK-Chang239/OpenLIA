"""Slice 6 — graph extraction proposal queue.

The extractor reads a chat session's transcript, asks an LLM (injected
via ``extract_fn`` so tests don't need a live model) for user constructs
and entity mentions it observed, and persists each result as a
``pending`` proposal. Slice 7 turns proposals into confirmed
UserConstructs / mentions; slice 8 wires the call site.
"""

from __future__ import annotations

from datetime import UTC, datetime

from openlia_server.db.models.content import ChatMessage, ChatSession
from openlia_server.services import graph_extraction


def _make_session(db_session, *, session_id: str = "s-1", user_id: str = "u-1") -> ChatSession:
    row = ChatSession(
        id=session_id,
        user_id=user_id,
        department="secretary",
        title="NVDA chat",
    )
    db_session.add(row)
    db_session.add_all(
        [
            ChatMessage(
                id=f"{session_id}-m1",
                session_id=session_id,
                role="user",
                content="I'm long NVDA on the services-margin thesis",
                created_at=datetime.now(UTC),
            ),
            ChatMessage(
                id=f"{session_id}-m2",
                session_id=session_id,
                role="assistant",
                content="Noted.",
                created_at=datetime.now(UTC),
            ),
        ]
    )
    db_session.flush()
    return row


def test_extract_persists_user_construct_proposal_as_pending(db_session) -> None:
    _make_session(db_session)

    def fake_extract(messages):
        return [
            {
                "kind": "user_construct",
                "payload": {
                    "construct_kind": "position",
                    "statement": "Long NVDA, services-margin thesis",
                    "entity_kind": "ticker",
                    "entity_value": "NVDA",
                    "source_excerpt": "I'm long NVDA on the services-margin thesis",
                },
            }
        ]

    proposals = graph_extraction.extract_proposals_from_session(
        db_session,
        session_id="s-1",
        user_id="u-1",
        extract_fn=fake_extract,
    )

    assert len(proposals) == 1
    p = proposals[0]
    assert p.kind == "user_construct"
    assert p.status == "pending"
    assert p.user_id == "u-1"
    assert p.source_kind == "session"
    assert p.source_id == "s-1"
    assert p.payload["construct_kind"] == "position"
    assert p.payload["entity_value"] == "NVDA"


def test_extract_skips_statements_with_dismissed_tombstone(db_session) -> None:
    """If the user already dismissed a proposal with this exact statement,
    the extractor must not re-propose it on the next run. Otherwise the
    review queue becomes a treadmill: dismiss it, run extraction again,
    same proposal reappears."""
    _make_session(db_session)

    seed_payload = {
        "construct_kind": "position",
        "statement": "Long NVDA, services-margin thesis",
        "entity_kind": "ticker",
        "entity_value": "NVDA",
    }
    graph_extraction.record_proposal(
        db_session,
        user_id="u-1",
        source_kind="session",
        source_id="s-1",
        kind="user_construct",
        payload=seed_payload,
        status="dismissed",
    )

    def fake_extract(messages):
        return [{"kind": "user_construct", "payload": seed_payload}]

    proposals = graph_extraction.extract_proposals_from_session(
        db_session,
        session_id="s-1",
        user_id="u-1",
        extract_fn=fake_extract,
    )

    assert proposals == []
