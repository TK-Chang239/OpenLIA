from __future__ import annotations

import pytest
from openlia_server.scheduler.payloads import (
    DepartmentPayloadBuilderNotWired,
    EUScanTarget,
    MRAssessmentPayload,
    StubEUScanPlanner,
    StubMBRequestBuilder,
    StubMRAssessmentBuilder,
    StubMRCacheStore,
    StubReportStore,
)


def test_eu_scan_target_holds_ticker_and_request() -> None:
    from openlia.llm.runtime.messages import ReportRequest

    req = ReportRequest(mode="stock_update", user_input="AAPL earnings")
    target = EUScanTarget(ticker="AAPL", request=req)
    assert target.ticker == "AAPL"
    assert target.request is req


def test_mr_assessment_payload_carries_items_schema_and_synthesize() -> None:
    from openlia.llm.runtime.messages import BatchItem, BatchResult, ReportRequest
    from pydantic import BaseModel

    class _T4Stub(BaseModel):
        score: float

    def _synth(results: list[BatchResult]) -> ReportRequest:
        joined = ",".join(r.id for r in results)
        return ReportRequest(mode="mr_synthesis", user_input=f"synth({joined})")

    payload = MRAssessmentPayload(
        items=[BatchItem(id="i1", context={"metric": "debt_burden"})],
        t4_task="debt_cycle",
        t4_schema=_T4Stub,
        synthesize=_synth,
    )
    assert payload.items[0].id == "i1"
    assert payload.t4_task == "debt_cycle"
    assert payload.t4_schema is _T4Stub
    req = payload.synthesize([BatchResult(id="i1", ok=True, data={"score": 1.0}, error=None)])
    assert req.mode == "mr_synthesis"
    assert "synth(i1)" in req.user_input


def test_stub_mb_builder_raises() -> None:
    stub = StubMBRequestBuilder()
    with pytest.raises(DepartmentPayloadBuilderNotWired, match="Plan 16"):
        stub.build(session=None, user_id="u_1", schedule_id="s_1")


def test_stub_eu_planner_raises() -> None:
    stub = StubEUScanPlanner()
    with pytest.raises(DepartmentPayloadBuilderNotWired, match="Plan 15"):
        stub.plan(session=None, user_id="u_1", schedule_id="s_1", since=None)


def test_stub_mr_builder_raises() -> None:
    stub = StubMRAssessmentBuilder()
    with pytest.raises(DepartmentPayloadBuilderNotWired, match="Plan 19"):
        stub.build(session=None, user_id="u_1")


def test_stub_report_store_raises() -> None:
    stub = StubReportStore()
    with pytest.raises(DepartmentPayloadBuilderNotWired, match="Plan 13"):
        stub.save(
            session=None,
            user_id="u_1",
            department="morning_briefing",
            payload={},
        )


def test_stub_mr_cache_store_raises() -> None:
    stub = StubMRCacheStore()
    with pytest.raises(DepartmentPayloadBuilderNotWired, match="Plan 19"):
        stub.save(session=None, user_id="u_1", payload={})
