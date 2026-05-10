"""Slice 12 — server-side recall_artifacts handler.

Verifies the handler wraps ``services.graph_vectors.recall_artifacts``
correctly: opens a fresh DB session per call, projects rows to the
compact ``{id, subject, tagline, score}`` shape the model expects,
errors on missing user context, and honors per-user scoping.
"""

from __future__ import annotations

import pytest
from openlia.llm.embeddings import FakeEmbeddingProvider
from openlia_server.runtime_tools.recall_artifacts import (
    _MissingUserError,
    build_recall_artifacts_handler,
)
from openlia_server.services import graph_vectors


@pytest.mark.asyncio
async def test_handler_returns_compact_rows_with_subject_and_tagline(
    db_session, db_session_factory, make_user
) -> None:
    user = make_user(email="alice@example.com")
    provider = FakeEmbeddingProvider(dim=32)
    graph_vectors.upsert_artifact_summary(
        db_session,
        user_id=user.id,
        artifact_kind="report",
        artifact_id="rep-a",
        summary_text="NVDA Q3 earnings beat on services margin",
        provider=provider,
        model_name="fake-d32",
        subject="NVDA",
        tagline="Q3 services margin beat",
    )
    db_session.commit()

    handler = build_recall_artifacts_handler(
        db_session_factory=db_session_factory,
        provider=provider,
    )
    rows = await handler(user.id, "NVDA Q3 earnings beat on services margin", 5)

    assert len(rows) == 1
    row = rows[0]
    # Compact projection only — no summary_text or embedding bytes.
    assert set(row.keys()) == {"id", "subject", "tagline", "score"}
    assert row["id"] == "rep-a"
    assert row["subject"] == "NVDA"
    assert row["tagline"] == "Q3 services margin beat"
    assert isinstance(row["score"], float)


@pytest.mark.asyncio
async def test_handler_scopes_results_per_user(
    db_session, db_session_factory, make_user
) -> None:
    """Two users with identical summaries — each user's recall returns
    only their own row, never the other's."""
    alice = make_user(email="alice@example.com")
    bob = make_user(email="bob@example.com")
    provider = FakeEmbeddingProvider(dim=16)

    graph_vectors.upsert_artifact_summary(
        db_session,
        user_id=alice.id,
        artifact_kind="report",
        artifact_id="rep-alice",
        summary_text="quarterly earnings",
        provider=provider,
        model_name="fake-d16",
        subject="Alice's",
    )
    graph_vectors.upsert_artifact_summary(
        db_session,
        user_id=bob.id,
        artifact_kind="report",
        artifact_id="rep-bob",
        summary_text="quarterly earnings",
        provider=provider,
        model_name="fake-d16",
        subject="Bob's",
    )
    db_session.commit()

    handler = build_recall_artifacts_handler(
        db_session_factory=db_session_factory,
        provider=provider,
    )
    alice_hits = await handler(alice.id, "quarterly earnings", 5)
    bob_hits = await handler(bob.id, "quarterly earnings", 5)

    assert {r["id"] for r in alice_hits} == {"rep-alice"}
    assert {r["id"] for r in bob_hits} == {"rep-bob"}


@pytest.mark.asyncio
async def test_handler_empty_corpus_returns_empty_list(db_session_factory) -> None:
    """Slice-12 contract: no rows for the user → ``[]``, not an error."""
    handler = build_recall_artifacts_handler(
        db_session_factory=db_session_factory,
        provider=FakeEmbeddingProvider(dim=8),
    )
    rows = await handler("ghost-user", "anything", 5)
    assert rows == []


@pytest.mark.asyncio
async def test_handler_rejects_missing_user_id(db_session_factory) -> None:
    handler = build_recall_artifacts_handler(
        db_session_factory=db_session_factory,
        provider=FakeEmbeddingProvider(dim=8),
    )
    with pytest.raises(_MissingUserError):
        await handler(None, "query", 5)


@pytest.mark.asyncio
async def test_handler_opens_fresh_session_per_call(db_session_factory) -> None:
    """The handler must close its session after each call so the chat
    runner cannot accidentally accumulate open DB connections."""
    closed_count = 0
    real_factory = db_session_factory

    class _CountingSession:
        """Wraps a real session and records close() invocations."""

        def __init__(self) -> None:
            self._inner = real_factory()

        def __getattr__(self, name: str):
            # __getattr__ only fires for attrs not on the instance; the
            # `_inner` attr above is set in __init__ so it never lands
            # here (no recursion). Forward everything else to the real
            # session.
            return getattr(self._inner, name)

        def close(self) -> None:
            nonlocal closed_count
            closed_count += 1
            self._inner.close()

    opened: list[_CountingSession] = []

    def spy_factory():
        s = _CountingSession()
        opened.append(s)
        return s

    handler = build_recall_artifacts_handler(
        db_session_factory=spy_factory,
        provider=FakeEmbeddingProvider(dim=8),
    )
    await handler("u-1", "q", 5)
    await handler("u-1", "q", 5)
    assert len(opened) == 2
    assert closed_count == 2
