"""MBRequestBuilder implementation — fulfills the Plan 6 Protocol.

Reads the user's MB config + (optional) portfolio holdings and composes
the ReportRequest. The scheduler's `MBBriefingExecutor` passes this
through to `ReportRunner`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from openlia.llm.runtime.messages import ReportRequest
from sqlalchemy.orm import Session

from openlia_server.db.models.content import PortfolioHolding
from openlia_server.services import mb_config as mb_config_svc

_LENGTH_MAP = {"concise": "brief", "normal": "standard", "elaborative": "long"}


def _portfolio_for_user(session: Session, *, user_id: str) -> list[dict]:
    rows = (
        session.query(PortfolioHolding)
        .filter_by(user_id=user_id)
        .order_by(PortfolioHolding.ticker.asc())
        .all()
    )
    return [{"ticker": r.ticker, "name": r.name} for r in rows]


@dataclass
class MbRequestBuilderImpl:
    """Implements `MBRequestBuilder` from `scheduler.payloads`."""

    def build(
        self,
        *,
        session: Session,
        user_id: str,
        schedule_id: str,
    ) -> ReportRequest:
        cfg = mb_config_svc.get_config(session, user_id=user_id)

        reference_portfolio: list[dict] | None = None
        if cfg.reference_portfolio:
            holdings = _portfolio_for_user(session, user_id=user_id)
            if holdings:
                reference_portfolio = holdings

        # The prompt consumes enabled_sections, section_topics, custom_sections,
        # and reference_portfolio directly. Plan 5's ReportRequest carries:
        #   mode, user_input, enabled_sections, custom_sections, length
        # Section topics and reference_portfolio ride inside `user_input` as
        # a JSON block the template can parse (no retroactive extension of
        # ReportRequest). Ancillary fields are serialized deterministically
        # so the prompt render matches regardless of dict ordering.
        extras = {
            "section_topics": cfg.section_topics,
            "reference_portfolio": reference_portfolio,
        }
        user_input = (
            "Generate today's Morning Briefing using the user's coverage list "
            "and configured topics.\n\n"
            "MB_EXTRAS_JSON:\n" + json.dumps(extras, sort_keys=True)
        )

        return ReportRequest(
            mode="morning_briefing",
            user_input=user_input,
            enabled_sections=list(cfg.enabled_section_ids),
            custom_sections=list(cfg.custom_sections),
            length=_LENGTH_MAP.get(cfg.report_length, "standard"),
        )
