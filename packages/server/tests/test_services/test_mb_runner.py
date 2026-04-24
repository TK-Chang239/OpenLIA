from __future__ import annotations

import pytest
from openlia.llm.runtime.events import ReportComplete, ReportStart
from openlia_server.db.models.auth import User
from openlia_server.db.models.departments import MbUserConfig
from openlia_server.services.mb_runner import ReportSavedEvent, run_on_demand
from sqlalchemy.orm import Session

MINIMAL_SCHEMA = {
    "schema_version": "1.0",
    "department": "morning_briefing",
    "generated_at": "2026-04-23T00:00:00Z",
    "cover": {"title": "Morning Briefing 2026-04-23", "subtitle": "", "tagline": ""},
    "sections": [],
}


def _mk_user(db: Session, user_id: str = "u_1") -> User:
    u = User(
        id=user_id,
        email=f"{user_id}@x",
        display_name=user_id,
        password_hash="x",
        is_admin=False,
    )
    db.add(u)
    db.commit()
    return u


@pytest.mark.asyncio
async def test_on_demand_forwards_events_and_persists(
    create_tables, db_session, fake_report_runner
) -> None:
    _mk_user(db_session)
    fake_report_runner.queue_events(
        [
            ReportStart(
                report_id="pending_r",
                department="morning_briefing",
                mode="morning_briefing",
                section_titles=["Executive Summary"],
            ),
            ReportComplete(report_id="pending_r", schema=MINIMAL_SCHEMA),
        ]
    )
    collected = []
    async for ev in run_on_demand(
        session=db_session, user_id="u_1", report_runner=fake_report_runner
    ):
        collected.append(ev)

    kinds = [type(e).__name__ for e in collected]
    assert kinds == ["ReportStart", "ReportComplete", "ReportSavedEvent"]
    assert isinstance(collected[-1], ReportSavedEvent)
    assert collected[-1].report_id

    last = fake_report_runner.last_request
    assert last.mode == "morning_briefing"


@pytest.mark.asyncio
async def test_on_demand_reads_config(
    create_tables, db_session, fake_report_runner
) -> None:
    _mk_user(db_session)
    db_session.add(
        MbUserConfig(
            id="c1",
            user_id="u_1",
            report_length="elaborative",
            enabled_section_ids=["executive_summary"],
            section_topics={},
            custom_sections=[],
            reference_portfolio=False,
        )
    )
    db_session.commit()
    fake_report_runner.queue_events(
        [ReportComplete(report_id="pending", schema=MINIMAL_SCHEMA)]
    )
    async for _ in run_on_demand(
        session=db_session, user_id="u_1", report_runner=fake_report_runner
    ):
        pass
    req = fake_report_runner.last_request
    assert req.length == "long"
    assert req.enabled_sections == ["executive_summary"]


@pytest.mark.asyncio
async def test_on_demand_no_persist_when_no_complete(
    create_tables, db_session, fake_report_runner
) -> None:
    _mk_user(db_session)
    fake_report_runner.queue_events(
        [
            ReportStart(
                report_id="pending_r",
                department="morning_briefing",
                mode="morning_briefing",
                section_titles=[],
            ),
        ]
    )
    collected = []
    async for ev in run_on_demand(
        session=db_session, user_id="u_1", report_runner=fake_report_runner
    ):
        collected.append(ev)
    saved = [e for e in collected if isinstance(e, ReportSavedEvent)]
    assert saved == []
