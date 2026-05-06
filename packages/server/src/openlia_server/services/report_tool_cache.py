"""Per-(user, department) report tool cache.

Policy summary (locked design 2026-05-05):

- **Warm-up**: the first 3 runs per (user, department) expose the full
  connector tool surface to the LLM so the cache can observe what the
  model actually picks. Warm-up runs are counted by `note_run_started`
  regardless of outcome.

- **Steady state**: a tool is in the cache for the next run iff it was
  called *successfully* on at least 3 distinct *report-run-days* among
  the user's most recent 5 distinct report-run-days. A "day" is a
  distinct `run_date` value among that user's runs for this department.
  Repeated calls in a single run dedupe to one day-use.

- **Empty cache**: when no tool meets the threshold, `tools_for`
  returns an empty list. The caller is responsible for adding the
  escalation tool (`request_additional_tools`) so the LLM can still
  discover what it needs.

Promotion and demotion are computed lazily at read time — there are
no cron sweeps or denormalized "is_cached" flags to drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from openlia.llm.types import ToolSchema
from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.report_tool_cache import (
    ReportToolUsage,
    ReportToolWarmup,
)

WARMUP_RUN_QUOTA = 3
ROLLING_WINDOW_DAYS = 5
PROMOTION_DAY_COUNT = 3


@dataclass(frozen=True)
class ReportToolCache:
    """Reads and writes the per-(user, department) usage tables."""

    session: Session

    def note_run_started(
        self,
        *,
        user_id: str,
        department_id: str,
        run_id: str,
        run_date: date,
    ) -> None:
        """Record that a report run started. Bumps the warm-up counter
        until the quota is reached, after which it stays pinned."""
        row = self.session.get(ReportToolWarmup, (user_id, department_id))
        if row is None:
            row = ReportToolWarmup(
                user_id=user_id,
                department_id=department_id,
                runs_completed=1,
            )
            self.session.add(row)
        else:
            row.runs_completed = row.runs_completed + 1
        self.session.flush()

    def record_tool_call(
        self,
        *,
        user_id: str,
        department_id: str,
        run_id: str,
        run_date: date,
        tool_name: str,
        success: bool,
    ) -> None:
        """Append a tool-call usage row. The cache reads these rows to
        compute promotion / demotion at next `tools_for` call."""
        self.session.add(
            ReportToolUsage(
                user_id=user_id,
                department_id=department_id,
                tool_name=tool_name,
                run_id=run_id,
                run_date=run_date,
                success=success,
            )
        )
        self.session.flush()

    def tools_for(
        self,
        *,
        user_id: str,
        department_id: str,
        full_inventory: list[ToolSchema],
    ) -> list[ToolSchema]:
        """Return the tool list for the next run.

        During warm-up: full inventory. After warm-up: filtered subset
        per the promotion rule. Pure read — no mutation.
        """
        warmup = self.session.get(ReportToolWarmup, (user_id, department_id))
        warmup_runs = warmup.runs_completed if warmup is not None else 0
        if warmup_runs <= WARMUP_RUN_QUOTA:
            return list(full_inventory)

        recent_days = self._recent_run_days(user_id, department_id)
        if not recent_days:
            return []
        promoted = self._promoted_tools(user_id, department_id, recent_days)
        return [tool for tool in full_inventory if tool.name in promoted]

    def _recent_run_days(self, user_id: str, department_id: str) -> set[date]:
        """The most recent N distinct report-run-days for this user/dept."""
        stmt = (
            select(ReportToolUsage.run_date)
            .where(
                ReportToolUsage.user_id == user_id,
                ReportToolUsage.department_id == department_id,
            )
            .group_by(ReportToolUsage.run_date)
            .order_by(ReportToolUsage.run_date.desc())
            .limit(ROLLING_WINDOW_DAYS)
        )
        return {row for (row,) in self.session.execute(stmt).all()}

    def _promoted_tools(
        self,
        user_id: str,
        department_id: str,
        recent_days: set[date],
    ) -> set[str]:
        """Tools called successfully on ≥ PROMOTION_DAY_COUNT distinct
        days within `recent_days`. Per-run dedupe is handled by the
        DISTINCT on (tool_name, run_date)."""
        stmt = (
            select(ReportToolUsage.tool_name, ReportToolUsage.run_date)
            .where(
                ReportToolUsage.user_id == user_id,
                ReportToolUsage.department_id == department_id,
                ReportToolUsage.success.is_(True),
                ReportToolUsage.run_date.in_(recent_days),
            )
            .distinct()
        )
        day_count: dict[str, int] = {}
        for tool_name, _run_date in self.session.execute(stmt).all():
            day_count[tool_name] = day_count.get(tool_name, 0) + 1
        return {name for name, count in day_count.items() if count >= PROMOTION_DAY_COUNT}


__all__ = [
    "PROMOTION_DAY_COUNT",
    "ROLLING_WINDOW_DAYS",
    "WARMUP_RUN_QUOTA",
    "ReportToolCache",
]
