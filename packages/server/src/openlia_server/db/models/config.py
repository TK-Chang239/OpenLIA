"""Plan 1a configuration tables: llm_providers, llm_models,
user_llm_preferences, data_providers, data_provider_requirement_mapping,
web_search_providers, plus Plan 11's user_prefs. Spec reference:
`database-design.md` §4 and §7 (user_prefs).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from openlia_server.db.base import Base, TimestampMixin


class LLMProvider(Base, TimestampMixin):
    __tablename__ = "llm_providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    env_var_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    extra_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        Index("ix_llm_providers_kind", "kind"),
        Index("ix_llm_providers_is_enabled", "is_enabled"),
    )


class LLMModel(Base, TimestampMixin):
    __tablename__ = "llm_models"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("llm_providers.id", ondelete="RESTRICT"), nullable=False
    )
    model_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    overrides: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    provider: Mapped[LLMProvider] = relationship("LLMProvider")

    __table_args__ = (
        Index("ix_llm_models_provider_id", "provider_id"),
    )


class LLMSlotDefault(Base):
    """Admin-assigned model per (slot_kind, slot_id) pair.

    slot_kind is 'department' (e.g. 'secretary', 'equity_research') or
    'system_role' (e.g. 'ai_review', 'graph_extraction'). Replaces the
    per-tier default model mechanism.
    """

    __tablename__ = "llm_slot_defaults"

    slot_kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    slot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("llm_models.id", ondelete="CASCADE"),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "slot_kind IN ('department','system_role')",
            name="ck_llm_slot_defaults_slot_kind",
        ),
        Index("ix_llm_slot_defaults_model_id", "model_id"),
    )


class UserPrefs(Base):
    __tablename__ = "user_prefs"
    __table_args__ = (
        CheckConstraint("theme IN ('system','light','dark')", name="ck_user_prefs_theme"),
        CheckConstraint(
            "display_language IN ('en','zh-TW') "
            "AND response_language IN ('en','zh-TW') "
            "AND report_language IN ('en','zh-TW','both')",
            name="ck_user_prefs_language",
        ),
        CheckConstraint(
            "timezone_source IN ('auto','manual')",
            name="ck_user_prefs_timezone_source",
        ),
        CheckConstraint(
            "portfolio_refresh_cadence IN ('15min','hourly','daily','weekly','manual')",
            name="ck_user_prefs_portfolio_cadence",
        ),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    theme: Mapped[str] = mapped_column(
        String(16), nullable=False, default="system", server_default="system"
    )
    notify_inapp: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1")
    )
    notify_email: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0")
    )
    display_language: Mapped[str] = mapped_column(
        String(8), nullable=False, default="en", server_default="en"
    )
    response_language: Mapped[str] = mapped_column(
        String(8), nullable=False, default="en", server_default="en"
    )
    report_language: Mapped[str] = mapped_column(
        String(8), nullable=False, default="en", server_default="en"
    )
    preferred_model_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("llm_models.id", ondelete="SET NULL"), nullable=True
    )
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="UTC", server_default="UTC"
    )
    timezone_source: Mapped[str] = mapped_column(
        String(8), nullable=False, default="auto", server_default="auto"
    )
    graph_extraction_time: Mapped[str] = mapped_column(
        String(5), nullable=False, default="03:00", server_default="03:00"
    )
    portfolio_refresh_cadence: Mapped[str] = mapped_column(
        String(16), nullable=False, default="daily", server_default="daily"
    )
    portfolio_display_currency: Mapped[str] = mapped_column(
        String(8), nullable=False, default="USD", server_default="USD"
    )


class UserDepartmentModelPref(Base, TimestampMixin):
    """Per-(user, department) model override.

    Wins over the user-level ``preferred_model_id`` and tier defaults
    in the resolver. Absence of a row falls back to the prior chain.
    """

    __tablename__ = "user_department_model_prefs"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    department_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("llm_models.id", ondelete="CASCADE"), nullable=False
    )


class WebSearchProvider(Base, TimestampMixin):
    __tablename__ = "web_search_providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    env_var_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    __table_args__ = (
        Index("ix_web_search_providers_is_enabled_priority", "is_enabled", "priority"),
    )
