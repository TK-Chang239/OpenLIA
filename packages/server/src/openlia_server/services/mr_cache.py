"""MRCacheStore implementation — backs Plan 6's MRCacheStore Protocol."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.dashboard import MrAssessmentCache


class MRCacheStoreImpl:
    """Persist T4/T5 LLM output in `mr_assessment_cache`."""

    def save(self, *, session: Session, user_id: str, payload: dict[str, Any]) -> str:
        """Insert a cache row. `user_id` is unused — cache is global per design spec."""
        now = datetime.now(UTC)
        ttl_hours = payload.get("ttl_hours", 168)
        cache_id = str(uuid.uuid4())
        row = MrAssessmentCache(
            id=cache_id,
            dashboard=payload["dashboard"],
            assessment_type=payload.get("assessment_type", "synthesis"),
            input_hash=payload.get("input_hash", ""),
            result=payload.get("result", payload),
            model_ref=payload.get("model_ref", "unknown"),
            token_usage=payload.get("token_usage"),
            generated_at=now,
            expires_at=now + timedelta(hours=ttl_hours),
        )
        session.add(row)
        session.flush()
        return cache_id

    def read_latest(
        self,
        *,
        session: Session,
        user_id: str,
        dashboard: str,
        assessment_type: str,
    ) -> dict[str, Any] | None:
        now = datetime.now(UTC)
        stmt = (
            select(MrAssessmentCache)
            .where(
                MrAssessmentCache.dashboard == dashboard,
                MrAssessmentCache.assessment_type == assessment_type,
                MrAssessmentCache.expires_at > now,
            )
            .order_by(MrAssessmentCache.generated_at.desc())
            .limit(1)
        )
        row = session.scalars(stmt).first()
        if row is None:
            return None
        return {
            "id": row.id,
            "dashboard": row.dashboard,
            "assessment_type": row.assessment_type,
            "result": row.result,
            "model_ref": row.model_ref,
            "generated_at": row.generated_at,
            "expires_at": row.expires_at,
            # Expose top-level keys some callers expect to read directly.
            **(row.result if isinstance(row.result, dict) else {}),
        }
