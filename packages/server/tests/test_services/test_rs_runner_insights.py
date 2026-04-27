"""Integration test for the narrative-synthesis hook in RsRunner.

Asserts:
  - When `narrative_synthesizer` returns a non-empty string, the snapshot
    persisted by the runner carries that narrative through the row payload
    and back out via `RsSnapshotService.latest`.
  - When `narrative_synthesizer` is None, the snapshot has narrative=None.
"""

from __future__ import annotations

from collections.abc import Sequence

from openlia.retail_sentiment.schemas import (
    BatchClassifyResult,
    ClassificationLabel,
    ClassifiedItem,
    MetricSnapshot,
    RawSocialPost,
)
from openlia_server.services.rs_runner import RsRunner


class _BullishClassifier:
    def classify_batch(self, *, ticker: str, posts: Sequence[RawSocialPost]) -> BatchClassifyResult:
        return BatchClassifyResult(
            items=[
                ClassifiedItem(
                    id=p.id,
                    classification=ClassificationLabel.BULLISH,
                    confidence=0.9,
                    key_phrases=[],
                )
                for p in posts
            ]
        )


class _SnapshotStub:
    def __init__(self) -> None:
        self.writes: list[MetricSnapshot] = []

    def history(self, ticker, *, days=7, limit=100):
        return []

    def write(self, snap):
        self.writes.append(snap)
        return f"snap_{len(self.writes)}"

    def latest(self, ticker):
        return self.writes[-1] if self.writes else None

    def latest_many(self, tickers):
        return {}

    def all_recent_tickers(self, *, days=7):
        return []


class _AuditStub:
    def insert(self, audit):
        return "log"


def _factory():
    raise AssertionError("session_factory should not be invoked")


def test_narrative_synthesizer_populates_snapshot_narrative() -> None:
    snaps = _SnapshotStub()

    async def _synth(snap, signals):
        return "Bullish flow with above-baseline buzz."

    runner = RsRunner(
        session_factory=_factory,
        classifier=_BullishClassifier(),
        snapshot_service=snaps,  # type: ignore[arg-type]
        classification_log_service=_AuditStub(),  # type: ignore[arg-type]
        narrative_synthesizer=_synth,
    )
    result = runner.run_ticker("AAPL")
    assert result.snapshot.narrative == "Bullish flow with above-baseline buzz."
    assert snaps.writes[0].narrative == "Bullish flow with above-baseline buzz."


def test_no_synthesizer_means_narrative_is_none() -> None:
    snaps = _SnapshotStub()
    runner = RsRunner(
        session_factory=_factory,
        classifier=_BullishClassifier(),
        snapshot_service=snaps,  # type: ignore[arg-type]
        classification_log_service=_AuditStub(),  # type: ignore[arg-type]
        narrative_synthesizer=None,
    )
    result = runner.run_ticker("AAPL")
    assert result.snapshot.narrative is None


def test_synthesizer_failure_swallowed_to_none() -> None:
    async def _bad(snap, signals):
        raise RuntimeError("provider down")

    snaps = _SnapshotStub()
    runner = RsRunner(
        session_factory=_factory,
        classifier=_BullishClassifier(),
        snapshot_service=snaps,  # type: ignore[arg-type]
        classification_log_service=_AuditStub(),  # type: ignore[arg-type]
        narrative_synthesizer=_bad,
    )
    result = runner.run_ticker("AAPL")
    assert result.snapshot.narrative is None
