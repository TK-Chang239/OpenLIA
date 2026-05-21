"""SQLAlchemy-backed CacheStore for connector tool call results (F5).

Implements the CacheStore Protocol from cache_wrapper.py using the
server's SQLite/Postgres database. get() returns a CachedDocument ORM row
directly (callers read .content_text and .raw_metadata). upsert() writes
or replaces the row.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from openlia.llm.runtime.report_v2.connectors.base import ToolResult

from openlia_server.db.models.cache import CachedDocument
from openlia_server.db.session import SessionLocal


class SQLAlchemyCacheStore:
    """CacheStore backed by the server database.

    Pass ``session_factory`` to inject a custom factory (useful in tests);
    defaults to the global ``SessionLocal``.
    """

    def __init__(self, session_factory=None) -> None:
        self._sf = session_factory or SessionLocal

    def get(self, key: str) -> CachedDocument | None:
        with self._sf() as db:
            return db.get(CachedDocument, key)

    def upsert(self, key: str, result: ToolResult, **meta: Any) -> None:
        content = result.content if isinstance(result.content, str) else str(result.content)
        bytes_size = len(content.encode())

        now = datetime.now(UTC)
        retrieved_at_str = meta.get("retrieved_at")
        if retrieved_at_str:
            try:
                original_retrieved_at = datetime.fromisoformat(retrieved_at_str)
                if original_retrieved_at.tzinfo is None:
                    original_retrieved_at = original_retrieved_at.replace(tzinfo=UTC)
            except ValueError:
                original_retrieved_at = now
        else:
            original_retrieved_at = now

        source = str(meta.get("adapter_name", "unknown"))
        tool = str(meta.get("tool", "unknown"))

        # Parse ticker/fiscal_period from key: <adapter>:<tool>:<ticker>:<period>
        parts = key.split(":")
        ticker: str | None = parts[2] if len(parts) >= 3 and parts[2] != "_" else None
        fiscal_period: str | None = parts[3] if len(parts) >= 4 else None

        row = CachedDocument(
            cache_key=key,
            source=source,
            document_id=f"{source}:{tool}",
            ticker=ticker,
            fiscal_period=fiscal_period,
            content_text=content,
            raw_metadata=dict(result.metadata),
            original_retrieved_at=original_retrieved_at,
            cached_at=now,
            bytes_size=bytes_size,
        )

        with self._sf() as db:
            db.merge(row)
            db.commit()
