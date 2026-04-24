"""Retail Sentiment snapshot read/write layer."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from openlia.retail_sentiment.schemas import MetricSnapshot
from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.dashboard import RsSnapshot


def _snapshot_to_row_payload(snap: MetricSnapshot) -> dict[str, Any]:
    return {
        "sentiment_score": snap.sentiment_score,
        "buzz_volume": snap.buzz_volume,
        "sentiment_momentum": snap.sentiment_momentum,
        "bull_bear_ratio": snap.bull_bear_ratio,
        "buzz_sentiment_divergence": snap.buzz_sentiment_divergence,
        "social_velocity": snap.social_velocity,
        "cross_source_agreement": snap.cross_source_agreement,
        "put_call_ratio": snap.put_call_ratio,
        "short_interest_pressure": snap.short_interest_pressure,
        "narrative_concentration": snap.narrative_concentration,
        "institutional_retail_gap": snap.institutional_retail_gap,
        "event_sensitivity": snap.event_sensitivity,
    }


def _row_to_metric_snapshot(row: RsSnapshot) -> MetricSnapshot:
    data = row.snapshot_data
    return MetricSnapshot(
        ticker=row.ticker,
        captured_at=row.captured_at,
        sentiment_score=float(data.get("sentiment_score", 0.0)),
        buzz_volume=float(data.get("buzz_volume", 0.0)),
        sentiment_momentum=float(data.get("sentiment_momentum", 0.0)),
        bull_bear_ratio=float(data.get("bull_bear_ratio", 0.0)),
        buzz_sentiment_divergence=float(data.get("buzz_sentiment_divergence", 0.0)),
        social_velocity=float(data.get("social_velocity", 0.0)),
        cross_source_agreement=float(data.get("cross_source_agreement", 0.0)),
        put_call_ratio=data.get("put_call_ratio"),
        short_interest_pressure=data.get("short_interest_pressure"),
        narrative_concentration=data.get("narrative_concentration"),
        institutional_retail_gap=data.get("institutional_retail_gap"),
        event_sensitivity=data.get("event_sensitivity"),
        source_breakdown=row.source_breakdown or {},
    )


class RsSnapshotService:
    def __init__(self, *, session_factory: Callable[[], Session]) -> None:
        self._factory = session_factory

    def write(self, snap: MetricSnapshot) -> str:
        with self._factory() as s:
            row = RsSnapshot(
                id=str(uuid.uuid4()),
                ticker=snap.ticker,
                snapshot_data=_snapshot_to_row_payload(snap),
                source_breakdown=dict(snap.source_breakdown),
                captured_at=snap.captured_at,
            )
            s.add(row)
            s.commit()
            return row.id

    def latest(self, ticker: str) -> MetricSnapshot | None:
        with self._factory() as s:
            row = s.scalars(
                select(RsSnapshot)
                .where(RsSnapshot.ticker == ticker)
                .order_by(RsSnapshot.captured_at.desc())
                .limit(1)
            ).first()
            if row is None:
                return None
            return _row_to_metric_snapshot(row)

    def history(self, ticker: str, *, days: int = 7, limit: int = 100) -> list[MetricSnapshot]:
        since = datetime.now(UTC) - timedelta(days=days)
        with self._factory() as s:
            rows = list(
                s.scalars(
                    select(RsSnapshot)
                    .where(
                        RsSnapshot.ticker == ticker,
                        RsSnapshot.captured_at >= since,
                    )
                    .order_by(RsSnapshot.captured_at.asc())
                    .limit(limit)
                ).all()
            )
            return [_row_to_metric_snapshot(r) for r in rows]

    def latest_many(self, tickers: Sequence[str]) -> dict[str, MetricSnapshot]:
        out: dict[str, MetricSnapshot] = {}
        for t in tickers:
            snap = self.latest(t)
            if snap is not None:
                out[t] = snap
        return out

    def all_recent_tickers(self, *, days: int = 7) -> list[str]:
        since = datetime.now(UTC) - timedelta(days=days)
        with self._factory() as s:
            rows = list(
                s.scalars(
                    select(RsSnapshot.ticker).where(RsSnapshot.captured_at >= since).distinct()
                ).all()
            )
            return list(rows)
