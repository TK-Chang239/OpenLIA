"""MR runner — T1-T3 live + T4 cache + T5 overlay."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from openlia.macro_research.assembler import DashboardAssembler
from openlia.macro_research.dashboards import DASHBOARDS
from openlia.macro_research.schemas import DashboardResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


class _DataProvider(Protocol):
    def fetch(self, *, requirement: str, **kwargs: Any) -> Any: ...


class _CacheStore(Protocol):
    def read_latest(
        self, *, session: Session, user_id: str, dashboard: str, assessment_type: str
    ) -> dict[str, Any] | None: ...


class MRRunner:
    def __init__(
        self,
        *,
        data_provider: _DataProvider | None = None,
        cache_store: _CacheStore,
        dashboard_service: Any,
        session_factory: Callable[[], Session],
        dispatcher: Any | None = None,
    ) -> None:
        self._data = data_provider
        self._cache = cache_store
        self._dashboard = dashboard_service
        self._factory = session_factory
        self._asm = DashboardAssembler(data_provider=data_provider, dispatcher=dispatcher)

    async def run(
        self,
        *,
        user_id: str,
        dashboard_slug: str,
        portfolio: dict[str, float] | None,
        smart_mode: bool,
    ) -> DashboardResult:
        if dashboard_slug not in DASHBOARDS:
            raise KeyError(f"unknown dashboard: {dashboard_slug!r}")
        # Touch per-user state row (ensures existence; also exposes thresholds).
        # Only swallow IntegrityError for the racy unique-constraint case
        # (concurrent first-touch); every other failure is a programming bug
        # and must propagate so callers see the real cause.
        try:
            self._dashboard.get_or_create(user_id=user_id, dashboard=dashboard_slug)
        except IntegrityError:
            pass

        t4_cached: dict[str, Any] | None = None
        dashboard = DASHBOARDS[dashboard_slug]
        if dashboard.T4_PROMPT_KEY is not None:
            with self._factory() as session:
                t4_cached = self._cache.read_latest(
                    session=session,
                    user_id=user_id,
                    dashboard=dashboard_slug,
                    assessment_type="synthesis",
                )
        return await self._asm.run(
            dashboard_slug=dashboard_slug,
            user_id=user_id,
            portfolio=portfolio,
            t4_cached=t4_cached,
            smart_mode=smart_mode,
        )
