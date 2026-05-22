"""Tests for template_defaults.py (three-source fidelity merge).

Covers:
- SEED_DEFAULTS has correct structure for stock_initiation_v2
- load_template_defaults returns SEED_DEFAULTS fallback for stock_initiation_v2
- load_template_defaults raises FileNotFoundError for unknown template
- load_template_defaults loads from a YAML file when present
- resolve_section_plan (re-exported) merges three layers in correct precedence:
    artifact default < template section override < planner override
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from openlia.llm.runtime.report_v2_2.enums import Fidelity
from openlia.llm.runtime.report_v2_2.materialize import PlanResolutionError
from openlia.llm.runtime.report_v2_2.section_plan import (
    PlannerOverrides,
    ReportSectionPlan,
    SectionArtifactRef,
    SectionPlan,
    SectionPlanOverride,
)
from openlia.llm.runtime.report_v2_2.template_defaults import (
    SEED_DEFAULTS,
    load_template_defaults,
    resolve_section_plan,
)

# ---------------------------------------------------------------------------
# SEED_DEFAULTS structure
# ---------------------------------------------------------------------------


def test_seed_defaults_template_id() -> None:
    assert SEED_DEFAULTS.template_id == "stock_initiation_v2"


def test_seed_defaults_has_four_sections() -> None:
    assert len(SEED_DEFAULTS.sections) == 4


def test_seed_defaults_section_ids() -> None:
    ids = {s.section_id for s in SEED_DEFAULTS.sections}
    assert ids == {"executive_summary", "investment_thesis", "valuation_dcf", "valuation_comps"}


def test_seed_defaults_executive_summary_artifacts_at_headline() -> None:
    exec_section = next(s for s in SEED_DEFAULTS.sections if s.section_id == "executive_summary")
    for art in exec_section.artifacts:
        assert art.fidelity == Fidelity.HEADLINE, (
            f"Artifact {art.artifact_id!r} in executive_summary should be HEADLINE, "
            f"got {art.fidelity}"
        )


def test_seed_defaults_valuation_dcf_has_full_dcf_artifact() -> None:
    dcf_section = next(s for s in SEED_DEFAULTS.sections if s.section_id == "valuation_dcf")
    dcf_ref = next(
        (a for a in dcf_section.artifacts if a.artifact_id == "dcf_base_valuation"), None
    )
    assert dcf_ref is not None
    assert dcf_ref.fidelity == Fidelity.FULL


# ---------------------------------------------------------------------------
# load_template_defaults
# ---------------------------------------------------------------------------


def test_load_template_defaults_fallback_to_seed() -> None:
    # No YAML on disk — should return SEED_DEFAULTS for stock_initiation_v2
    result = load_template_defaults("stock_initiation_v2")
    assert result.template_id == "stock_initiation_v2"
    assert len(result.sections) == 4


def test_load_template_defaults_unknown_template_raises() -> None:
    with pytest.raises(FileNotFoundError, match="pharma_v2_2"):
        load_template_defaults("pharma_v2_2")


def test_load_template_defaults_from_yaml_file() -> None:
    yaml_content = """
template_id: test_template_v1
sections:
  - section_id: overview
    title: Overview
    artifacts:
      - artifact_id: summary_artifact
        fidelity: summary
  - section_id: deep_dive
    title: Deep Dive
    artifacts:
      - artifact_id: full_artifact
        fidelity: full
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        template_dir = root / "test_template_v1"
        template_dir.mkdir()
        (template_dir / "section_plan_defaults.yaml").write_text(yaml_content)

        result = load_template_defaults("test_template_v1", root=root)

    assert result.template_id == "test_template_v1"
    assert len(result.sections) == 2
    assert result.sections[0].section_id == "overview"
    assert result.sections[0].artifacts[0].fidelity == Fidelity.SUMMARY
    assert result.sections[1].artifacts[0].fidelity == Fidelity.FULL


# ---------------------------------------------------------------------------
# resolve_section_plan: 3-layer precedence
# ---------------------------------------------------------------------------


def _make_plan(artifacts: list[tuple[str, Fidelity]]) -> ReportSectionPlan:
    """Helper: build a single-section plan with the given artifact fidelities."""
    return ReportSectionPlan(
        template_id="test_template",
        sections=[
            SectionPlan(
                section_id="valuation",
                title="Valuation",
                artifacts=[
                    SectionArtifactRef(artifact_id=aid, fidelity=fid) for aid, fid in artifacts
                ],
            )
        ],
    )


def test_resolve_no_overrides_returns_template_defaults_unchanged() -> None:
    plan = _make_plan([("dcf_output", Fidelity.FULL)])
    resolved = resolve_section_plan(plan, None)
    assert resolved.sections[0].artifacts[0].fidelity == Fidelity.FULL
    assert resolved.overrides_applied == []


def test_resolve_change_fidelity_override_wins_over_template() -> None:
    """Planner override (layer 3) must win over template default (layer 2)."""
    plan = _make_plan([("dcf_output", Fidelity.SUMMARY)])  # template default: SUMMARY
    overrides = PlannerOverrides(
        template_id="test_template",
        overrides=[
            SectionPlanOverride(
                section_id="valuation",
                operation="change_fidelity",
                artifact_id="dcf_output",
                fidelity=Fidelity.FULL,  # planner upgrades to FULL
            )
        ],
        rationale="User requested full DCF.",
    )
    resolved = resolve_section_plan(plan, overrides)
    artifact = resolved.sections[0].artifacts[0]
    assert artifact.fidelity == Fidelity.FULL
    assert len(resolved.overrides_applied) == 1


