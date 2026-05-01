"""Macro Research department — dashboard-only (no chat)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar, Protocol

from openlia.connectors.types import Category
from openlia.macro_research.dashboards import DASHBOARDS
from openlia.macro_research.schemas import MRSnapshot


class _SnapshotReader(Protocol):
    def latest_state(self, *, user_id: str, dashboard: str) -> dict[str, Any] | None: ...
    def latest_assessment(
        self, *, user_id: str, dashboard: str, assessment_type: str
    ) -> dict[str, Any] | None: ...


class MacroResearchDepartment:
    """Public department surface. Read-only snapshot for cross-department consumers."""

    name: str = "macro_research"
    slug: str = "macro_research"
    display_name: str = "Macro Research"
    is_dashboard: bool = True
    has_chat: bool = False

    # Connector dependencies (spec §10.1).
    required_categories: ClassVar[tuple[Category, ...]] = (Category.FINANCIAL,)
    optional_categories: ClassVar[tuple[Category, ...]] = (Category.NEWS,)

    # Runtime behavior (spec §5.2).
    requires_runner: ClassVar[bool] = True
    disable_runtime_routing: ClassVar[bool] = False

    valid_modes: tuple[str, ...] = ()
    extra_tools: tuple[str, ...] = ()

    def __init__(self, snapshot_reader: _SnapshotReader | None = None) -> None:
        self._reader = snapshot_reader

    def dashboard_slugs(self) -> tuple[str, ...]:
        return tuple(DASHBOARDS.keys())

    def get_current_snapshot(self, user_id: str) -> MRSnapshot:
        """Read-only: indexed DB reads. Never fetches, never calls LLMs."""
        if self._reader is None:
            return MRSnapshot()

        t1 = self._reader.latest_state(user_id=user_id, dashboard="debt_cycle")
        t2 = self._reader.latest_state(user_id=user_id, dashboard="four_seasons")
        t5 = self._reader.latest_assessment(
            user_id=user_id, dashboard="five_forces", assessment_type="synthesis"
        )

        debt_cycle_phase = (t1 or {}).get("phase")
        economic_season = (t2 or {}).get("season")
        active_force_count = (t5 or {}).get("active_force_count")

        generated = [x.get("generated_at") for x in (t1, t2, t5) if x and x.get("generated_at")]
        generated_at = min(generated) if generated else None

        is_stale = False
        now = datetime.now(UTC)
        if t1 and t1.get("generated_at") and (now - t1["generated_at"]) > timedelta(hours=24):
            is_stale = True
        if t2 and t2.get("generated_at") and (now - t2["generated_at"]) > timedelta(hours=24):
            is_stale = True
        if t5 and t5.get("generated_at"):
            schedule = (t5.get("schedule") or "quarterly").lower()
            max_age = timedelta(days=95) if schedule == "quarterly" else timedelta(days=8)
            if (now - t5["generated_at"]) > max_age:
                is_stale = True

        return MRSnapshot(
            debt_cycle_phase=debt_cycle_phase,
            economic_season=economic_season,
            active_force_count=active_force_count,
            generated_at=generated_at,
            is_stale=is_stale,
        )
