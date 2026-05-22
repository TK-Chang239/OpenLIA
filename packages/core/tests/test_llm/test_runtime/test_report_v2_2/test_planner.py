"""Tests for Stage 5 planner (planner.py).

Covers:
- PlannerOutput Pydantic shape round-trips
- HelperSelection / HelperInvocation construction
- Stubbed LLM call returns valid PlannerOutput via Planner.aplan()
- _parse_planner_response handles both clean JSON and markdown-fenced JSON
- sections_from_spec builds section dicts from a TemplateSpecV2
"""

from __future__ import annotations

import asyncio
import json

import pytest
from openlia.llm.runtime.report_v2_2.planner import (
    HelperInvocation,
    HelperSelection,
    Planner,
    PlannerOutput,
    _parse_planner_response,
    sections_from_spec,
)
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _minimal_planner_output_dict() -> dict:
    return {
        "helper_selection": [
            {
                "section_id": "valuation_dcf",
                "helpers": [
                    {
                        "helper_name": "dcf_valuation",
                        "params": {"wacc": 9.8},
                        "artifact_id": "dcf_output",
                    }
                ],
            }
        ],
        "planner_overrides": [],
        "open_questions": [],
        "cross_section_themes": ["Cloud growth driving margin expansion"],
    }


def _full_planner_output_dict() -> dict:
    return {
        "helper_selection": [
            {
                "section_id": "executive_summary",
                "helpers": [
                    {
                        "helper_name": "dcf_valuation",
                        "params": {},
                        "artifact_id": "dcf_base_valuation",
                    },
                    {
                        "helper_name": "ratio_calculator",
                        "params": {},
                        "artifact_id": "peer_multiple_panel",
                    },
                ],
            },
            {
                "section_id": "valuation_dcf",
                "helpers": [
                    {
                        "helper_name": "dcf_valuation",
                        "params": {},
                        "artifact_id": "dcf_base_valuation",
                    }
                ],
            },
        ],
        "planner_overrides": [
            {
                "template_id": "stock_initiation_v2",
                "overrides": [
                    {
                        "section_id": "valuation_comps",
                        "operation": "change_fidelity",
                        "artifact_id": "peer_multiple_panel",
                        "fidelity": "full",
                        "drafter_brief": None,
                    }
                ],
                "rationale": "User requested heavy peer comparison.",
            }
        ],
        "open_questions": ["What is the normalized free cash flow margin?"],
        "cross_section_themes": ["Cloud acceleration", "AI monetisation"],
    }


# ---------------------------------------------------------------------------
# PlannerOutput Pydantic shape
# ---------------------------------------------------------------------------


def test_planner_output_minimal_round_trip() -> None:
    raw = _minimal_planner_output_dict()
    output = _parse_planner_response(json.dumps(raw))
    assert isinstance(output, PlannerOutput)
    assert len(output.helper_selection) == 1
    assert output.helper_selection[0].section_id == "valuation_dcf"
    assert len(output.helper_selection[0].helpers) == 1
    assert output.helper_selection[0].helpers[0].helper_name == "dcf_valuation"
    assert output.planner_overrides == []
    assert output.open_questions == []
    assert output.cross_section_themes == ["Cloud growth driving margin expansion"]


def test_planner_output_full_round_trip() -> None:
    raw = _full_planner_output_dict()
    output = _parse_planner_response(json.dumps(raw))
    assert isinstance(output, PlannerOutput)
    assert len(output.helper_selection) == 2
    assert len(output.planner_overrides) == 1
    override = output.planner_overrides[0]
    assert override.template_id == "stock_initiation_v2"
    assert len(override.overrides) == 1
    assert override.overrides[0].operation == "change_fidelity"
    assert override.overrides[0].fidelity.value == "full"
    assert output.open_questions == ["What is the normalized free cash flow margin?"]


def test_planner_output_model_dump_validate() -> None:
    raw = _full_planner_output_dict()
    output = _parse_planner_response(json.dumps(raw))
    dumped = output.model_dump()
    # Re-validate from the dump (not via _parse_planner_response, directly).
    restored_selection = [HelperSelection.model_validate(s) for s in dumped["helper_selection"]]
    assert len(restored_selection) == 2


def test_helper_invocation_requires_helper_name_and_artifact_id() -> None:
    with pytest.raises(ValidationError):
        HelperInvocation.model_validate({"params": {}})  # missing required fields


def test_helper_selection_allows_empty_helpers() -> None:
    hs = HelperSelection(section_id="empty_section", helpers=[])
    assert hs.helpers == []


# ---------------------------------------------------------------------------
# _parse_planner_response: markdown-fenced JSON
# ---------------------------------------------------------------------------


