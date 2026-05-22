"""Tests for Stage 7a materialization: determinism, warnings, registry, dedup."""

from __future__ import annotations

from openlia.llm.runtime.report_v2_2.enums import Fidelity, VerifierIssueType
from openlia.llm.runtime.report_v2_2.materialize import (
    _HARD_CAP_CHARS,
    DefaultProjector,
    DefaultRenderer,
    MaterializationError,
    PlanResolutionError,
    _render_artifact,
    _render_table,
    materialize,
    materialize_section,
    register_projector,
    register_renderer,
    resolve_section_plan,
)
from openlia.llm.runtime.report_v2_2.section_plan import (
    PlannerOverrides,
    ReportSectionPlan,
    SectionArtifactRef,
    SectionPlan,
    SectionPlanOverride,
)

# ---- Helpers ----


def _make_report_plan(
    *,
    template_id: str = "t",
    sections: list[SectionPlan] | None = None,
) -> ReportSectionPlan:
    return ReportSectionPlan(template_id=template_id, sections=sections or [])


def _make_section(
    section_id: str,
    artifacts: list[SectionArtifactRef],
    drafter_brief: str | None = None,
) -> SectionPlan:
    return SectionPlan(
        section_id=section_id,
        title=section_id.replace("_", " ").title(),
        artifacts=artifacts,
        drafter_brief=drafter_brief,
    )


def _ref(artifact_id: str, fidelity: Fidelity = Fidelity.FULL) -> SectionArtifactRef:
    return SectionArtifactRef(artifact_id=artifact_id, fidelity=fidelity)


# ---- Determinism ----


def test_materialize_is_deterministic() -> None:
    plan = _make_report_plan(
        sections=[
            _make_section("s1", [_ref("a"), _ref("b", Fidelity.SUMMARY)]),
            _make_section("s2", [_ref("a", Fidelity.HEADLINE), _ref("c")]),
        ]
    )
    artifacts = {"a": {"value": 42, "rate": 0.05}, "b": {"score": 9}, "c": {"name": "MSFT"}}

    result1 = materialize(plan, artifacts)
    result2 = materialize(plan, artifacts)
    assert result1.markdown == result2.markdown


# ---- Missing artifact raises hard error ----


def test_materialize_missing_artifact_raises() -> None:
    plan = _make_report_plan(sections=[_make_section("s1", [_ref("ghost")])])
    try:
        materialize(plan, {})
        assert False, "Should have raised MaterializationError"
    except MaterializationError as exc:
        assert "ghost" in str(exc)


# ---- Orphan artifact is dropped silently ----


def test_materialize_orphan_artifact_not_in_output() -> None:
    plan = _make_report_plan(sections=[_make_section("s1", [_ref("a")])])
    artifacts = {"a": {"x": 1}, "orphan": {"y": 2}}
    result = materialize(plan, artifacts)
    assert "orphan" not in result.markdown
    assert "orphan" in result.orphan_artifact_ids


# ---- Highest-fidelity-wins dedup ----


def test_dedup_renders_at_highest_fidelity() -> None:
    """Artifact 'a' requested at HEADLINE in s1 and FULL in s2.
    Canonical site is s1 (first in order) but renders at FULL (highest anywhere).
    s2 gets a back-reference.
    """
    plan = _make_report_plan(
        sections=[
            _make_section("s1", [_ref("a", Fidelity.HEADLINE)]),
            _make_section("s2", [_ref("a", Fidelity.FULL)]),
        ]
    )
    artifacts = {"a": {"dcf_value": 312, "range_low": 260, "range_high": 365}}
    result = materialize(plan, artifacts)
    # Canonical render in s1 section at FULL (not HEADLINE).
    # s2 should contain a back-reference (no second full render).
    assert result.markdown.count("dcf_value") == 1  # rendered once only
    assert "above" in result.markdown  # back-reference present


