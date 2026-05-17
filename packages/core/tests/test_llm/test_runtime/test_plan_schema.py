from __future__ import annotations

import pytest
from openlia.llm.runtime.plan_schema import DataPath, ReportPlan, SectionPlan
from pydantic import ValidationError


def _valid_section_plan(**overrides) -> dict:
    base = {
        "section_id": "company_overview",
        "title": "Company Overview",
        "narrative_goal": "Frame the business and its current position.",
        "key_questions": [
            "What does the company do?",
            "How does it make money?",
            "Who are key customers?",
        ],
        "target_depth": "standard",
        "word_budget": 600,
        "data_paths": [
            {
                "tool_name": "eodhd__get_fundamentals_data",
                "tool_arguments": {"ticker": "MSFT.US"},
                "path": "General",
                "purpose": "Company background fields",
            }
        ],
        "cross_refs": [],
    }
    base.update(overrides)
    return base


def _valid_plan(**overrides) -> dict:
    base = {
        "company_thesis": "Microsoft is a mature franchise with cloud growth as the swing factor.",
        "sections": [_valid_section_plan()],
        "cross_section_themes": ["cloud growth", "AI capex pressure"],
    }
    base.update(overrides)
    return base


def test_minimal_plan_validates() -> None:
    plan = ReportPlan.model_validate(_valid_plan())
    assert plan.company_thesis.startswith("Microsoft")
    assert len(plan.sections) == 1
    assert plan.sections[0].section_id == "company_overview"


def test_section_id_uniqueness_enforced() -> None:
    bad = _valid_plan(sections=[_valid_section_plan(), _valid_section_plan()])
    with pytest.raises(ValidationError, match="unique"):
        ReportPlan.model_validate(bad)


def test_word_budget_range_enforced() -> None:
    with pytest.raises(ValidationError):
        SectionPlan.model_validate(_valid_section_plan(word_budget=50))
    with pytest.raises(ValidationError):
        SectionPlan.model_validate(_valid_section_plan(word_budget=3000))


def test_key_questions_min_three_max_six() -> None:
    too_few = _valid_section_plan(key_questions=["just one?", "and two"])
    with pytest.raises(ValidationError):
        SectionPlan.model_validate(too_few)
    too_many = _valid_section_plan(key_questions=[f"q{i}" for i in range(7)])
    with pytest.raises(ValidationError):
        SectionPlan.model_validate(too_many)


def test_cross_section_themes_min_two_max_four() -> None:
    with pytest.raises(ValidationError):
        ReportPlan.model_validate(_valid_plan(cross_section_themes=["only one"]))
    with pytest.raises(ValidationError):
        ReportPlan.model_validate(_valid_plan(cross_section_themes=[f"t{i}" for i in range(5)]))


def test_data_path_requires_exactly_one_source() -> None:
    with pytest.raises(ValidationError, match="one of"):
        DataPath.model_validate({"purpose": "x"})  # neither ref nor tool_name
    with pytest.raises(ValidationError, match="one of"):
        DataPath.model_validate(
            {
                "ref": "r_abc",
                "tool_name": "eodhd__get_fundamentals_data",
                "tool_arguments": {"ticker": "MSFT.US"},
                "purpose": "x",
            }
        )


def test_data_path_tool_requires_arguments() -> None:
    with pytest.raises(ValidationError, match="arguments"):
        DataPath.model_validate({"tool_name": "eodhd__get_fundamentals_data", "purpose": "x"})


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        ReportPlan.model_validate(_valid_plan(extra_field="nope"))