def test_parse_strips_markdown_code_fence() -> None:
    raw = _minimal_planner_output_dict()
    fenced = "```json\n" + json.dumps(raw) + "\n```"
    output = _parse_planner_response(fenced)
    assert isinstance(output, PlannerOutput)
    assert len(output.helper_selection) == 1


def test_parse_strips_plain_code_fence() -> None:
    raw = _minimal_planner_output_dict()
    fenced = "```\n" + json.dumps(raw) + "\n```"
    output = _parse_planner_response(fenced)
    assert isinstance(output, PlannerOutput)


def test_parse_raises_on_invalid_json() -> None:
    with pytest.raises((json.JSONDecodeError, ValueError)):
        _parse_planner_response("not valid json")


# ---------------------------------------------------------------------------
# Stubbed LLM integration: Planner.aplan()
# ---------------------------------------------------------------------------


class _StubLLMProvider:
    """Minimal stub that returns a canned JSON PlannerOutput."""

    def __init__(self, response_json: str) -> None:
        self._response_json = response_json

    async def generate(self, request):
        from openlia.llm.types import LLMResponse

        return LLMResponse(
            text=self._response_json,
            finish_reason="stop",
            input_tokens=100,
            output_tokens=200,
        )


def test_planner_aplan_returns_valid_output() -> None:
    response_json = json.dumps(_minimal_planner_output_dict())
    stub = _StubLLMProvider(response_json)
    planner = Planner(
        llm=stub,  # type: ignore[arg-type]
        ticker="MSFT",
        template_sections=[
            {
                "section_id": "valuation_dcf",
                "title": "DCF Valuation",
                "default_artifacts": [{"artifact_id": "dcf_output", "fidelity": "full"}],
            }
        ],
        template_id="stock_initiation_v2",
    )
    output = asyncio.run(planner.aplan())
    assert isinstance(output, PlannerOutput)
    assert output.helper_selection[0].section_id == "valuation_dcf"


def test_planner_aplan_with_overrides() -> None:
    response_json = json.dumps(_full_planner_output_dict())
    stub = _StubLLMProvider(response_json)
    planner = Planner(
        llm=stub,  # type: ignore[arg-type]
        ticker="MSFT",
        template_sections=[],
        template_id="stock_initiation_v2",
    )
    output = asyncio.run(planner.aplan())
    assert len(output.planner_overrides) == 1
    assert output.planner_overrides[0].rationale == "User requested heavy peer comparison."


def test_planner_plan_sync_wrapper() -> None:
    """planner.plan() must work (sync wrapper around aplan)."""
    response_json = json.dumps(_minimal_planner_output_dict())
    stub = _StubLLMProvider(response_json)
    planner = Planner(
        llm=stub,  # type: ignore[arg-type]
        ticker="AAPL",
        template_sections=[],
        template_id="stock_initiation_v2",
    )
    output = planner.plan()
    assert isinstance(output, PlannerOutput)


# ---------------------------------------------------------------------------
# sections_from_spec
# ---------------------------------------------------------------------------


class _FakeSectionSpec:
    def __init__(self, id: str, name: str) -> None:
        self.id = id
        self.name = name


class _FakeArtifactSpec:
    def __init__(self, id: str, target_section_id: str) -> None:
        self.id = id
        self.target_section_id = target_section_id


class _FakeTemplateSpec:
    def __init__(self) -> None:
        self.sections = [
            _FakeSectionSpec("executive_summary", "Executive Summary"),
            _FakeSectionSpec("valuation_dcf", "DCF Valuation"),
        ]
        self.required_artifacts = [
            _FakeArtifactSpec("dcf_base_valuation", "valuation_dcf"),
            _FakeArtifactSpec("peer_panel", "executive_summary"),
        ]


def test_sections_from_spec_returns_correct_structure() -> None:
    spec = _FakeTemplateSpec()
    sections = sections_from_spec(spec)
    assert len(sections) == 2
    exec_section = next(s for s in sections if s["section_id"] == "executive_summary")
    dcf_section = next(s for s in sections if s["section_id"] == "valuation_dcf")
    assert exec_section["title"] == "Executive Summary"
    assert len(exec_section["default_artifacts"]) == 1
    assert exec_section["default_artifacts"][0]["artifact_id"] == "peer_panel"
    assert len(dcf_section["default_artifacts"]) == 1
    assert dcf_section["default_artifacts"][0]["artifact_id"] == "dcf_base_valuation"


def test_sections_from_spec_handles_no_sections() -> None:
    from typing import ClassVar

    class _Empty:
        sections: ClassVar[list] = []
        required_artifacts: ClassVar[list] = []

    sections = sections_from_spec(_Empty())
    assert sections == []


def test_sections_from_spec_handles_missing_attributes() -> None:
    """spec with no sections or required_artifacts attribute falls back gracefully."""
    sections = sections_from_spec(object())
    assert sections == []
