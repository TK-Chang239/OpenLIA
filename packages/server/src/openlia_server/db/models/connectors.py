"""SQLAlchemy models for the connector redesign.

See docs/superpowers/specs/2026-04-26-connector-redesign-design.md §4.
Owned by the connector-redesign plan. Registered for metadata via
db.models.register_all (side-effect import).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base, UTCDateTime


class Connector(Base):
    __tablename__ = "connectors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    launch: Mapped[dict] = mapped_column(JSON, nullable=False)
    credentials_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cached_tools: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_connectors_provider_id", "provider_id"),
        Index("ix_connectors_category", "category"),
        Index("ix_connectors_status", "status"),
        CheckConstraint(
            "source IN ('built_in', 'remote_mcp', 'cli_mcp')",
            name="source",
        ),
        CheckConstraint(
            "category IN ('financial', 'news', 'social', 'web_search')",
            name="category",
        ),
        CheckConstraint(
            "status IN ('pending', 'validated', 'failed')",
            name="status",
        ),
    )


