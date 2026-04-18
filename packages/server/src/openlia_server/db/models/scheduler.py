"""Scheduler and notification tables.

Rows:
  mb_schedules, eu_schedules — per-user cron schedules.
  job_runs — append-only history of every scheduled execution.
  user_notifications — lightweight notification queue.

FK notes:
  - All user_id FKs cascade on user delete.
  - job_runs.retry_of → job_runs.id, SET NULL.
  - user_notifications.job_run_id → job_runs.id, SET NULL.
  - job_runs.schedule_id is a soft-polymorphic pointer (no FK constraint).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base


class MbSchedule(Base):
    """Per-user Morning Briefing cron schedule."""

    __tablename__ = "mb_schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    time: Mapped[str] = mapped_column(String(5), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    days_of_week: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_mb_schedules_user", "user_id"),)


class EuSchedule(Base):
    """Per-user Earnings Update scan schedule. Identical shape to MbSchedule."""

    __tablename__ = "eu_schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    time: Mapped[str] = mapped_column(String(5), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    days_of_week: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_eu_schedules_user", "user_id"),)


class JobRun(Base):
    """Append-only execution history for every scheduled background job."""

    __tablename__ = "job_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # Soft-polymorphic pointer: mb_schedules.id or eu_schedules.id depending
    # on job_type. No FK constraint — service layer enforces the invariant.
    schedule_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_of: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("job_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        Index(
            "ix_job_runs_user_type_started",
            "user_id",
            "job_type",
            "started_at",
        ),
        Index("ix_job_runs_status", "status"),
        Index("ix_job_runs_schedule", "schedule_id", "started_at"),
    )


class UserNotification(Base):
    """Lightweight notification record for background job results."""

    __tablename__ = "user_notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    department: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    job_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("job_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_notifications_user_unread", "user_id", "read_at"),)