def test_resolve_add_override_appends_artifact() -> None:
    plan = _make_plan([("dcf_output", Fidelity.FULL)])
    overrides = PlannerOverrides(
        template_id="test_template",
        overrides=[
            SectionPlanOverride(
                section_id="valuation",
                operation="add",
                artifact_id="sensitivity_grid",
                fidelity=Fidelity.SUMMARY,
            )
        ],
        rationale="Adding sensitivity analysis.",
    )
    resolved = resolve_section_plan(plan, overrides)
    artifact_ids = [a.artifact_id for a in resolved.sections[0].artifacts]
    assert "sensitivity_grid" in artifact_ids
    assert "dcf_output" in artifact_ids


def test_resolve_remove_override_removes_artifact() -> None:
    plan = _make_plan([("dcf_output", Fidelity.FULL), ("peer_panel", Fidelity.SUMMARY)])
    overrides = PlannerOverrides(
        template_id="test_template",
        overrides=[
            SectionPlanOverride(
                section_id="valuation",
                operation="remove",
                artifact_id="peer_panel",
            )
        ],
        rationale="Removing peer panel from valuation section.",
    )
    resolved = resolve_section_plan(plan, overrides)
    artifact_ids = [a.artifact_id for a in resolved.sections[0].artifacts]
    assert "peer_panel" not in artifact_ids
    assert "dcf_output" in artifact_ids


def test_resolve_add_brief_override() -> None:
    plan = _make_plan([("dcf_output", Fidelity.FULL)])
    overrides = PlannerOverrides(
        template_id="test_template",
        overrides=[
            SectionPlanOverride(
                section_id="valuation",
                operation="add_brief",
                drafter_brief="Emphasise downside sensitivity.",
            )
        ],
        rationale="User asked for downside focus.",
    )
    resolved = resolve_section_plan(plan, overrides)
    assert resolved.sections[0].drafter_brief == "Emphasise downside sensitivity."


def test_resolve_multiple_overrides_applied_in_order() -> None:
    plan = _make_plan([("dcf_output", Fidelity.HEADLINE), ("peer_panel", Fidelity.SUMMARY)])
    overrides = PlannerOverrides(
        template_id="test_template",
        overrides=[
            SectionPlanOverride(
                section_id="valuation",
                operation="change_fidelity",
                artifact_id="dcf_output",
                fidelity=Fidelity.FULL,
            ),
            SectionPlanOverride(
                section_id="valuation",
                operation="change_fidelity",
                artifact_id="peer_panel",
                fidelity=Fidelity.FULL,
            ),
        ],
        rationale="Both artifacts to full.",
    )
    resolved = resolve_section_plan(plan, overrides)
    for art in resolved.sections[0].artifacts:
        assert art.fidelity == Fidelity.FULL
    assert len(resolved.overrides_applied) == 2


def test_resolve_unknown_section_raises_plan_resolution_error() -> None:
    plan = _make_plan([("dcf_output", Fidelity.FULL)])
    overrides = PlannerOverrides(
        template_id="test_template",
        overrides=[
            SectionPlanOverride(
                section_id="nonexistent_section",
                operation="add_brief",
                drafter_brief="Should fail.",
            )
        ],
        rationale="Bad override.",
    )
    with pytest.raises(PlanResolutionError, match="nonexistent_section"):
        resolve_section_plan(plan, overrides)


def test_resolve_does_not_mutate_original_plan() -> None:
    """resolve_section_plan must deep-copy; original must be unchanged."""
    plan = _make_plan([("dcf_output", Fidelity.SUMMARY)])
    overrides = PlannerOverrides(
        template_id="test_template",
        overrides=[
            SectionPlanOverride(
                section_id="valuation",
                operation="change_fidelity",
                artifact_id="dcf_output",
                fidelity=Fidelity.FULL,
            )
        ],
        rationale="Upgrade fidelity.",
    )
    _ = resolve_section_plan(plan, overrides)
    # Original must be unchanged.
    assert plan.sections[0].artifacts[0].fidelity == Fidelity.SUMMARY


def test_resolve_with_seed_defaults() -> None:
    """Use actual SEED_DEFAULTS as layer 2; override one artifact fidelity."""
    overrides = PlannerOverrides(
        template_id="stock_initiation_v2",
        overrides=[
            SectionPlanOverride(
                section_id="valuation_comps",
                operation="change_fidelity",
                artifact_id="historical_multiple_trends",
                fidelity=Fidelity.FULL,
            )
        ],
        rationale="User requested full peer trend analysis.",
    )
    resolved = resolve_section_plan(SEED_DEFAULTS, overrides)
    comps_section = next(s for s in resolved.sections if s.section_id == "valuation_comps")
    hist = next(a for a in comps_section.artifacts if a.artifact_id == "historical_multiple_trends")
    assert hist.fidelity == Fidelity.FULL
    # Original should still be SUMMARY in SEED_DEFAULTS.
    orig_comps = next(s for s in SEED_DEFAULTS.sections if s.section_id == "valuation_comps")
    orig_hist = next(
        a for a in orig_comps.artifacts if a.artifact_id == "historical_multiple_trends"
    )
    assert orig_hist.fidelity == Fidelity.SUMMARY
