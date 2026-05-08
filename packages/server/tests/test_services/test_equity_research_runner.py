from __future__ import annotations

import pytest
from openlia.llm.runtime.events import ReportComplete, ReportStart
from openlia_server.db.models.auth import User
from openlia_server.services.equity_research_runner import (
    EquityResearchRunner,
    ReportSavedEvent,
)

MINIMAL_SCHEMA = {
    "schema_version": "2.0",
    "department": "equity_research",
    "generated_at": "2026-04-23T00:00:00Z",
    "cover": {
        "title": "AAPL Update",
        "subtitle": "",
        "tagline": "",
    },
    "sections": [],
}


@pytest.fixture
def user(db_session):
    db_session.add(User(id="u1", email="u1@example.com", display_name="u1"))
    db_session.commit()
    return "u1"


@pytest.mark.asyncio
async def test_runner_yields_report_saved_after_complete(db_session, user, fake_report_runner):
    fake_report_runner.queue_events(
        [
            ReportStart(
                report_id="r_1",
                department="equity_research",
                mode="stock_update",
                section_titles=["t"],
            ),
            ReportComplete(report_id="r_1", schema=MINIMAL_SCHEMA),
        ]
    )
    runner = EquityResearchRunner(db_session=db_session, inner=fake_report_runner)
    events = []
    async for e in runner.run_report(
        user_id=user,
        mode="stock_update",
        user_input="AAPL event",
        session_id=None,
    ):
        events.append(e)
    assert any(isinstance(e, ReportStart) for e in events)
    assert any(isinstance(e, ReportComplete) for e in events)
    saved = [e for e in events if isinstance(e, ReportSavedEvent)]
    assert len(saved) == 1
    assert saved[0].report_id


@pytest.mark.asyncio
async def test_runner_rejects_invalid_mode(db_session, user, fake_report_runner):
    runner = EquityResearchRunner(db_session=db_session, inner=fake_report_runner)
    with pytest.raises(ValueError, match="unknown equity_research mode"):
        async for _ in runner.run_report(
            user_id=user,
            mode="bogus",
            user_input="x",
            session_id=None,
        ):
            pass


@pytest.mark.asyncio
async def test_runner_forwards_active_config_to_inner(db_session, user, fake_report_runner):
    fake_report_runner.queue_events(
        [
            ReportComplete(report_id="r_1", schema=MINIMAL_SCHEMA),
        ]
    )
    runner = EquityResearchRunner(db_session=db_session, inner=fake_report_runner)
    async for _ in runner.run_report(
        user_id=user,
        mode="stock_update",
        user_input="AAPL",
        session_id=None,
    ):
        pass
    last = fake_report_runner.last_request
    assert last is not None
    assert last.mode == "stock_update"
    assert last.user_input == "AAPL"
    assert len(last.enabled_sections) == 7


@pytest.mark.asyncio
async def test_runner_threads_report_length_via_resolve_active(
    db_session, user, fake_report_runner
):
    """resolve_active threads `report_length` from the user's saved config
    into the inner ReportRequest (mapped: concise→brief, normal→standard,
    elaborative→long)."""
    from openlia_server.services.equity_research_config import (
        EquityResearchConfigService,
    )

    cfg_svc = EquityResearchConfigService(db_session)
    cfg_svc.get_config(user)
    cfg_svc.update_config(
        user,
        report_mode=None,
        report_length="elaborative",
        sections_by_mode=None,
        custom_sections_by_mode=None,
    )

    fake_report_runner.queue_events([ReportComplete(report_id="r_1", schema=MINIMAL_SCHEMA)])
    runner = EquityResearchRunner(db_session=db_session, inner=fake_report_runner)
    async for _ in runner.run_report(
        user_id=user,
        mode="stock_update",
        user_input="AAPL",
        session_id=None,
    ):
        pass
    assert fake_report_runner.last_request is not None
    assert fake_report_runner.last_request.length == "long"
