"""SQLAlchemy models for the connector redesign.

See docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md §3.
Owned by the connector-redesign-v2 plan. Registered for metadata via
db.models.register_all (side-effect import).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base, UTCDateTime


class Connector(Base):
    __tablename__ = "connectors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(
        String(128), nullable=False, server_default=text("('')")
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    launch: Mapped[dict] = mapped_column(JSON, nullable=False)
    secrets: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )
    cached_tools: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    cached_python_callables: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    source_repo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_repo_revision: Mapped[str | None] = mapped_column(String(128), nullable=True)
    grounding_paths: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    openapi_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cached_repo_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    cached_openapi: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    grounding_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="none", server_default="none"
    )
    grounding_fetched_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True, onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_connectors_provider_id", "provider_id"),
        Index("ix_connectors_category", "category"),
        Index("ix_connectors_status", "status"),
        CheckConstraint(
            "source IN ('built_in', 'remote_mcp', 'cli_mcp', 'python_lib', 'skill')",
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
        CheckConstraint(
            "grounding_status IN ('none', 'pending', 'ready', 'failed')",
            name="grounding_status",
        ),
    )


class RunnerCallableSpec(Base):
    """Per-department, per-need callable resolution (§3.5).

    The wizard-time adapter LLM populates these rows when a department's
    needs.yaml is resolved against a connector. The deterministic runtime
    runner reads them at execution time.
    """

    __tablename__ = "runner_callable_specs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    department_id: Mapped[str] = mapped_column(String(64), nullable=False)
    need_id: Mapped[str] = mapped_column(String(64), nullable=False)
    connector_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("connectors.id", ondelete="CASCADE"),
        nullable=False,
    )
    access_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    spec: Mapped[dict] = mapped_column(JSON, nullable=False)
    canary_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    canary_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True, onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("department_id", "need_id", name="uq_dept_need"),
        Index("ix_rcs_department_id", "department_id"),
        Index("ix_rcs_connector_id", "connector_id"),
        CheckConstraint(
            "access_mode IN ('cli_mcp', 'remote_mcp', 'python_lib')",
            name="access_mode",
        ),
    )
