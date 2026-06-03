"""Dashboard and formula-engine tables from database-design.md § 7.

Rows:
  pt_user_configs, pt_presets — Panic Thermometer.
  mr_dashboard_state, mr_dashboard_cache — Macro Research Dalio dashboards.
  rs_user_config, rs_snapshots — Retail Sentiment.
  fe_saved_formulas — shared formula-engine DSL rows.

Notes:
  - pt_presets.user_id is nullable: NULL rows are shipped library presets.
  - pt_user_configs.active_preset_id uses SET NULL so deleting a preset
    demotes the active config to "custom unsaved."
  - rs_snapshots is also global — one row per ticker per refresh cycle.
  - fe_saved_formulas.expression is stored as Text; Plan 17 (formula engine)
    validates the DSL at the service layer on write.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base, TimestampMixin, UTCDateTime

# ---------- Panic Thermometer ----------


class PtUserConfig(Base, TimestampMixin):
    """Per-user PT dashboard configuration. Replaces window.storage."""

    __tablename__ = "pt_user_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    active_preset_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("pt_presets.id", ondelete="SET NULL"),
        nullable=True,
    )
    panel_config: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list, server_default=text("'[]'")
    )
    composite_settings: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )


class PtTriggerEvent(Base, TimestampMixin):
    """Composite-level transition log. One row per panic-level change.

    Used by `pt_runner.compute_dashboard` to detect transitions and emit
    user_notifications. `payload_json` carries the full composite snapshot
    (panel statuses, score, mode) at the time of the change.
    """

    __tablename__ = "pt_trigger_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    level_from: Mapped[str | None] = mapped_column(String(16), nullable=True)
    level_to: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )

    __table_args__ = (
        Index(
            "ix_pt_trigger_events_user_occurred",
            "user_id",
            "occurred_at",
        ),
    )


class PtPreset(Base, TimestampMixin):
    """Named configuration snapshots. Shipped library presets + user-created."""

    __tablename__ = "pt_presets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_shipped: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0")
    )
    panel_config: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list, server_default=text("'[]'")
    )
    composite_settings: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_pt_presets_user_name"),
        # Partial unique over shipped rows: SQLAlchemy lets us declare this as
        # an Index with `unique=True` + `sqlite_where=` (the migration uses the
        # same trick). Declaring here so create_all() mirrors the migration.
        Index(
            "uq_pt_presets_shipped_name",
            "name",
            unique=True,
            sqlite_where=text("user_id IS NULL"),
        ),
    )


# ---------- Macro Research ----------


class MrDashboardState(Base):
    """Per-user state for Dalio dashboards. One row per user per dashboard."""

    __tablename__ = "mr_dashboard_state"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    dashboard: Mapped[str] = mapped_column(String(32), nullable=False)
    view_config: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )
    threshold_overrides: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )
    assessment_schedule: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_assessment_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("user_id", "dashboard", name="uq_mr_dashboard_user_dashboard"),
    )


class MrDashboardCache(Base):
    """Latest dashboard payload per (user, dashboard). The report_dash_mr
    engine writes here on each scheduled/refresh run; the route reads it."""

    __tablename__ = "mr_dashboard_cache"

    id: Mapped[int] = mapped_column(Integer, autoincrement=True, nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    dashboard: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    provenance: Mapped[str] = mapped_column(String(16), nullable=False, default="live")
    model_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_mr_dashboard_cache"),
        UniqueConstraint("user_id", "dashboard", name="uq_mr_dashboard_cache_user_dashboard"),
        Index("ix_mr_dashboard_cache_user_dashboard", "user_id", "dashboard"),
    )


# ---------- Retail Sentiment ----------


class RsUserConfig(Base):
    """Per-user Retail Sentiment dashboard configuration."""

    __tablename__ = "rs_user_config"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    active_tab: Mapped[str] = mapped_column(String(32), nullable=False, default="overview")
    metric_settings: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )
    filter_presets: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list, server_default=text("'[]'")
    )
    refresh_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class RsSnapshot(Base):
    """Point-in-time sentiment metric snapshots. Global, per ticker per cycle."""

    __tablename__ = "rs_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    snapshot_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    source_breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    __table_args__ = (
        Index(
            "ix_rs_snapshots_ticker_captured",
            "ticker",
            text("captured_at DESC"),
        ),
    )


class RsClassificationLog(Base):
    """One row per LLM classification batch call. Global, no user_id:
    classifications are produced per ticker and shared across users via
    `rs_snapshots`, so the audit trail follows the same shape."""

    __tablename__ = "rs_classification_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(36), nullable=False)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    model_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    completion_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    latency_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_rs_classification_log_ticker_created",
            "ticker",
            "created_at",
        ),
        Index(
            "ix_rs_classification_log_batch",
            "batch_id",
        ),
    )


# ---------- Formula engine ----------


class FeSavedFormula(Base, TimestampMixin):
    """User-created formulas for PT custom panels and MR T1/T2 overrides."""

    __tablename__ = "fe_saved_formulas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    expression: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    department_scope: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_fe_formulas_user_name"),)
