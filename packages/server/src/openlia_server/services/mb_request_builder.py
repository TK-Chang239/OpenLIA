"""MBRequestBuilder implementation — fulfills the Plan 6 Protocol.

Reads the user's MB config + (optional) portfolio holdings and composes
the ReportRequest. The scheduler's `MBBriefingExecutor` passes this
through to `ReportRunner`.
"""

from __future__ import annotations

from dataclasses import dataclass

from openlia.llm.runtime.messages import ReportRequest
from sqlalchemy.orm import Session

from openlia_server.services import mb_config as mb_config_svc
from openlia_server.services.portfolio import get_reference_holdings

_LENGTH_MAP = {"concise": "brief", "normal": "standard", "elaborative": "long"}


def _portfolio_for_user(session: Session, *, user_id: str) -> list[dict]:
    """Fetch the user's reference portfolio via the Plan 21 helper.

    The MB prompt only needs `ticker` + `name`; the Portfolio helper returns
    a richer dict but we project down here to keep the prompt contract stable.
    """
    refs = get_reference_holdings(session, user_id=user_id)
    return [{"ticker": r["ticker"], "name": r["name"]} for r in refs]


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

        user_input = (
            "Generate today's Morning Briefing using the user's coverage list "
            "and configured topics."
        )

        return ReportRequest(
            mode="morning_briefing",
            user_input=user_input,
            enabled_sections=list(cfg.enabled_section_ids),
            custom_sections=list(cfg.custom_sections),
            length=_LENGTH_MAP.get(cfg.report_length, "standard"),
            section_topics=dict(cfg.section_topics) if cfg.section_topics else None,
            reference_portfolio=reference_portfolio,
        )
