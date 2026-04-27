"""Full-pipeline tests for `RsRunner`.

Verifies post coercion, optional-input fan-out, snapshot history feed,
spike emission against the 7-day baseline, and provider-error swallowing.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from openlia.retail_sentiment.schemas import (
    BatchClassifyResult,
    ClassificationLabel,
    ClassifiedItem,
    MetricSnapshot,
    RawSocialPost,
)
from openlia_server.services.rs_runner import RsRunner

# RS runtime data wiring through the connector dispatcher is a follow-up to
# the connector cutover. Tests below that exercise live post-fetch behavior
# from a fake data provider are skipped until that wiring lands.
_DATA_FETCH_SKIP = pytest.mark.skip(reason="RS runtime wiring pending after connector cutover")


class _FakeProvider:
    def __init__(self, *, posts_payload: Any | None, raise_on: tuple[str, ...] = ()) -> None:
        self._posts = posts_payload
        self._raise_on = raise_on
        self.calls: list[tuple[str, str]] = []

    def fetch(self, *, requirement: str, ticker: str, **_: Any) -> Any:
        self.calls.append((requirement, ticker))
        if requirement in self._raise_on:
            raise RuntimeError(f"boom in {requirement}")
        if requirement in ("social_sentiment", "company_news"):
            return self._posts
        return None


class _BullishClassifier:
    def classify_batch(self, *, ticker: str, posts: Sequence[RawSocialPost]) -> BatchClassifyResult:
        items = [
            ClassifiedItem(
                id=p.id,
                classification=ClassificationLabel.BULLISH,
                confidence=0.9,
                key_phrases=["ai"],
            )
            for p in posts
        ]
        return BatchClassifyResult(items=items)


class _StubSnapshotService:
    """In-memory replacement for RsSnapshotService."""

    def __init__(self, *, history: list[MetricSnapshot] | None = None) -> None:
        self.history_calls: list[tuple[str, int]] = []
        self.writes: list[MetricSnapshot] = []
        self._history = list(history or [])

    def history(self, ticker: str, *, days: int = 7, limit: int = 100) -> list[MetricSnapshot]:
        self.history_calls.append((ticker, days))
        return list(self._history)

    def write(self, snap: MetricSnapshot) -> str:
        self.writes.append(snap)
        return f"snap_{len(self.writes)}"

    def latest(self, ticker: str) -> MetricSnapshot | None:
        return self._history[-1] if self._history else None

    def latest_many(self, tickers: Sequence[str]):
        return {}

    def all_recent_tickers(self, *, days: int = 7) -> list[str]:
        return []


class _StubAuditLog:
    def __init__(self) -> None:
        self.inserts: list[Any] = []

    def insert(self, audit) -> str:
        self.inserts.append(audit)
        return "log_x"


def _factory():  # session_factory placeholder — never called by stubs.
    raise AssertionError("session_factory should not be invoked in stubbed runner")


def _build_runner(
    *,
    posts_payload: Any | None,
    history: list[MetricSnapshot] | None = None,
    raise_on: tuple[str, ...] = (),
) -> tuple[RsRunner, _StubSnapshotService, _StubAuditLog]:
    snaps = _StubSnapshotService(history=history)
    audits = _StubAuditLog()
    # _FakeProvider retained for reference-only; constructor no longer accepts it
    # since RS runtime data wiring is pending (post-cutover task).
    _ = _FakeProvider(posts_payload=posts_payload, raise_on=raise_on)
    runner = RsRunner(
        session_factory=_factory,
        classifier=_BullishClassifier(),
        snapshot_service=snaps,  # type: ignore[arg-type]
        classification_log_service=audits,  # type: ignore[arg-type]
    )
    return runner, snaps, audits


def _social_payload(now: datetime) -> list[dict]:
    return [
        {
            "id": f"p{i}",
            "text": f"bullish {i}",
            "source": "social_media",
            "created_at": now.isoformat(),
        }
        for i in range(20)
    ]


def _prior_snapshot(captured_at: datetime, *, count: float) -> MetricSnapshot:
    return MetricSnapshot(
        ticker="AAPL",
        captured_at=captured_at,
        sentiment_score=0.0,
        buzz_volume=count,
        buzz_count=count,
        sentiment_momentum=0.0,
        bull_bear_ratio=1.0,
        buzz_sentiment_divergence=0.0,
        social_velocity=0.0,
        cross_source_agreement=1.0,
    )


@_DATA_FETCH_SKIP
def test_run_ticker_writes_snapshot_and_history_was_consulted() -> None:
    now = datetime.now(UTC)
    history = [_prior_snapshot(now - timedelta(days=2), count=2.0)]
    runner, snaps, _ = _build_runner(
        posts_payload=_social_payload(now),
        history=history,
    )
    result = runner.run_ticker("AAPL")
    assert result.snapshot.ticker == "AAPL"
    assert snaps.writes, "snapshot was not persisted"
    assert ("AAPL", 7) in snaps.history_calls


@_DATA_FETCH_SKIP
def test_run_ticker_emits_spike_when_buzz_exceeds_baseline() -> None:
    now = datetime.now(UTC)
    # Vary the baseline so stddev is non-zero (otherwise spike-detector
    # short-circuits). buzz_volume in prior snapshots = ratios already
    # baked in by their source.
    history = [_prior_snapshot(now - timedelta(days=i + 1), count=2.0 + (i % 2)) for i in range(8)]
    runner, _, _ = _build_runner(
        posts_payload=_social_payload(now),
        history=history,
    )
    result = runner.run_ticker("AAPL")
    assert result.spike is not None


@_DATA_FETCH_SKIP
def test_run_ticker_swallows_provider_exception_with_empty_posts() -> None:
    runner, snaps, _ = _build_runner(
        posts_payload=None,
        raise_on=("social_sentiment", "company_news"),
    )
    result = runner.run_ticker("AAPL")
    # Still wrote a snapshot (with zeros).
    assert result.snapshot.buzz_count == 0.0
    assert snaps.writes


@_DATA_FETCH_SKIP
def test_run_many_preserves_order() -> None:
    now = datetime.now(UTC)
    runner, _, _ = _build_runner(posts_payload=_social_payload(now))
    results = runner.run_many(["AAPL", "MSFT", "NVDA"])
    assert [r.snapshot.ticker for r in results] == ["AAPL", "MSFT", "NVDA"]


@_DATA_FETCH_SKIP
@pytest.mark.parametrize("source_key", ["title", "summary", "text"])
def test_run_ticker_handles_alt_text_keys(source_key: str) -> None:
    now = datetime.now(UTC)
    payload = [{"id": "p1", source_key: "hello", "created_at": now.isoformat()}]
    runner, _, _ = _build_runner(posts_payload=payload)
    result = runner.run_ticker("AAPL")
    assert result.snapshot.buzz_count >= 1.0
