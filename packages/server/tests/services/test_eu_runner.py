from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import pytest
from openlia.llm.runtime.events import (
    ReportComplete,
    ReportPhase,
    ReportStart,
    SseEvent,
)
from openlia.llm.runtime.messages import ReportRequest
from openlia_server.db.models.auth import User
from openlia_server.services.eu_runner import run_on_demand
from sqlalchemy.orm import Session


def _mk_user(db: Session, user_id: str = "u_1") -> User:
    u = User(
        id=user_id, email=f"{user_id}@x", display_name=user_id,
        password_hash="x", is_admin=False,
    )
    db.add(u)
    db.commit()
    return u


@dataclass
class ScriptedRunner:
    events: list[SseEvent]
    received: list[tuple[str, str, ReportRequest]] = field(default_factory=list)

    async def run(
        self, *, department_id: str, user_id: str, request: ReportRequest,
    ) -> AsyncIterator[SseEvent]:
        self.received.append((department_id, user_id, request))
        for e in self.events:
            yield e


@dataclass
class FakeReportStore:
    saved: list[dict] = field(default_factory=list)

    def save_from_event(
        self, *, user_id: str, department: str, report_type: str, event: ReportComplete,
    ) -> str:
        rid = event.report_id
        self.saved.append({"user_id": user_id, "report_id": rid,
                           "department": department, "report_type": report_type})
        return rid


@pytest.mark.asyncio
async def test_on_demand_forwards_events_and_persists(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    complete = ReportComplete(report_id="r_1", schema={"title": "AAPL Q1 FY2026", "sections": []})
    runner = ScriptedRunner(events=[
        ReportStart(report_id="r_1", department="earnings_update",
                    mode="earnings_analysis", section_titles=["Quick Take"]),
        ReportPhase(report_id="r_1", phase="writing"),
        complete,
    ])
    store = FakeReportStore()

    collected: list[SseEvent] = []
    async for ev in run_on_demand(
        session=db_session, user_id="u_1", ticker="AAPL",
        report_runner=runner, report_store=store,
    ):
        collected.append(ev)

    assert [type(e).__name__ for e in collected] == ["ReportStart", "ReportPhase", "ReportComplete"]
    assert runner.received[0][0] == "earnings_update"
    assert "AAPL" in runner.received[0][2].user_input
    assert runner.received[0][2].mode == "earnings_analysis"
    assert store.saved == [
        {"user_id": "u_1", "report_id": "r_1",
         "department": "earnings_update", "report_type": "earnings_update"},
    ]


@pytest.mark.asyncio
async def test_on_demand_uppercases_ticker(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    complete = ReportComplete(report_id="r_2", schema={"title": "x", "sections": []})
    runner = ScriptedRunner(events=[complete])
    store = FakeReportStore()

    async for _ in run_on_demand(
        session=db_session, user_id="u_1", ticker="tsla",
        report_runner=runner, report_store=store,
    ):
        pass
    assert "TSLA" in runner.received[0][2].user_input


@pytest.mark.asyncio
async def test_on_demand_pulls_user_config(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.departments import EuUserConfig
    _mk_user(db_session)
    db_session.add(EuUserConfig(
        id="euc_1", user_id="u_1", report_length="elaborative",
        enabled_section_ids=["quick_take"], custom_sections=[],
    ))
    db_session.commit()

    complete = ReportComplete(report_id="r_3", schema={"title": "x", "sections": []})
    runner = ScriptedRunner(events=[complete])
    store = FakeReportStore()
    async for _ in run_on_demand(
        session=db_session, user_id="u_1", ticker="AAPL",
        report_runner=runner, report_store=store,
    ):
        pass
    req = runner.received[0][2]
    # Config column holds "elaborative"; service maps to ReportRequest.length "long".
    assert req.length == "long"
    assert req.enabled_sections == ["quick_take"]
