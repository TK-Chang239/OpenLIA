"""Tests for Stage 3 Research Planner + Plan schema (Task P2)."""

from unittest.mock import Mock

from openlia.llm.runtime.report_v2.pipeline.stage_3_research_plan import ResearchPlanner
from openlia.llm.runtime.report_v2.schemas.plan import (
    ArtifactSpec,
    Plan,
)


def test_plan_has_research_strands_and_required_artifacts():
    p = Plan(research_strands=[], required_artifacts=[], section_dag={})
    assert hasattr(p, "research_strands")
    assert hasattr(p, "required_artifacts")
    assert hasattr(p, "section_dag")


def test_planner_freezes_required_artifacts_from_template():
    fake_llm = Mock()
    fake_llm.call.return_value = {
        "research_strands": [
            {
                "id": "financials",
                "purpose": "Pull financials",
                "allowed_tools": ["eodhd.get_fundamentals_data"],
            }
        ],
        "required_artifacts": [],
        "section_dag": {"thesis": [], "valuation": ["thesis"]},
    }
    template = Mock()
    template.required_artifacts = [
        ArtifactSpec(
            id="dcf",
            type="chart",
            description="DCF",
            parameters={},
            helper="dcf_valuation",
            source="template",
        )
    ]
    template.sections = []
    composer_inputs = {"ticker": "NVDA", "prompt": "include a DCF sensitivity"}
    planner = ResearchPlanner(llm=fake_llm)
    plan = planner.plan(
        composer_inputs=composer_inputs,
        template_spec=template,
        clarifier_answers={},
    )
    ids = {a.id for a in plan.required_artifacts}
    assert "dcf" in ids
    # template artifact source must be "template"
    dcf = next(a for a in plan.required_artifacts if a.id == "dcf")
    assert dcf.source == "template"


def test_planner_appends_composer_parsed_artifacts():
    fake_llm = Mock()
    fake_llm.call.return_value = {
        "research_strands": [],
        "required_artifacts": [
            {
                "id": "revenue_table",
                "type": "table",
                "description": "Revenue breakdown",
                "source": "composer",
            }
        ],
        "section_dag": {},
    }
    template = Mock()
    template.required_artifacts = [
        ArtifactSpec(
            id="dcf",
            type="chart",
            description="DCF",
            source="template",
        )
    ]
    template.sections = []
    planner = ResearchPlanner(llm=fake_llm)
    plan = planner.plan(
        composer_inputs={"ticker": "AAPL"},
        template_spec=template,
        clarifier_answers={},
    )
    ids = {a.id for a in plan.required_artifacts}
    assert "dcf" in ids
    assert "revenue_table" in ids
    sources = {a.id: a.source for a in plan.required_artifacts}
    assert sources["dcf"] == "template"
    assert sources["revenue_table"] == "composer"


def test_planner_emits_slipped_request_for_unmapped_intent():
    fake_llm = Mock()
    fake_llm.call.return_value = {
        "research_strands": [],
        "required_artifacts": [],
        "section_dag": {},
        "slipped_requests": ["use VaR for risk section"],
    }
    template = Mock()
    template.required_artifacts = []
    template.sections = []
    planner = ResearchPlanner(llm=fake_llm)
    plan = planner.plan(
        composer_inputs={"ticker": "NVDA"},
        template_spec=template,
        clarifier_answers={},
    )
    assert "use VaR for risk section" in plan.slipped_requests


def test_section_dag_passed_through():
    fake_llm = Mock()
    expected_dag = {"thesis": [], "valuation": ["thesis"]}
    fake_llm.call.return_value = {
        "research_strands": [],
        "required_artifacts": [],
        "section_dag": expected_dag,
    }
    template = Mock()
    template.required_artifacts = []
    template.sections = []
    planner = ResearchPlanner(llm=fake_llm)
    plan = planner.plan(
        composer_inputs={"ticker": "MSFT"},
        template_spec=template,
        clarifier_answers={},
    )
    assert plan.section_dag == expected_dag