def test_dedup_same_fidelity_back_reference_without_headline() -> None:
    """Artifact requested at FULL in both sections → s2 gets 'See ... above'."""
    plan = _make_report_plan(
        sections=[
            _make_section("s1", [_ref("x", Fidelity.FULL)]),
            _make_section("s2", [_ref("x", Fidelity.FULL)]),
        ]
    )
    artifacts = {"x": {"revenue": 100}}
    result = materialize(plan, artifacts)
    assert result.markdown.count("revenue") == 1
    assert "See" in result.markdown


# ---- Oversize artifact warning + truncation ----


def test_materialize_section_oversize_emits_warning_and_truncates() -> None:
    cap = _HARD_CAP_CHARS[Fidelity.FULL]
    big_value = "X" * (cap + 100)
    big_artifact = {"data": big_value}

    section = _make_section("s1", [_ref("big")])
    ms = materialize_section(section, {"big": big_artifact})

    # Must have a BLOCK_ARTIFACT_TOO_LARGE warning.
    warning_types = [w.type for w in ms.materialization_warnings]
    assert VerifierIssueType.BLOCK_ARTIFACT_TOO_LARGE in warning_types

    # Content must be truncated.
    for ra in ms.rendered_artifacts:
        assert ra.content.endswith("[truncated]")


# ---- Missing artifact in materialize_section emits warning ----


def test_materialize_section_missing_artifact_emits_warning() -> None:
    section = _make_section("s1", [_ref("missing")])
    ms = materialize_section(section, {})

    warning_types = [w.type for w in ms.materialization_warnings]
    assert VerifierIssueType.BLOCK_PLAN_ARTIFACT_MISSING in warning_types
    assert ms.rendered_artifacts == []


# ---- Override resolver ----


def test_resolve_section_plan_no_overrides() -> None:
    plan = _make_report_plan(sections=[_make_section("s1", [_ref("a")])])
    result = resolve_section_plan(plan, None)
    assert result.overrides_applied == []
    assert result.sections[0].section_id == "s1"


def test_resolve_add_override() -> None:
    plan = _make_report_plan(sections=[_make_section("s1", [_ref("a")])])
    overrides = PlannerOverrides(
        template_id="t",
        overrides=[
            SectionPlanOverride(
                section_id="s1", operation="add", artifact_id="b", fidelity=Fidelity.SUMMARY
            )
        ],
        rationale="test",
    )
    result = resolve_section_plan(plan, overrides)
    artifact_ids = [r.artifact_id for r in result.sections[0].artifacts]
    assert "b" in artifact_ids
    assert len(result.overrides_applied) == 1


def test_resolve_remove_override() -> None:
    plan = _make_report_plan(sections=[_make_section("s1", [_ref("a"), _ref("b")])])
    overrides = PlannerOverrides(
        template_id="t",
        overrides=[SectionPlanOverride(section_id="s1", operation="remove", artifact_id="b")],
        rationale="remove b",
    )
    result = resolve_section_plan(plan, overrides)
    artifact_ids = [r.artifact_id for r in result.sections[0].artifacts]
    assert "b" not in artifact_ids
    assert "a" in artifact_ids


def test_resolve_change_fidelity() -> None:
    plan = _make_report_plan(sections=[_make_section("s1", [_ref("a", Fidelity.FULL)])])
    overrides = PlannerOverrides(
        template_id="t",
        overrides=[
            SectionPlanOverride(
                section_id="s1",
                operation="change_fidelity",
                artifact_id="a",
                fidelity=Fidelity.SUMMARY,
            )
        ],
        rationale="downgrade",
    )
    result = resolve_section_plan(plan, overrides)
    assert result.sections[0].artifacts[0].fidelity == Fidelity.SUMMARY


