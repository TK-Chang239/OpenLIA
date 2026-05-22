"""Tests for SectionPlan / FidelityHint / HelperInvocation Pydantic shape + validation."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2_2.enums import Fidelity
from openlia.llm.runtime.report_v2_2.section_plan import (
    PlannerOverrides,
    ReportSectionPlan,
    SectionArtifactRef,
    SectionPlan,
    SectionPlanOverride,
)
from pydantic import ValidationError


def _make_plan(section_id: str = "valuation_dcf", artifacts: list | None = None) -> SectionPlan:
    if artifacts is None:
        artifacts = [SectionArtifactRef(artifact_id="dcf_output", fidelity=Fidelity.FULL)]
    return SectionPlan(section_id=section_id, title="DCF Valuation", artifacts=artifacts)


def _make_report_plan(*sections: SectionPlan) -> ReportSectionPlan:
    return ReportSectionPlan(
        template_id="stock_initiation_v2",
        sections=list(sections),
    )


# ---- SectionArtifactRef ----


def test_artifact_ref_required_fields() -> None:
    ref = SectionArtifactRef(artifact_id="foo", fidelity=Fidelity.SUMMARY)
    assert ref.artifact_id == "foo"
    assert ref.fidelity == Fidelity.SUMMARY
    assert ref.note is None


def test_artifact_ref_with_note() -> None:
    ref = SectionArtifactRef(artifact_id="foo", fidelity=Fidelity.HEADLINE, note="key figure")
    assert ref.note == "key figure"


def test_artifact_ref_invalid_fidelity() -> None:
    with pytest.raises(ValidationError):
        SectionArtifactRef(artifact_id="foo", fidelity="bogus")  # type: ignore[arg-type]


def test_artifact_ref_missing_artifact_id() -> None:
    with pytest.raises(ValidationError):
        SectionArtifactRef(fidelity=Fidelity.FULL)  # type: ignore[call-arg]


# ---- SectionPlan ----


def test_section_plan_minimal() -> None:
    plan = _make_plan()
    assert plan.section_id == "valuation_dcf"
    assert plan.drafter_brief is None


def test_section_plan_with_brief() -> None:
    plan = SectionPlan(
        section_id="exec",
        title="Executive Summary",
        artifacts=[],
        drafter_brief="Focus on the upside case.",
    )
    assert plan.drafter_brief == "Focus on the upside case."


def test_section_plan_empty_artifacts_allowed() -> None:
    plan = SectionPlan(section_id="exec", title="Exec", artifacts=[])
    assert plan.artifacts == []


# ---- ReportSectionPlan ----


def test_report_section_plan_basic() -> None:
    plan = _make_report_plan(_make_plan("s1"), _make_plan("s2"))
    assert plan.template_id == "stock_initiation_v2"
    assert len(plan.sections) == 2
    assert plan.overrides_applied == []


def test_report_section_plan_overrides_applied_defaults_empty() -> None:
    plan = _make_report_plan()
    assert isinstance(plan.overrides_applied, list)
    assert len(plan.overrides_applied) == 0


# ---- SectionPlanOverride ----


def test_override_add() -> None:
    ov = SectionPlanOverride(
        section_id="exec",
        operation="add",
        artifact_id="peer_panel",
        fidelity=Fidelity.SUMMARY,
    )
    assert ov.operation == "add"
    assert ov.artifact_id == "peer_panel"


def test_override_add_brief() -> None:
    ov = SectionPlanOverride(
        section_id="exec",
        operation="add_brief",
        drafter_brief="Emphasise relative valuation.",
    )
    assert ov.drafter_brief == "Emphasise relative valuation."
    assert ov.artifact_id is None


def test_override_invalid_operation() -> None:
    with pytest.raises(ValidationError):
        SectionPlanOverride(section_id="s", operation="delete_all")  # type: ignore[arg-type]


# ---- PlannerOverrides ----


def test_planner_overrides_basic() -> None:
    po = PlannerOverrides(
        template_id="stock_initiation_v2",
        overrides=[
            SectionPlanOverride(
                section_id="valuation_dcf",
                operation="change_fidelity",
                artifact_id="dcf_output",
                fidelity=Fidelity.SUMMARY,
            )
        ],
        rationale="User asked for shorter valuation section.",
    )
    assert len(po.overrides) == 1
    assert po.rationale.startswith("User")


def test_planner_overrides_empty_overrides() -> None:
    po = PlannerOverrides(
        template_id="t",
        overrides=[],
        rationale="no changes",
    )
    assert po.overrides == []
