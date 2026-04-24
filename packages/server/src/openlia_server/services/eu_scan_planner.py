"""EUScanPlanner — reads watchlist + user config, asks the earnings adapter
for companies with new releases since `since`, and returns EUScanTargets.

Fulfills the Plan 6 `EUScanPlanner` Protocol. Wired at app startup into
`build_scheduler_service(eu_planner=...)`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from openlia.llm.runtime.messages import ReportRequest
from sqlalchemy.orm import Session

from openlia_server.db.models.departments import EuWatchlistEntry
from openlia_server.scheduler.payloads import EUScanTarget
from openlia_server.services import eu_config as eu_config_svc

_LENGTH_MAP = {"concise": "brief", "normal": "standard", "elaborative": "long"}


class EarningsRecentReleaseAdapter(Protocol):
    def latest_release(self, ticker: str, *, since: datetime | None) -> datetime | None:
        """Return the datetime of the latest earnings release for ticker if one
        happened after `since`; otherwise None."""
        ...


@dataclass
class EuScanPlannerImpl:
    adapter: EarningsRecentReleaseAdapter

    def plan(
        self,
        *,
        session: Session,
        user_id: str,
        schedule_id: str,
        since: datetime | None,
    ) -> list[EUScanTarget]:
        entries = (
            session.query(EuWatchlistEntry)
            .filter_by(user_id=user_id)
            .order_by(EuWatchlistEntry.ticker.asc())
            .all()
        )
        if not entries:
            return []

        cfg = eu_config_svc.get_config(session, user_id=user_id)

        targets: list[EUScanTarget] = []
        for row in entries:
            released_at = self.adapter.latest_release(row.ticker, since=since)
            if released_at is None:
                continue
            if since is not None and released_at < since:
                continue
            request = ReportRequest(
                mode="earnings_analysis",
                user_input=(
                    f"Analyze {row.ticker} ({row.company_name}) "
                    f"earnings released at {released_at.isoformat()}."
                ),
                enabled_sections=list(cfg.enabled_section_ids),
                custom_sections=list(cfg.custom_sections),
                length=_LENGTH_MAP.get(cfg.report_length, "standard"),
            )
            targets.append(EUScanTarget(ticker=row.ticker, request=request))
        return targets
