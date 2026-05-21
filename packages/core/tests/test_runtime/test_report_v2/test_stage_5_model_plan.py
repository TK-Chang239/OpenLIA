"""Tests for Stage 5 Model Planner (Task P4)."""

from unittest.mock import Mock

from openlia.llm.runtime.report_v2.pipeline.stage_5_model_plan import (
    ModelPlanner,
    build_model_planner_prompt,
)
from openlia.llm.runtime.report_v2.schemas.plan import (
    ArtifactSpec,
    Plan,
)


def _make_plan_with_required() -> Plan:
    return Plan(
        required_artifacts=[
            ArtifactSpec(
                id="dcf",
                type="chart",
                description="DCF valuation",
                source="template",
            )
        ],
        optional_artifacts=[],
        research_strands=[],
        section_dag={},
    )


def _make_research_pool(findings: dict[str, str]):
    pool = Mock()
    pool.findings_by_strand = findings
    return pool


def test_model_planner_appends_optional_artifacts_only():
    fake_llm = Mock()
    fake_llm.call.return_value = {
        "optional_artifacts": [
            {
                "id": "peer_table",
                "type": "table",
                "description": "Peer comparison table",
                "source": "planner",
            }
        ]
    }
    plan = _make_plan_with_required()
    pool = _make_research_pool({"financials": "Revenue grew 20% YoY."})

    planner = ModelPlanner(llm=fake_llm)
    result = planner.plan(plan, pool)

    # required_artifacts unchanged
    assert len(result.required_artifacts) == 1
    assert result.required_artifacts[0].id == "dcf"
    # optional_artifacts appended
    assert len(result.optional_artifacts) == 1
    assert result.optional_artifacts[0].id == "peer_table"


def test_model_planner_swallows_llm_error():
    fake_llm = Mock()
    fake_llm.call.side_effect = RuntimeError("LLM timeout")
    plan = _make_plan_with_required()
    pool = _make_research_pool({"financials": "Revenue data."})

    planner = ModelPlanner(llm=fake_llm)
    result = planner.plan(plan, pool)

    assert result.optional_artifacts == []
    assert len(result.required_artifacts) == 1
    assert result.required_artifacts[0].id == "dcf"


def test_optional_artifact_source_set_to_planner():
    fake_llm = Mock()
    # LLM returns artifact without source field
    fake_llm.call.return_value = {
        "optional_artifacts": [
            {
                "id": "segment_chart",
                "type": "chart",
                "description": "Revenue by segment",
                # no "source" key
            }
        ]
    }
    plan = _make_plan_with_required()
    pool = _make_research_pool({"segments": "Product, Cloud, Services."})

    planner = ModelPlanner(llm=fake_llm)
    result = planner.plan(plan, pool)

    assert result.optional_artifacts[0].source == "planner"


def test_research_pool_index_uses_first_line_first_160_chars():
    fake_llm = Mock()
    fake_llm.call.return_value = {"optional_artifacts": []}

    long_finding = "Line one with lots of data here.\nLine two should be ignored entirely."
    expected_snippet = "Line one with lots of data here."[:160]

    pool = _make_research_pool({"financials": long_finding})
    plan = _make_plan_with_required()

    planner = ModelPlanner(llm=fake_llm)
    planner.plan(plan, pool)

    fake_llm.call.assert_called_once()
    call_args = fake_llm.call.call_args
    # Support both positional and keyword argument styles
    user = call_args.kwargs.get("user")
    if user is None and len(call_args.args) > 1:
        user = call_args.args[1]
    assert user is not None, "user argument not found in LLM call"
    assert "research_pool_index" in user
    assert user["research_pool_index"]["financials"] == expected_snippet


def test_build_model_planner_prompt_returns_str():
    prompt = build_model_planner_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 0
