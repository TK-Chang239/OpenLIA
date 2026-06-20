"""Macro Research department — dashboard-only (no chat)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import ClassVar, Protocol

from openlia.connectors.types import Category
from openlia.macro_research.dashboards import DASHBOARDS
from openlia.macro_research.schemas import MRSnapshot, SnapshotEntry


class _SnapshotReader(Protocol):
    def latest_snapshot(self, *, user_id: str, dashboard: str) -> SnapshotEntry | None: ...


class MacroResearchDepartment:
    """Public department surface. Read-only snapshot for cross-department consumers."""

    name: str = "macro_research"
    slug: str = "macro_research"
    display_name: str = "Macro Research"
    is_dashboard: bool = True
    has_chat: bool = False

    # Connector dependencies (spec §9). The macro dashboard engine
    # (report_dash_mr) runs on the model's native web search, so no connector
    # category is required. WEB_SEARCH (a scraping connector such as Firecrawl),
    # FINANCIAL (live quotes + whatever indicators it exposes), and NEWS are all
    # optional: any value a connector does not cover falls back to native
    # web_search. MR is dashboard-routed (report_dash_mr via the connector
    # dispatcher), NOT a runner department.
    required_categories: ClassVar[tuple[Category, ...]] = ()
    optional_categories: ClassVar[tuple[Category, ...]] = (
        Category.FINANCIAL,
        Category.NEWS,
        Category.WEB_SEARCH,
    )
    required_any_of: ClassVar[tuple[tuple[Category, ...], ...]] = ()

    # Runtime behavior: dashboard engine.
    disable_runtime_routing: ClassVar[bool] = False

    valid_modes: tuple[str, ...] = ()
    extra_tools: tuple[str, ...] = ()

    _SNAPSHOT_TTL = timedelta(hours=24)

    def __init__(self, snapshot_reader: _SnapshotReader | None = None) -> None:
        self._reader = snapshot_reader

    def set_snapshot_reader(self, reader: _SnapshotReader) -> None:
        """Inject the snapshot reader post-construction. The server wires the
        DB-backed reader at startup."""
        self._reader = reader

    def dashboard_slugs(self) -> tuple[str, ...]:
        return tuple(DASHBOARDS.keys())

    def get_current_snapshot(self, user_id: str) -> MRSnapshot:
        """Read-only cross-department view assembled from the cached dashboard
        payloads. Never fetches, never calls LLMs."""
        if self._reader is None:
            return MRSnapshot()
        dc = self._reader.latest_snapshot(user_id=user_id, dashboard="debt_cycle")
        fs = self._reader.latest_snapshot(user_id=user_id, dashboard="four_seasons")
        ff = self._reader.latest_snapshot(user_id=user_id, dashboard="five_forces")
        entries = [e for e in (dc, fs, ff) if e is not None]
        generated_at = min((e.generated_at for e in entries), default=None)
        now = datetime.now(UTC)
        is_stale = any((now - e.generated_at) > self._SNAPSHOT_TTL for e in entries)
        return MRSnapshot(
            debt_cycle_phase=dc.value if dc else None,
            economic_season=fs.value if fs else None,
            active_force_count=ff.value if ff else None,
            generated_at=generated_at,
            is_stale=is_stale,
        )
