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


def test_recall_artifacts_returns_most_similar_summary_first(db_session) -> None:
    """Slice 12: brute-force cosine search ranks the artifact whose
    summary embedding most closely matches the query vector. Since the
    fake provider is deterministic, embedding the same text twice gives
    identical vectors (cosine == 1.0) — so the artifact whose summary
    matches the query verbatim must rank first."""
    provider = FakeEmbeddingProvider(dim=32)

    graph_vectors.upsert_artifact_summary(
        db_session,
        user_id="u-1",
        artifact_kind="report",
        artifact_id="rep-a",
        summary_text="NVDA Q3 earnings beat on services margin",
        provider=provider,
        model_name="fake-d32",
    )
    graph_vectors.upsert_artifact_summary(
        db_session,
        user_id="u-1",
        artifact_kind="report",
        artifact_id="rep-b",
        summary_text="totally unrelated content about coffee",
        provider=provider,
        model_name="fake-d32",
    )

    hits = graph_vectors.recall_artifacts(
        db_session,
        user_id="u-1",
        query_text="NVDA Q3 earnings beat on services margin",
        provider=provider,
        top_k=2,
    )

    assert len(hits) == 2
    top, score = hits[0]
    assert top.artifact_id == "rep-a"
    assert score == pytest.approx(1.0, abs=1e-4)


def test_upsert_artifact_summary_persists_structured_fields(db_session) -> None:
    """Slice 9: structured metadata (subject/tagline/findings/entities/tone/
    horizon) is persisted alongside the embedded ``summary_text`` so
    slice-12 retrieval can pre-filter before cosine ranking."""
    provider = FakeEmbeddingProvider(dim=8)

    row = graph_vectors.upsert_artifact_summary(
        db_session,
        user_id="u-1",
        artifact_kind="report",
        artifact_id="rep-structured",
        summary_text="NVDA Q3 services margin expansion",
        provider=provider,
        model_name="fake-d8",
        subject="NVDA",
        tagline="Services margin durable",
        findings_text="Services margin up 400bps. Data center beat.",
        entities_mentioned=["ticker:NVDA", "sector:semis"],
        tone="bullish",
        horizon="medium",
    )

    db_session.refresh(row)
    assert row.subject == "NVDA"
    assert row.tagline == "Services margin durable"
    assert row.findings_text == "Services margin up 400bps. Data center beat."
    assert row.entities_mentioned == ["ticker:NVDA", "sector:semis"]
    assert row.tone == "bullish"
    assert row.horizon == "medium"


def test_upsert_artifact_summary_updates_structured_fields_in_place(db_session) -> None:
    provider = FakeEmbeddingProvider(dim=8)

    first = graph_vectors.upsert_artifact_summary(
        db_session,
        user_id="u-1",
        artifact_kind="report",
        artifact_id="rep-update",
        summary_text="initial",
        provider=provider,
        model_name="fake-d8",
        subject="NVDA",
        tagline="initial tagline",
        findings_text="initial findings",
        entities_mentioned=["ticker:NVDA"],
        tone="neutral",
        horizon="short",
    )
    second = graph_vectors.upsert_artifact_summary(
        db_session,
        user_id="u-1",
        artifact_kind="report",
        artifact_id="rep-update",
        summary_text="revised",
        provider=provider,
        model_name="fake-d8",
        subject="NVDA",
        tagline="revised tagline",
        findings_text="revised findings",
        entities_mentioned=["ticker:NVDA", "theme:AI"],
        tone="bearish",
        horizon="long",
    )

    assert first.id == second.id
    db_session.refresh(second)
    assert second.tagline == "revised tagline"
    assert second.findings_text == "revised findings"
    assert second.entities_mentioned == ["ticker:NVDA", "theme:AI"]
    assert second.tone == "bearish"
    assert second.horizon == "long"


def test_upsert_artifact_summary_invalid_tone_raises(db_session) -> None:
    provider = FakeEmbeddingProvider(dim=8)
    with pytest.raises(ValueError, match="tone"):
        graph_vectors.upsert_artifact_summary(
            db_session,
            user_id="u-1",
            artifact_kind="report",
            artifact_id="rep-bad-tone",
            summary_text="x",
            provider=provider,
            model_name="fake-d8",
            tone="exuberant",
        )


def test_upsert_artifact_summary_invalid_horizon_raises(db_session) -> None:
    provider = FakeEmbeddingProvider(dim=8)
    with pytest.raises(ValueError, match="horizon"):
        graph_vectors.upsert_artifact_summary(
            db_session,
            user_id="u-1",
            artifact_kind="report",
            artifact_id="rep-bad-horizon",
            summary_text="x",
            provider=provider,
            model_name="fake-d8",
            horizon="forever",
        )


def test_upsert_artifact_summary_defaults_structured_fields_to_none(db_session) -> None:
    """Backwards compat: callers passing only the original args persist
    None for every new structured column."""
    provider = FakeEmbeddingProvider(dim=8)

    row = graph_vectors.upsert_artifact_summary(
        db_session,
        user_id="u-1",
        artifact_kind="session",
        artifact_id="s-bc",
        summary_text="legacy summary",
        provider=provider,
        model_name="fake-d8",
    )
    db_session.refresh(row)
    assert row.subject is None
    assert row.tagline is None
    assert row.findings_text is None
    assert row.entities_mentioned is None
    assert row.tone is None
    assert row.horizon is None


def test_recall_artifacts_filters_to_user(db_session) -> None:
    """No matter how close another user's summary is, it must not leak
    into Alice's recall."""
    provider = FakeEmbeddingProvider(dim=16)

    graph_vectors.upsert_artifact_summary(
        db_session,
        user_id="u-2",
        artifact_kind="report",
        artifact_id="rep-bob",
        summary_text="exact match string",
        provider=provider,
        model_name="fake-d16",
    )
    graph_vectors.upsert_artifact_summary(
        db_session,
        user_id="u-1",
        artifact_kind="report",
        artifact_id="rep-alice",
        summary_text="alice's only summary",
        provider=provider,
        model_name="fake-d16",
    )

    hits = graph_vectors.recall_artifacts(
        db_session,
        user_id="u-1",
        query_text="exact match string",
        provider=provider,
        top_k=5,
    )

    assert [h[0].artifact_id for h in hits] == ["rep-alice"]
