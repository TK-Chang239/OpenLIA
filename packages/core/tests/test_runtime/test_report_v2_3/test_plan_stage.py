"""Unit tests for PlanStage — request shape + outline validation."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2_3.clients.planner import (
    FakePlannerClient,
    PlannerRequest,
)
from openlia.llm.runtime.report_v2_3.schemas import (
    ClarifyProceed,
    DataNeed,
    Language,
    Outline,
    OutlineSection,
    ReportType,
)
from openlia.llm.runtime.report_v2_3.stages import PlanStage, StageContext
from openlia.llm.runtime.report_v2_3.state import ReportState
from openlia.llm.runtime.report_v2_3.templates import get_builtin


def _state() -> ReportState:
    s = ReportState(
        run_id="r",
        user_id="u",
        raw_prompt="initiate on NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
        template=get_builtin(ReportType.INITIATION),
    )
    s.clarify_result = ClarifyProceed(assumptions=["audience: PM", "horizon: 12 months"])
    return s


def _ctx() -> StageContext:
    return StageContext(clients={}, tools={}, extras={})


def _outline(
    *,
    tickers: list[str] | None = None,
    report_type: ReportType = ReportType.INITIATION,
    sections: list[OutlineSection] | None = None,
) -> Outline:
    return Outline(
        tickers=tickers if tickers is not None else ["NVDA"],
        report_type=report_type,
        sections=sections
        if sections is not None
        else [
            OutlineSection(
                id="overview",
                title="Overview",
                data_needs=[DataNeed(description="business model summary")],
            ),
            OutlineSection(
                id="financials",
                title="Financials",
                data_needs=[
                    DataNeed(description="revenue, last 8 quarters"),
                    DataNeed(description="gross margin trend, last 8 quarters"),
                ],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_happy_path_writes_outline_to_state() -> None:
    expected = _outline()
    client = FakePlannerClient(result=expected)
    stage = PlanStage(client)

    state = stage.run(_state(), _ctx())
    assert state.outline is expected
    assert len(client.calls) == 1
    request = client.calls[0]
    assert isinstance(request, PlannerRequest)
    assert request.raw_prompt == "initiate on NVDA"
    assert request.tickers == ["NVDA"]
    assert isinstance(request.clarify_result, ClarifyProceed)
    assert request.clarify_result.assumptions == ["audience: PM", "horizon: 12 months"]


def test_data_needs_specificity_carried_through() -> None:
    """data_needs is what RESEARCH consumes; verify it survives the stage."""
    stage = PlanStage(FakePlannerClient(result=_outline()))
    state = stage.run(_state(), _ctx())
    assert state.outline is not None
    financials = next(s for s in state.outline.sections if s.id == "financials")
    descriptions = [n.description for n in financials.data_needs]
    assert "revenue, last 8 quarters" in descriptions


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


def test_outline_with_mismatched_tickers_raises() -> None:
    bad = _outline(tickers=["AAPL"])
    with pytest.raises(RuntimeError, match="tickers"):
        PlanStage(FakePlannerClient(result=bad)).run(_state(), _ctx())


def test_outline_with_mismatched_report_type_raises() -> None:
    bad = _outline(report_type=ReportType.MORNING_BRIEF)
    with pytest.raises(RuntimeError, match="report_type"):
        PlanStage(FakePlannerClient(result=bad)).run(_state(), _ctx())


def test_outline_with_no_sections_raises() -> None:
    bad = _outline(sections=[])
    with pytest.raises(RuntimeError, match="no sections"):
        PlanStage(FakePlannerClient(result=bad)).run(_state(), _ctx())


def test_outline_with_duplicate_section_ids_raises() -> None:
    bad = _outline(
        sections=[
            OutlineSection(id="overview", title="Overview"),
            OutlineSection(id="overview", title="Overview again"),
        ]
    )
    with pytest.raises(RuntimeError, match="duplicate section ids"):
        PlanStage(FakePlannerClient(result=bad)).run(_state(), _ctx())
