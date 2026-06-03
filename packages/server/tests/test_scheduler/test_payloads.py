from __future__ import annotations

import pytest
from _scheduler_fakes import (
    StubEUScanPlanner,
    StubReportStore,
)
from openlia_server.scheduler.payloads import (
    DepartmentPayloadBuilderNotWired,
    EUScanTarget,
)


def test_eu_scan_target_holds_ticker_and_request() -> None:
    from openlia.llm.runtime.messages import ReportRequest

    req = ReportRequest(mode="stock_update", user_input="AAPL earnings")
    target = EUScanTarget(ticker="AAPL", request=req)
    assert target.ticker == "AAPL"
    assert target.request is req


def test_stub_eu_planner_raises() -> None:
    stub = StubEUScanPlanner()
    with pytest.raises(DepartmentPayloadBuilderNotWired):
        stub.plan(session=None, user_id="u_1", schedule_id="s_1", since=None)


def test_stub_report_store_raises() -> None:
    stub = StubReportStore()
    with pytest.raises(DepartmentPayloadBuilderNotWired):
        stub.save(
            session=None,
            user_id="u_1",
            department="morning_briefing",
            payload={},
        )