def test_resolve_add_brief() -> None:
    plan = _make_report_plan(sections=[_make_section("s1", [_ref("a")])])
    overrides = PlannerOverrides(
        template_id="t",
        overrides=[
            SectionPlanOverride(
                section_id="s1",
                operation="add_brief",
                drafter_brief="Focus on upside.",
            )
        ],
        rationale="add brief",
    )
    result = resolve_section_plan(plan, overrides)
    assert result.sections[0].drafter_brief == "Focus on upside."


def test_resolve_unknown_section_raises() -> None:
    plan = _make_report_plan(sections=[_make_section("real_section", [_ref("a")])])
    overrides = PlannerOverrides(
        template_id="t",
        overrides=[
            SectionPlanOverride(
                section_id="ghost_section", operation="add_brief", drafter_brief="x"
            )
        ],
        rationale="test",
    )
    try:
        resolve_section_plan(plan, overrides)
        assert False, "Should raise PlanResolutionError"
    except PlanResolutionError as exc:
        assert "ghost_section" in str(exc)


def test_resolve_preserves_original_plan() -> None:
    """resolve_section_plan must not mutate the input plan (deep copy)."""
    section = _make_section("s1", [_ref("a")])
    plan = _make_report_plan(sections=[section])
    overrides = PlannerOverrides(
        template_id="t",
        overrides=[SectionPlanOverride(section_id="s1", operation="add_brief", drafter_brief="x")],
        rationale="test",
    )
    resolve_section_plan(plan, overrides)
    # Original must be untouched.
    assert plan.sections[0].drafter_brief is None


# ---- Default projector ----


def test_default_projector_full_returns_raw() -> None:
    proj = DefaultProjector()
    raw = {"a": 1, "b": [1, 2], "c": {"x": 3}}
    assert proj.project(raw, Fidelity.FULL) == raw


def test_default_projector_summary_returns_scalars() -> None:
    proj = DefaultProjector()
    raw = {"a": 1, "b": [1, 2], "c": 3.5}
    result = proj.project(raw, Fidelity.SUMMARY)
    assert "a" in result
    assert "c" in result
    assert "b" not in result  # list excluded


def test_default_projector_headline_returns_first_scalar() -> None:
    proj = DefaultProjector()
    raw = {"revenue": 100, "profit": 20}
    result = proj.project(raw, Fidelity.HEADLINE)
    assert len(result) == 1
    assert "revenue" in result


# ---- Default renderer ----


def test_default_renderer_bullet_list() -> None:
    rend = DefaultRenderer()
    projected = {"revenue": 100, "margin": 0.2}
    out = rend.render(projected, Fidelity.FULL)
    assert "revenue" in out
    assert "100" in out


def test_default_renderer_table_for_list_of_dicts() -> None:
    rend = DefaultRenderer()
    projected = {"rows": [{"ticker": "MSFT", "pe": 30}, {"ticker": "AAPL", "pe": 28}]}
    out = rend.render(projected, Fidelity.FULL)
    assert "ticker" in out
    assert "MSFT" in out
    assert "|" in out  # table markdown


def test_render_table_numeric_right_align() -> None:
    rows = [{"name": "a", "value": 10}, {"name": "b", "value": 20}]
    table = _render_table(rows)
    assert "---:" in table  # numeric col right-aligned
    assert "---" in table


# ---- projector / renderer registry ----


def test_register_and_use_custom_projector() -> None:
    class MockProjector:
        def project(self, raw, fidelity):
            return {"mocked": True}

    register_projector("__test_proj__", MockProjector())
    content, _ = _render_artifact("__test_proj__", {"x": 1}, Fidelity.FULL)
    assert "mocked" in content


def test_register_and_use_custom_renderer() -> None:
    class MockRenderer:
        def render(self, projected, fidelity):
            return "CUSTOM_RENDER"

    register_renderer("__test_rend__", MockRenderer())
    content, _ = _render_artifact("__test_rend__", {"x": 1}, Fidelity.FULL)
    assert content == "CUSTOM_RENDER"
