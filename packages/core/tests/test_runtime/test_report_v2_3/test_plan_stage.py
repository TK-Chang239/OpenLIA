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
from openlia.llm.runtime.report_v2_3.templates import (
    SectionSpec,
    TemplateSpec,
)


def _overview_financials_template() -> TemplateSpec:
    """Template whose section list mirrors the legacy _outline() fixture
    so the existing happy-path tests survive the strict coercion step."""
    return TemplateSpec(
        template_id="t_overview_financials",
        name="Overview + Financials",
        shape_description="Two-section test template.",
        sections=[
            SectionSpec(id="overview", title="Overview", intent="Overview."),
            SectionSpec(id="financials", title="Financials", intent="Financials."),
        ],
    )


def _state() -> ReportState:
    s = ReportState(
        run_id="r",
        user_id="u",
        raw_prompt="initiate on NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
        template=_overview_financials_template(),
    )
    s.clarify_result = ClarifyProceed(assumptions=["audience: PM", "horizon: 12 months"])
    return s


def _state_with_template(*, template: TemplateSpec) -> ReportState:
    s = ReportState(
        run_id="r",
        user_id="u",
        raw_prompt="initiate on NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
        template=template,
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
    # Coercion rebuilds outline.sections from the template, so identity
    # is no longer preserved — content equality is what matters.
    assert state.outline is not None
    assert [s.id for s in state.outline.sections] == ["overview", "financials"]
    assert state.outline.tickers == expected.tickers
    assert state.outline.report_type == expected.report_type
    assert len(client.calls) == 1
    request = client.calls[0]
    assert isinstance(request, PlannerRequest)
    assert request.raw_prompt == "initiate on NVDA"
    assert request.tickers == ["NVDA"]
    assert request.template.template_id == "t_overview_financials"
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


# Note: tests asserting "outline with no sections raises" and "outline
# with duplicate section ids raises" were removed in Phase 1 Task 6.
# Both invariants are now guaranteed by `_coerce_outline_to_template`,
# which rebuilds the outline from `template.sections` after the LLM
# returns. The template's own validator (TemplateSpec._check_unique_section_ids)
# already forbids duplicate ids at construction time, and the schema
# enforces at least one section, so the validator paths these tests
# pinned are no longer reachable through PLAN.


# ---------------------------------------------------------------------------
# Template coercion — outline structure comes from template, not LLM
# ---------------------------------------------------------------------------


def test_plan_outline_matches_template_sections_exactly():
    """The planner's outline must have one section per template section,
    in order, with matching ids. The LLM's job is fact_ids and
    valuation_plan, not structure."""
    from openlia.llm.runtime.report_v2_3.clients.planner import (
        FakePlannerClient,
    )
    from openlia.llm.runtime.report_v2_3.schemas import (
        Outline,
        OutlineSection,
        ReportType,
        ValuationPlan,
    )
    from openlia.llm.runtime.report_v2_3.templates import (
        SectionSpec,
        TemplateSpec,
    )

    custom = TemplateSpec(
        template_id="t_three",
        name="Three sections",
        shape_description="Three sections for coercion test.",
        sections=[
            SectionSpec(id="a", title="A", intent="A."),
            SectionSpec(id="b", title="B", intent="B."),
            SectionSpec(id="c", title="C", intent="C."),
        ],
    )
    state = _state_with_template(template=custom)
    # Fake planner returns an outline with the WRONG section list to
    # exercise the coercion path.
    fake_outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[
            OutlineSection(
                id="something_else",
                title="Something",
                data_needs=[],
            ),
        ],
        valuation_plan=ValuationPlan(),
    )
    stage = PlanStage(FakePlannerClient(result=fake_outline))
    stage.run(state, _ctx())

    # After coercion, state.outline.sections must mirror template.sections
    assert [s.id for s in state.outline.sections] == ["a", "b", "c"]
    assert [s.title for s in state.outline.sections] == ["A", "B", "C"]


def test_plan_preserves_llm_authored_fact_ids_per_matching_section():
    """When the LLM correctly enumerates fact_ids for a section whose
    id matches a template section, the coercion step keeps the fact_ids."""
    from openlia.llm.runtime.report_v2_3.clients.planner import (
        FakePlannerClient,
    )
    from openlia.llm.runtime.report_v2_3.schemas import (
        DataNeed,
        Outline,
        OutlineSection,
        ReportType,
        ValuationPlan,
    )
    from openlia.llm.runtime.report_v2_3.templates import (
        SectionSpec,
        TemplateSpec,
    )

    custom = TemplateSpec(
        template_id="t_two",
        name="Two sections",
        shape_description="Two sections for fact_id preservation test.",
        sections=[
            SectionSpec(id="alpha", title="Alpha", intent="A."),
            SectionSpec(id="beta", title="Beta", intent="B."),
        ],
    )
    state = _state_with_template(template=custom)
    fake_outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[
            OutlineSection(
                id="alpha",
                title="Alpha",
                data_needs=[
                    DataNeed(description="alpha facts", expected_fact_ids=["fact_a1", "fact_a2"]),
                ],
            ),
            OutlineSection(
                id="beta",
                title="Beta",
                data_needs=[
                    DataNeed(description="beta facts", expected_fact_ids=["fact_b1"]),
                ],
            ),
        ],
        valuation_plan=ValuationPlan(),
    )
    stage = PlanStage(FakePlannerClient(result=fake_outline))
    stage.run(state, _ctx())

    alpha = next(s for s in state.outline.sections if s.id == "alpha")
    beta = next(s for s in state.outline.sections if s.id == "beta")
    alpha_ids = [fid for n in alpha.data_needs for fid in n.expected_fact_ids]
    beta_ids = [fid for n in beta.data_needs for fid in n.expected_fact_ids]
    assert alpha_ids == ["fact_a1", "fact_a2"]
    assert beta_ids == ["fact_b1"]


def test_plan_strips_extra_sections_emitted_by_llm():
    """If the LLM emits an extra section not in the template, drop it."""
    from openlia.llm.runtime.report_v2_3.clients.planner import (
        FakePlannerClient,
    )
    from openlia.llm.runtime.report_v2_3.schemas import (
        DataNeed,
        Outline,
        OutlineSection,
        ReportType,
        ValuationPlan,
    )
    from openlia.llm.runtime.report_v2_3.templates import (
        SectionSpec,
        TemplateSpec,
    )

    custom = TemplateSpec(
        template_id="t_one",
        name="One section",
        shape_description="One section.",
        sections=[
            SectionSpec(id="only", title="Only", intent="O."),
        ],
    )
    state = _state_with_template(template=custom)
    fake_outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[
            OutlineSection(
                id="only",
                title="Only",
                data_needs=[DataNeed(description="x", expected_fact_ids=["x"])],
            ),
            OutlineSection(
                id="stray",
                title="Stray",
                data_needs=[DataNeed(description="y", expected_fact_ids=["y"])],
            ),
        ],
        valuation_plan=ValuationPlan(),
    )
    stage = PlanStage(FakePlannerClient(result=fake_outline))
    stage.run(state, _ctx())

    assert len(state.outline.sections) == 1
    assert state.outline.sections[0].id == "only"
    only_ids = [
        fid for n in state.outline.sections[0].data_needs for fid in n.expected_fact_ids
    ]
    assert only_ids == ["x"]
