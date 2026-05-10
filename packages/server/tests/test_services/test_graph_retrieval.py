"""Slice 11 — entity-trigger retrieval.

Builds the memory block that gets auto-injected into the Secretary
system prompt (slice 13). Inputs: the user's live chat message + their
user_id. Output: a short, token-budgeted string describing every
confirmed UserConstruct anchored to an entity the user mentioned.

The entity extractor is deterministic and on-the-hot-path (no LLM call)
so chat latency doesn't grow with every turn.
"""

from __future__ import annotations

from openlia_server.services import graph_retrieval, user_constructs


def test_retrieve_memory_returns_construct_for_mentioned_ticker(db_session) -> None:
    user_constructs.create_construct(
        db_session,
        user_id="u-1",
        kind="position",
        statement="Long NVDA on services-margin thesis since Q3 2025",
        entity_kind="ticker",
        entity_value="NVDA",
    )

    block = graph_retrieval.retrieve_memory_block(
        db_session,
        user_id="u-1",
        message="What's the latest on NVDA earnings?",
    )

    assert block is not None
    assert "NVDA" in block
    assert "services-margin" in block
    # Block carries an explicit label so the model knows what it's looking at.
    assert "Memory" in block or "memory" in block


def test_retrieve_memory_returns_none_when_no_entity_mentioned(db_session) -> None:
    """No entity in the message means no retrieval — saves tokens on
    every turn that doesn't need memory."""
    user_constructs.create_construct(
        db_session,
        user_id="u-1",
        kind="position",
        statement="Long NVDA",
        entity_kind="ticker",
        entity_value="NVDA",
    )

    block = graph_retrieval.retrieve_memory_block(
        db_session,
        user_id="u-1",
        message="What's the time in Tokyo?",
    )

    assert block is None


def test_retrieve_memory_skips_other_users_constructs(db_session) -> None:
    """Bob's belief about NVDA must not leak into Alice's prompt."""
    user_constructs.create_construct(
        db_session,
        user_id="u-2",
        kind="thesis",
        statement="bob's private take on NVDA",
        entity_kind="ticker",
        entity_value="NVDA",
    )

    block = graph_retrieval.retrieve_memory_block(
        db_session,
        user_id="u-1",
        message="Tell me about NVDA",
    )

    assert block is None


def test_retrieve_memory_skips_unconfirmed_constructs(db_session) -> None:
    """Proposed (LLM-extracted, not yet user-accepted) constructs must
    stay out of the prompt or the user's memory ends up shaped by
    things they never approved."""
    user_constructs.create_construct(
        db_session,
        user_id="u-1",
        kind="thesis",
        statement="proposed but not confirmed",
        entity_kind="ticker",
        entity_value="NVDA",
        status="proposed",
    )

    block = graph_retrieval.retrieve_memory_block(
        db_session,
        user_id="u-1",
        message="What's new on NVDA?",
    )

    assert block is None


def test_extract_entities_finds_known_tickers_only(db_session) -> None:
    """Uppercase tokens are common in chat ("FYI", "TODO"). The
    extractor must only return tokens that already exist as ticker
    entities in the graph, otherwise we'd 1-hop traverse from nothing
    on every turn."""
    user_constructs.create_construct(
        db_session,
        user_id="u-1",
        kind="position",
        statement="seed entity",
        entity_kind="ticker",
        entity_value="NVDA",
    )

    found = graph_retrieval.extract_entity_ids(
        db_session,
        user_id="u-1",
        text="FYI watching NVDA and TODO check AMD",
    )

    # Only NVDA exists as a graph entity for this user; AMD isn't seeded.
    assert found == ["ticker:NVDA"]
