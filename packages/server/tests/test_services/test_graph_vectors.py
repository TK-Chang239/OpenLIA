"""Slice 10 — vector storage for the cross-session memory graph.

Two storage seams:

* UserConstruct rows gain an ``embedding`` BLOB + ``embedding_model``
  tag so retrieval (slice 12) can match the user's live message against
  every confirmed belief.
* ``graph_artifact_summaries`` is a new table — one summary embedding
  per (user, artifact). Reports and chat sessions each contribute one
  row; the summary text comes from upstream (LLM-generated at write
  time for reports, session-close for chats).
"""

from __future__ import annotations

import struct

import pytest
from openlia.llm.embeddings import FakeEmbeddingProvider
from openlia_server.services import graph_vectors, user_constructs


def test_embed_and_store_construct_writes_blob_and_model(db_session) -> None:
    construct = user_constructs.create_construct(
        db_session,
        user_id="u-1",
        kind="thesis",
        statement="NVDA services-margin expansion is durable",
        entity_kind="ticker",
        entity_value="NVDA",
    )
    provider = FakeEmbeddingProvider(dim=8)

    graph_vectors.embed_and_store_construct(
        db_session,
        construct=construct,
        provider=provider,
        model_name="fake-d8",
    )
    db_session.refresh(construct)

    assert construct.embedding is not None
    assert construct.embedding_model == "fake-d8"
    # 8 floats * 4 bytes each.
    assert len(construct.embedding) == 8 * 4
    decoded = list(struct.unpack(f"<{8}f", construct.embedding))
    # Float32 precision: decoded vector approximates the float64 input.
    assert decoded == pytest.approx(provider.embed([construct.statement])[0])


def test_upsert_artifact_summary_creates_then_updates_in_place(db_session) -> None:
    provider = FakeEmbeddingProvider(dim=8)

    first = graph_vectors.upsert_artifact_summary(
        db_session,
        user_id="u-1",
        artifact_kind="session",
        artifact_id="s-1",
        summary_text="Initial summary",
        provider=provider,
        model_name="fake-d8",
    )
    second = graph_vectors.upsert_artifact_summary(
        db_session,
        user_id="u-1",
        artifact_kind="session",
        artifact_id="s-1",
        summary_text="Updated summary text",
        provider=provider,
        model_name="fake-d8",
    )

    assert first.id == second.id  # same row, no duplication
    db_session.refresh(second)
    assert second.summary_text == "Updated summary text"

    expected = provider.embed(["Updated summary text"])[0]
    decoded = list(struct.unpack(f"<{8}f", second.embedding))
    assert decoded == pytest.approx(expected)


def test_artifact_summary_scoped_per_user(db_session) -> None:
    """Two users with the same artifact_id (e.g. shared session feature
    later) must own independent summary rows so embeddings don't leak
    across tenants."""
    provider = FakeEmbeddingProvider(dim=8)

    graph_vectors.upsert_artifact_summary(
        db_session,
        user_id="u-1",
        artifact_kind="report",
        artifact_id="rep-shared",
        summary_text="alice's summary",
        provider=provider,
        model_name="fake-d8",
    )
    graph_vectors.upsert_artifact_summary(
        db_session,
        user_id="u-2",
        artifact_kind="report",
        artifact_id="rep-shared",
        summary_text="bob's summary",
        provider=provider,
        model_name="fake-d8",
    )

    rows_u1 = graph_vectors.list_artifact_summaries(db_session, user_id="u-1")
    rows_u2 = graph_vectors.list_artifact_summaries(db_session, user_id="u-2")
    assert len(rows_u1) == 1 and rows_u1[0].summary_text == "alice's summary"
    assert len(rows_u2) == 1 and rows_u2[0].summary_text == "bob's summary"
