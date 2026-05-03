"""ORM models for Lia safety & compliance guardrails."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base


class LiaGuardrailEvent(Base):
    __tablename__ = "lia_guardrail_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('persona_refusal', 'tripwire_flag')",
            name="ck_lia_guardrail_events_event_type",
        ),
        CheckConstraint(
            "action_taken IN ('replaced', 'warned', 'logged')",
            name="ck_lia_guardrail_events_action_taken",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    session_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    department_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action_taken: Mapped[str] = mapped_column(String(16), nullable=False)
    user_input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    tripwire_pattern: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)


class UserDisclaimerAcceptance(Base):
    __tablename__ = "user_disclaimer_acceptance"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    disclaimer_version: Mapped[str] = mapped_column(String(32), primary_key=True)
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
