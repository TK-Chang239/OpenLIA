"""Persistence helper for `rs_classification_log` audit rows.

One row per batch LLM classification call (success or failure). Called
from `RsRunner` whenever a classifier returns `BatchClassifyResult`
audits.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from openlia.retail_sentiment.schemas import ClassificationAudit
from sqlalchemy.orm import Session

from openlia_server.db.models.dashboard import RsClassificationLog


class RsClassificationLogService:
    def __init__(self, *, session_factory: Callable[[], Session]) -> None:
        self._factory = session_factory

    def insert(self, audit: ClassificationAudit) -> str:
        row_id = str(uuid.uuid4())
        with self._factory() as session:
            session.add(
                RsClassificationLog(
                    id=row_id,
                    batch_id=audit.batch_id,
                    ticker=audit.ticker,
                    model_ref=audit.model_ref,
                    item_count=audit.item_count,
                    prompt_tokens=audit.prompt_tokens,
                    completion_tokens=audit.completion_tokens,
                    latency_ms=audit.latency_ms,
                    error=audit.error,
                )
            )
            session.commit()
        return row_id

    def recent(self, *, ticker: str | None = None, limit: int = 50) -> list[RsClassificationLog]:
        with self._factory() as session:
            q = session.query(RsClassificationLog)
            if ticker is not None:
                q = q.filter(RsClassificationLog.ticker == ticker)
            return q.order_by(RsClassificationLog.created_at.desc()).limit(limit).all()
