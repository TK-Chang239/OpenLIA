from __future__ import annotations

from openlia.llm.runtime.plan_schema import ReportPlan, SectionPlan
from openlia.llm.runtime.subagent_runner import dedupe_data_paths


def _section(section_id: str, data_paths: list[dict]) -> SectionPlan:
    return SectionPlan.model_validate(
        {
            "section_id": section_id,
            "title": section_id,
            "narrative_goal": "g",
            "key_questions": ["a", "b", "c"],
            "target_depth": "standard",
            "word_budget": 200,
            "data_paths": data_paths,
            "cross_refs": [],
        }
    )


def test_dedupe_identical_tool_calls_across_sections() -> None:
    fund_path_a = {
        "tool_name": "eodhd__get_fundamentals_data",
        "tool_arguments": {"ticker": "MSFT.US"},
        "purpose": "income",
        "path": "Financials.Income_Statement.yearly",
    }
    fund_path_b = {
        "tool_name": "eodhd__get_fundamentals_data",
        "tool_arguments": {"ticker": "MSFT.US"},
        "purpose": "balance",
        "path": "Financials.Balance_Sheet.yearly",
    }
    plan = ReportPlan.model_validate(
        {
            "company_thesis": "x",
            "cross_section_themes": ["t1", "t2"],
            "sections": [
                _section("a", [fund_path_a]).model_dump(),
                _section("b", [fund_path_b]).model_dump(),
            ],
        }
    )
    unique_calls = dedupe_data_paths(plan)
    # Tool dispatch is keyed by (tool_name, frozenset(args.items())). Two
    # paths sharing the same tool+args produce ONE dispatch entry, with both
    # paths attached for later slicing.
    assert len(unique_calls) == 1
    call = unique_calls[0]
    assert call.tool_name == "eodhd__get_fundamentals_data"
    assert call.tool_arguments == {"ticker": "MSFT.US"}
    paths = [dp.path for dp in call.attached]
    assert "Financials.Income_Statement.yearly" in paths
    assert "Financials.Balance_Sheet.yearly" in paths


def test_dedupe_distinct_tool_calls() -> None:
    plan = ReportPlan.model_validate(
        {
            "company_thesis": "x",
            "cross_section_themes": ["t1", "t2"],
            "sections": [
                _section(
                    "a",
                    [
                        {
                            "tool_name": "eodhd__get_fundamentals_data",
                            "tool_arguments": {"ticker": "MSFT.US"},
                            "purpose": "x",
                        }
                    ],
                ).model_dump(),
                _section(
                    "b",
                    [
                        {
                            "tool_name": "eodhd__get_fundamentals_data",
                            "tool_arguments": {"ticker": "AAPL.US"},
                            "purpose": "y",
                        }
                    ],
                ).model_dump(),
            ],
        }
    )
    unique = dedupe_data_paths(plan)
    assert len(unique) == 2
