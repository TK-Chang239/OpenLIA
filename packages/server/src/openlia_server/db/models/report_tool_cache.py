"""Per-(user, department) report tool cache.

Tracks which connector tools each user/department pair has actually
used in recent report runs so the next run only exposes that subset to
the LLM. See `services/report_tool_cache.py` for the policy.

Two tables:

- `report_tool_warmup` — one row per (user, department). Tracks how
  many runs have completed during the "warm-up" window (first 3 runs
  per (user, dept) get the full connector surface so we can learn
  what the LLM actually picks).

- `report_tool_usage` — append-only log of tool calls. One row per
  (run_id, tool_name) tuple per (user, department). `success=True` if
  the tool returned without raising. The cache policy reads this log
  to compute promotion / demotion lazily at run start.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import (
    Boolean,
    Date,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base, TimestampMixin


class ReportToolWarmup(Base, TimestampMixin):
    """Counts warm-up runs per (user, department). PK on (user_id, department_id)."""

    __tablename__ = "report_tool_warmup"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    department_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    runs_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ReportToolUsage(Base, TimestampMixin):
    """Append-only tool-call log used by the cache policy.

    `run_id` is the report run that called the tool. `run_date` is the
    UTC calendar date of the run; the cache policy treats a "day" as a
    distinct run_date among the user's most recent reports.
    """

    __tablename__ = "report_tool_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    department_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)

    __table_args__ = (
        Index(
            "ix_report_tool_usage_lookup",
            "user_id",
            "department_id",
            "tool_name",
            "run_date",
        ),
    )
