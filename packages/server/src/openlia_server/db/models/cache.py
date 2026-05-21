"""ORM model for the persistent document cache (F5).

Stores connector tool call results keyed by a canonical cache key so
repeated upstream fetches (financials, filings, etc.) are served locally.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base, UTCDateTime


class CachedDocument(Base):
    __tablename__ = "cached_documents"

    cache_key: Mapped[str] = mapped_column(String(512), primary_key=True)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    document_id: Mapped[str] = mapped_column(String(256), nullable=False)
    ticker: Mapped[str | None] = mapped_column(String(32), nullable=True)
    fiscal_period: Mapped[str | None] = mapped_column(String(32), nullable=True)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    original_retrieved_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    cached_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    bytes_size: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (Index("ix_cached_documents_ticker_fiscal", "ticker", "fiscal_period"),)
