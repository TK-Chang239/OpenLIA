from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from openlia.llm.runtime.events import ReportComplete, ReportStart
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import PortfolioHolding, Report
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
async def test_on_demand_reads_config(create_tables, db_session, fake_report_runner) -> None:
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
    fake_report_runner.queue_events([ReportComplete(report_id="pending", schema=MINIMAL_SCHEMA)])
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


@pytest.mark.asyncio
async def test_on_demand_titles_report_with_date_and_session(
    create_tables, db_session, fake_report_runner, monkeypatch
) -> None:
    """Stage 14: persisted report.title follows MM/DD/YYYY <Session> format
    derived from local time, not whatever the LLM put in cover.title."""
    _mk_user(db_session)
    fixed_local = datetime(2026, 5, 5, 8, 30, tzinfo=ZoneInfo("America/Los_Angeles"))
    monkeypatch.setattr(
        "openlia_server.services.mb_runner._now_local", lambda: fixed_local
    )
    fake_report_runner.queue_events(
        [ReportComplete(report_id="pending_r", schema=MINIMAL_SCHEMA)]
    )
    async for _ in run_on_demand(
        session=db_session, user_id="u_1", report_runner=fake_report_runner
    ):
        pass
    saved = db_session.query(Report).filter_by(user_id="u_1").one()
    assert saved.title == "05/05/2026 Morning"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("hour", "expected_label"),
    [
        (4, "Morning"),
        (11, "Morning"),
        (12, "Noon"),
        (16, "Noon"),
        (17, "Night"),
        (3, "Night"),
    ],
)
async def test_on_demand_session_label_buckets_hours(
    create_tables, db_session, fake_report_runner, monkeypatch, hour, expected_label
) -> None:
    _mk_user(db_session)
    fixed_local = datetime(2026, 5, 5, hour, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
    monkeypatch.setattr(
        "openlia_server.services.mb_runner._now_local", lambda: fixed_local
    )
    fake_report_runner.queue_events(
        [ReportComplete(report_id="pending_r", schema=MINIMAL_SCHEMA)]
    )
    async for _ in run_on_demand(
        session=db_session, user_id="u_1", report_runner=fake_report_runner
    ):
        pass
    saved = db_session.query(Report).filter_by(user_id="u_1").one()
    assert saved.title.endswith(expected_label), (
        f"hour {hour} expected {expected_label}, got {saved.title!r}"
    )


@pytest.mark.asyncio
async def test_on_demand_forwards_section_topics_and_reference_portfolio(
    create_tables, db_session, fake_report_runner
) -> None:
    """NEW-16-06 — captured ReportRequest carries section_topics + reference_portfolio
    as typed fields (not JSON-stuffed into user_input)."""
    _mk_user(db_session)
    db_session.add(
        MbUserConfig(
            id="c1",
            user_id="u_1",
            report_length="normal",
            enabled_section_ids=["global_macro", "upcoming_preview"],
            section_topics={"global_macro": [{"topic": "War", "notes": "Russia-Ukraine"}]},
            custom_sections=[],
            reference_portfolio=True,
        )
    )
    db_session.add(PortfolioHolding(id="h1", user_id="u_1", ticker="AAPL", name="Apple Inc."))
    db_session.add(PortfolioHolding(id="h2", user_id="u_1", ticker="NVDA", name="NVIDIA"))
    db_session.commit()
    fake_report_runner.queue_events([ReportComplete(report_id="pending", schema=MINIMAL_SCHEMA)])
    async for _ in run_on_demand(
        session=db_session, user_id="u_1", report_runner=fake_report_runner
    ):
        pass
    captured = fake_report_runner.last_request
    assert captured.section_topics == {
        "global_macro": [{"topic": "War", "notes": "Russia-Ukraine"}]
    }
    assert captured.reference_portfolio is not None
    tickers = [h["ticker"] for h in captured.reference_portfolio]
    assert "AAPL" in tickers
    assert "NVDA" in tickers
    assert "MB_EXTRAS_JSON" not in captured.user_input
