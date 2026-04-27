"""Retail Sentiment pipeline orchestrator.

Fetches raw posts, produces classifications (via an injected classifier),
computes the metric snapshot, persists it, and (when a Quick-tier model
is configured) synthesizes a narrative paragraph for the Insights tab.

Classifiers return a `BatchClassifyResult` (items + audits). For the
LLM-backed classifier each LLM call emits one `ClassificationAudit`,
which the runner persists into `rs_classification_log`. The neutral
stub emits no audits (no LLM call was made).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from openlia.retail_sentiment.metrics import compute_snapshot
from openlia.retail_sentiment.schemas import (
    BatchClassifyResult,
    ClassificationLabel,
    ClassifiedItem,
    MetricSnapshot,
    RawSocialPost,
    SignalAlert,
    SpikeEvent,
)
from openlia.retail_sentiment.spike_detector import detect_spike
from sqlalchemy.orm import Session

from openlia_server.services.rs_classification_log import RsClassificationLogService
from openlia_server.services.rs_snapshot import RsSnapshotService


class _Classifier(Protocol):
    def classify_batch(
        self, *, ticker: str, posts: Sequence[RawSocialPost]
    ) -> BatchClassifyResult: ...


# Optional sync wrapper around the async narrative-synthesis call.
NarrativeSynthesizer = Callable[
    [MetricSnapshot, Sequence[SignalAlert]],
    Awaitable[str | None],
]


class NeutralClassifier:
    """Fallback classifier used when no LLM-backed one is wired.

    Marks every post neutral with confidence 0.5. Allows the pipeline to
    produce deterministic snapshots in dev/test without a live LLM. No
    audit rows are emitted because no LLM call was made.
    """

    def classify_batch(self, *, ticker: str, posts: Sequence[RawSocialPost]) -> BatchClassifyResult:
        items = [
            ClassifiedItem(
                id=p.id,
                classification=ClassificationLabel.NEUTRAL,
                confidence=0.5,
                key_phrases=[],
            )
            for p in posts
        ]
        return BatchClassifyResult(items=items, audits=[])


@dataclass
class RsRunResult:
    snapshot: MetricSnapshot
    snapshot_id: str
    spike: SpikeEvent | None


class RsRunner:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        classifier: _Classifier | None = None,
        snapshot_service: RsSnapshotService | None = None,
        classification_log_service: RsClassificationLogService | None = None,
        narrative_synthesizer: NarrativeSynthesizer | None = None,
    ) -> None:
        self._factory = session_factory
        self._classifier = classifier or NeutralClassifier()
        self._snapshots = snapshot_service or RsSnapshotService(session_factory=session_factory)
        self._classification_log = classification_log_service or RsClassificationLogService(
            session_factory=session_factory
        )
        self._narrative_synthesizer = narrative_synthesizer

    def _fetch_posts(self, ticker: str) -> list[RawSocialPost]:
        # RS runtime data wiring through the connector dispatcher is a follow-up
        # to the connector cutover; production was already silently empty here
        # because the legacy provider hook was never set on production paths.
        return []

    def _fetch_optional(self, ticker: str) -> dict[str, Any]:
        return {}

    def run_ticker(self, ticker: str) -> RsRunResult:
        posts = self._fetch_posts(ticker)
        optional = self._fetch_optional(ticker)
        result = self._classifier.classify_batch(ticker=ticker, posts=posts)
        for audit in result.audits:
            self._classification_log.insert(audit)
        prior = self._snapshots.history(ticker, days=7, limit=50)
        now = datetime.now(UTC)
        snap = compute_snapshot(
            ticker=ticker,
            captured_at=now,
            posts=posts,
            classifications=result.items,
            prior_snapshots=prior,
            optional_inputs=optional or None,
        )

        if self._narrative_synthesizer is not None:
            narrative = self._run_narrative(snap, signals=())
            if narrative:
                snap = snap.model_copy(update={"narrative": narrative})

        snap_id = self._snapshots.write(snap)
        spike = detect_spike(
            ticker=ticker,
            detected_at=now,
            current_buzz=snap.buzz_volume,
            recent_snapshots=prior,
        )
        return RsRunResult(snapshot=snap, snapshot_id=snap_id, spike=spike)

    def run_many(self, tickers: Sequence[str]) -> list[RsRunResult]:
        return [self.run_ticker(t) for t in tickers]

    def _run_narrative(
        self,
        snap: MetricSnapshot,
        *,
        signals: Sequence[SignalAlert],
    ) -> str | None:
        synth = self._narrative_synthesizer
        if synth is None:
            return None
        try:
            return asyncio.run(synth(snap, signals))
        except Exception:
            return None
