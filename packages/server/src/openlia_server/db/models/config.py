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
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from openlia_server.db.base import Base, TimestampMixin, UTCDateTime


class LLMProvider(Base, TimestampMixin):
    __tablename__ = "llm_providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    tier: Mapped[str] = mapped_column(String(16), nullable=False)
    model_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_tier_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    overrides: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    provider: Mapped[LLMProvider] = relationship("LLMProvider")

    __table_args__ = (
        Index("ix_llm_models_tier_is_enabled", "tier", "is_enabled"),
        Index("ix_llm_models_provider_id", "provider_id"),
        Index(
            "uq_llm_models_tier_default",
            "tier",
            unique=True,
            sqlite_where=text("is_tier_default = 1"),
            postgresql_where=text("is_tier_default"),
        ),
        CheckConstraint(
            "tier IN ('thinking', 'everyday', 'quick')",
            name="tier_enum",
        ),
    )


class UserLLMPreference(Base):
    __tablename__ = "user_llm_preferences"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    tier: Mapped[str] = mapped_column(String(16), primary_key=True)
    model_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("llm_models.id", ondelete="CASCADE"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "tier IN ('thinking', 'everyday', 'quick')",
            name="tier_enum",
        ),
    )


class DataProvider(Base, TimestampMixin):
    __tablename__ = "data_providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(
        String(16), nullable=False, default="financial", server_default="financial"
    )
    mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="api_key", server_default="api_key"
    )
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    env_var_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mcp_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mcp_auth_header: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        Index("ix_data_providers_kind", "kind"),
        Index("ix_data_providers_is_enabled", "is_enabled"),
        Index("ix_data_providers_category", "category"),
        CheckConstraint(
            "category IN ('financial', 'news', 'social_media', 'search')",
            name="ck_data_providers_category",
        ),
        CheckConstraint(
            "mode IN ('api_key', 'mcp')",
            name="ck_data_providers_mode",
        ),
    )


class DataProviderRequirementMapping(Base):
    __tablename__ = "data_provider_requirement_mapping"

    requirement_type: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("data_providers.id", ondelete="CASCADE"), primary_key=True
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
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


class WebSearchProvider(Base, TimestampMixin):
    __tablename__ = "web_search_providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    env_var_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    __table_args__ = (
        Index("ix_web_search_providers_is_enabled_priority", "is_enabled", "priority"),
    )
