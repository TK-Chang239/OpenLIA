"""Slice 11 — entity-trigger retrieval.

Builds the memory block that gets auto-injected into the Secretary
system prompt (slice 13). Inputs: the user's live chat message + their
user_id. Output: a short, token-budgeted string describing every
confirmed UserConstruct anchored to an entity the user mentioned.

The entity extractor is deterministic and on-the-hot-path (no LLM call)
so chat latency doesn't grow with every turn.
"""

from __future__ import annotations

from openlia_server.db.models.graph import GraphEntity
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


def test_extract_entities_matches_lowercase_theme_via_construct(db_session) -> None:
    """Themes like ``ai-capex`` live as ``theme:ai-capex`` entities. The
    old ticker-only regex never fired for them; broadened extraction
    matches any confirmed-construct-anchored entity by case-insensitive
    substring."""
    user_constructs.create_construct(
        db_session,
        user_id="u-1",
        kind="thesis",
        statement="AI capex cycle peaks 2027",
        entity_kind="theme",
        entity_value="ai-capex",
    )

    found = graph_retrieval.extract_entity_ids(
        db_session,
        user_id="u-1",
        text="what's your read on AI-capex pacing?",
    )

    assert found == ["theme:ai-capex"]


def test_extract_entities_skips_short_values(db_session) -> None:
    """Values <=3 chars would false-positive everywhere ("ai" matching
    "said", "again"). Skip them even if a construct exists."""
    user_constructs.create_construct(
        db_session,
        user_id="u-1",
        kind="thesis",
        statement="bullish AI",
        entity_kind="theme",
        entity_value="ai",
    )

    found = graph_retrieval.extract_entity_ids(
        db_session,
        user_id="u-1",
        text="I said again I'm bullish on ai infra",
    )

    assert found == []


def test_extract_entities_skips_trigger_disabled(db_session) -> None:
    """User-flagged opt-out: if ``is_trigger_disabled=True`` on the entity,
    even a clean substring match doesn't fire."""
    user_constructs.create_construct(
        db_session,
        user_id="u-1",
        kind="thesis",
        statement="long semis broadly",
        entity_kind="sector",
        entity_value="semiconductors",
    )
    entity = db_session.get(GraphEntity, "sector:semiconductors")
    entity.is_trigger_disabled = True
    db_session.flush()

    found = graph_retrieval.extract_entity_ids(
        db_session,
        user_id="u-1",
        text="semiconductors are rolling over",
    )

    assert found == []


def test_extract_entities_skips_other_users_constructs(db_session) -> None:
    """Substring path is user-scoped: only entities the *caller* has
    anchored constructs against should trigger. Otherwise users could
    inadvertently surface each other's themes."""
    user_constructs.create_construct(
        db_session,
        user_id="u-2",
        kind="thesis",
        statement="bob's view on risk-off",
        entity_kind="macro_regime",
        entity_value="risk-off",
    )

    found = graph_retrieval.extract_entity_ids(
        db_session,
        user_id="u-1",
        text="market feels risk-off today",
    )

    assert found == []


def test_extract_entities_ignores_unconfirmed_constructs(db_session) -> None:
    """Substring trigger requires a *confirmed* construct — proposed
    extractions shouldn't promote an entity into the trigger set before
    the user reviews them."""
    user_constructs.create_construct(
        db_session,
        user_id="u-1",
        kind="thesis",
        statement="proposed only",
        entity_kind="theme",
        entity_value="ai-capex",
        status="proposed",
    )

    found = graph_retrieval.extract_entity_ids(
        db_session,
        user_id="u-1",
        text="thoughts on ai-capex?",
    )

    assert found == []


def test_extract_entities_preserves_ticker_regex_fallback(db_session) -> None:
    """Backward compat: an uppercase ticker mention with NO existing
    construct for that user must still resolve via the regex path so the
    first-ever mention of ``NVDA`` finds the seeded entity."""
    # Seed entity directly without any user construct (e.g. global
    # ticker universe loaded outside the user's belief graph).
    from openlia_server.services import graph_store

    graph_store.entity_for(db_session, kind="ticker", value="NVDA")
    db_session.flush()

    found = graph_retrieval.extract_entity_ids(
        db_session,
        user_id="u-1",
        text="Quick take on NVDA?",
    )

    assert found == ["ticker:NVDA"]


def test_extract_entities_dedupes_and_sorts(db_session) -> None:
    """Multiple matches in one message should be deduped and sorted."""
    user_constructs.create_construct(
        db_session,
        user_id="u-1",
        kind="thesis",
        statement="ai capex thesis",
        entity_kind="theme",
        entity_value="ai-capex",
    )
    user_constructs.create_construct(
        db_session,
        user_id="u-1",
        kind="thesis",
        statement="semis exposure",
        entity_kind="sector",
        entity_value="semiconductors",
    )

    found = graph_retrieval.extract_entity_ids(
        db_session,
        user_id="u-1",
        text="ai-capex and semiconductors and AI-CAPEX again",
    )

    assert found == ["sector:semiconductors", "theme:ai-capex"]


def test_retrieve_memory_block_works_for_theme(db_session) -> None:
    """End-to-end: broadened extraction must feed into the memory block
    so theme-anchored beliefs land in the prompt."""
    user_constructs.create_construct(
        db_session,
        user_id="u-1",
        kind="thesis",
        statement="AI capex peaks 2027 per hyperscaler guidance",
        entity_kind="theme",
        entity_value="ai-capex",
    )

    block = graph_retrieval.retrieve_memory_block(
        db_session,
        user_id="u-1",
        message="give me your latest on ai-capex",
    )

    assert block is not None
    assert "ai-capex" in block
    assert "hyperscaler" in block
