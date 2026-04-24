"""Retail Sentiment pipeline orchestrator.

Fetches raw posts, produces classifications (via an injected classifier),
computes the metric snapshot, and persists it. Also detects spikes from
recent history and returns them alongside the snapshot.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from openlia.retail_sentiment.metrics import compute_snapshot
from openlia.retail_sentiment.schemas import (
    ClassificationLabel,
    ClassifiedItem,
    MetricSnapshot,
    RawSocialPost,
    SpikeEvent,
)
from openlia.retail_sentiment.spike_detector import detect_spike
from sqlalchemy.orm import Session

from openlia_server.services.rs_snapshot import RsSnapshotService


class _DataProvider(Protocol):
    def fetch(self, *, requirement: str, ticker: str, **kwargs: Any) -> Any: ...


class _Classifier(Protocol):
    def classify_batch(
        self, *, ticker: str, posts: Sequence[RawSocialPost]
    ) -> list[ClassifiedItem]: ...


class NeutralClassifier:
    """Fallback classifier used when no LLM-backed one is wired.

    Marks every post neutral with confidence 0.5. Allows the pipeline to
    produce deterministic snapshots in dev/test without a live LLM.
    """

    def classify_batch(
        self, *, ticker: str, posts: Sequence[RawSocialPost]
    ) -> list[ClassifiedItem]:
        return [
            ClassifiedItem(
                id=p.id,
                classification=ClassificationLabel.NEUTRAL,
                confidence=0.5,
                key_phrases=[],
            )
            for p in posts
        ]


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
        data_provider: _DataProvider | None,
        classifier: _Classifier | None = None,
        snapshot_service: RsSnapshotService | None = None,
    ) -> None:
        self._factory = session_factory
        self._data = data_provider
        self._classifier = classifier or NeutralClassifier()
        self._snapshots = snapshot_service or RsSnapshotService(session_factory=session_factory)

    def _fetch_posts(self, ticker: str) -> list[RawSocialPost]:
        if self._data is None:
            return []
        posts: list[RawSocialPost] = []
        for requirement in ("social_sentiment", "company_news"):
            try:
                raw = self._data.fetch(requirement=requirement, ticker=ticker)
            except Exception:
                raw = None
            if not raw:
                continue
            posts.extend(_coerce_posts(raw, ticker=ticker, source=requirement))
        return posts

    def run_ticker(self, ticker: str) -> RsRunResult:
        posts = self._fetch_posts(ticker)
        classifications = self._classifier.classify_batch(ticker=ticker, posts=posts)
        prior = self._snapshots.history(ticker, days=7, limit=50)
        now = datetime.now(UTC)
        snap = compute_snapshot(
            ticker=ticker,
            captured_at=now,
            posts=posts,
            classifications=classifications,
            prior_snapshots=prior,
        )
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


def _coerce_posts(raw: Any, *, ticker: str, source: str) -> list[RawSocialPost]:
    """Best-effort coercion of adapter payloads into RawSocialPost."""
    out: list[RawSocialPost] = []
    if not isinstance(raw, list):
        return out
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        text = item.get("text") or item.get("title") or item.get("summary") or ""
        if not text:
            continue
        created_at = item.get("created_at") or item.get("published_at")
        if isinstance(created_at, str):
            try:
                created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError:
                created_dt = datetime.now(UTC)
        elif isinstance(created_at, datetime):
            created_dt = created_at
        else:
            created_dt = datetime.now(UTC)
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=UTC)
        out.append(
            RawSocialPost(
                id=str(item.get("id") or f"{source}:{ticker}:{idx}"),
                ticker=ticker,
                source=str(item.get("source") or source),
                text=str(text),
                engagement=item.get("engagement") or {},
                created_at=created_dt,
            )
        )
    return out
