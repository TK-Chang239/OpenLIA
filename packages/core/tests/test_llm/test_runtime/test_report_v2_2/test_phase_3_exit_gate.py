"""Phase 3 exit gate — helper count, skill-doc invariants, and verifier coverage.

This test is the machine-checkable part of the Phase 3 exit criteria defined in
planning/phase-progress.md. It fails loudly if:

  1. The total registered helper count drifts from the expected value (113).
  2. Any category deviates more than ±2 from the expected breakdown.
  3. Any of the 18 complex helpers from schema-and-skills §6 is either:
       a. Not registered in the runtime library_helpers registry, OR
       b. Registered but missing its skill_doc field (None or empty path).
  4. Any of the 18 parent VerifierIssueType values is unreachable (impl-plan §16).

If the helper count changes intentionally (e.g. a helper is added or removed),
update EXPECTED_TOTAL_HELPERS and EXPECTED_CATEGORY_BREAKDOWN to match the new
counts, and update planning/phase-progress.md per the update protocol.
"""

from __future__ import annotations

import pathlib

import pytest
from openlia.llm.runtime.report_v2_2.enums import VerifierIssueType
from openlia.llm.runtime.report_v2_2.materialize import MaterializedSection, RenderedArtifact
from openlia.llm.runtime.report_v2_2.section_plan import (
    ReportSectionPlan,
    SectionArtifactRef,
    SectionPlan,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers import list_helpers
from openlia.llm.runtime.report_v2_2.verifier import Verifier
from openlia.llm.runtime.report_v2_2.verifier_models import VerifierIssue

# ---------------------------------------------------------------------------
# Expected totals — update when helpers are added / removed intentionally
# ---------------------------------------------------------------------------

EXPECTED_TOTAL_HELPERS = 113

# Per impl plan §16 / category breakdown from `list_helpers()` at Phase 3 close.
# Tolerance: ±2 per category.
EXPECTED_CATEGORY_BREAKDOWN: dict[str, int] = {
    "adapter": 20,
    "alternative_valuation": 3,
    "business_quality": 34,
    "comparables": 1,
    "dcf": 7,
    "decision": 7,
    "forensic": 8,
    "llm_nlp": 7,
    "output": 4,
    "risk_macro": 9,
    "saas_kpis": 2,
    "sector_banks": 1,
    "sector_energy": 1,
    "sector_insurance": 1,
    "sector_pharma": 1,
    "sector_reits": 1,
    "signals": 3,
    "statement_integrity": 3,
}

_CATEGORY_TOLERANCE = 2

# ---------------------------------------------------------------------------
# The closed list of 18 complex helpers from schema-and-skills §6.
# Updating this list requires also updating §6 and impl plan §16.
# ---------------------------------------------------------------------------

COMPLEX_HELPERS_REQUIRING_SKILL_DOCS: list[str] = [
    "dcf_engine",
    "cost_of_capital_builder",
    "comparables_run",
    "ddm_family",
    "justified_multiples",
    "sotp_builder",
    "price_target_blender",
    "rating_band_assigner",
    "rnpv_pipeline",
    "banks_sector_panel",
    "reit_valuation_panel",
    "ep_sector_panel",
    "insurance_valuation_panel",
    "forensic_panel",
    "statement_integrity_bundle",
    "insider_signal_panel",
    "historical_multiple_trends",
    "workbook_builder",
]

_SKILLS_DIR = (
    pathlib.Path(__file__).resolve().parents[4]
    / "src"
    / "openlia"
    / "llm"
    / "runtime"
    / "report_v2_2"
    / "tools"
    / "library_helpers"
    / "skills"
)


# ---------------------------------------------------------------------------
# Helper count gate
# ---------------------------------------------------------------------------


def test_total_helper_count() -> None:
    """Total registered helper count must equal EXPECTED_TOTAL_HELPERS.

    If you intentionally added or removed helpers, update EXPECTED_TOTAL_HELPERS
    in this file and note the change in planning/phase-progress.md.
    """
    helpers = list_helpers()
    actual = len(helpers)
    assert actual == EXPECTED_TOTAL_HELPERS, (
        f"Expected {EXPECTED_TOTAL_HELPERS} registered helpers, got {actual}. "
        f"If this is intentional, update EXPECTED_TOTAL_HELPERS in "
        f"test_phase_3_exit_gate.py and planning/phase-progress.md."
    )


def test_category_breakdown_within_tolerance() -> None:
    """Each category's helper count must be within ±2 of the expected value."""
    helpers = list_helpers()
    actual: dict[str, int] = {}
    for h in helpers:
        cat = h.schema.directory.category
        actual[cat] = actual.get(cat, 0) + 1

    failures: list[str] = []

    # Check expected categories against actuals.
    for category, expected_count in EXPECTED_CATEGORY_BREAKDOWN.items():
        got = actual.get(category, 0)
        diff = abs(got - expected_count)
        if diff > _CATEGORY_TOLERANCE:
            failures.append(
                f"  {category}: expected {expected_count} ±{_CATEGORY_TOLERANCE}, got {got}"
            )

    # Check for unexpected categories (present in actuals but not expected).
    for category in actual:
        if category not in EXPECTED_CATEGORY_BREAKDOWN:
            failures.append(
                f"  {category}: unexpected category with {actual[category]} helpers "
                f"(add to EXPECTED_CATEGORY_BREAKDOWN if intentional)"
            )

    assert not failures, "Category breakdown deviates from expected (tolerance ±{}):\n{}".format(
        _CATEGORY_TOLERANCE, "\n".join(failures)
    )


# ---------------------------------------------------------------------------
# Skill-doc invariants for the 18 complex helpers
# ---------------------------------------------------------------------------


def test_complex_helper_list_is_eighteen() -> None:
    """Sanity: the closed §6 list must be exactly 18 entries."""
    assert len(COMPLEX_HELPERS_REQUIRING_SKILL_DOCS) == 18, (
        f"Expected exactly 18 complex helpers per schema-and-skills §6, "
        f"got {len(COMPLEX_HELPERS_REQUIRING_SKILL_DOCS)}. "
        f"Update §6, impl plan §16, and phase-progress.md if changing this."
    )


@pytest.mark.parametrize("helper_name", COMPLEX_HELPERS_REQUIRING_SKILL_DOCS)
def test_complex_helper_is_registered(helper_name: str) -> None:
    """Each of the 18 complex helpers must be registered in the runtime registry.

    Phase 3 exit gate: all 18 must be registered (unlike Phase 0-2 where
    helpers landed incrementally). Fails loudly if any are absent.
    """
    registered_names = {h.schema.directory.name for h in list_helpers()}
    assert helper_name in registered_names, (
        f"Complex helper {helper_name!r} is NOT registered in the v2.2 library_helpers registry. "
        f"Per schema-and-skills §6, all 18 complex helpers must be registered at Phase 3 close. "
        f"Either register the helper or remove it from COMPLEX_HELPERS_REQUIRING_SKILL_DOCS."
    )


@pytest.mark.parametrize("helper_name", COMPLEX_HELPERS_REQUIRING_SKILL_DOCS)
def test_complex_helper_has_skill_doc_set(helper_name: str) -> None:
    """Each registered complex helper must have skill_doc field set (non-None, non-empty path).

    Phase 3 exit gate: fails loudly (not a warning or skip) when a complex helper
    is registered without its skill doc wired in. Per impl plan §8 cross-cutting
    requirement 5: every §6 helper must ship its skill doc in the same PR.
    """
    from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

    registered = get_helper(helper_name)
    if registered is None:
        pytest.fail(
            f"Complex helper {helper_name!r} is not registered. "
            f"Run test_complex_helper_is_registered first."
        )

    skill_doc = registered.schema.skill_doc
    assert skill_doc is not None, (
        f"Complex helper {helper_name!r} has skill_doc=None. "
        f"Per schema-and-skills §6, all 18 complex helpers must have their skill doc "
        f"wired via SkillDocRef(path=...). Set skill_doc= in the helper's _SCHEMA definition."
    )
    assert skill_doc.path, (
        f"Complex helper {helper_name!r} has skill_doc with empty path. "
        f"Set a non-empty path in SkillDocRef(path='skills/{helper_name}.md', ...)."
    )


@pytest.mark.parametrize("helper_name", COMPLEX_HELPERS_REQUIRING_SKILL_DOCS)
def test_complex_helper_skill_doc_file_exists(helper_name: str) -> None:
    """The skill doc file referenced by each complex helper's skill_doc must exist on disk."""
    from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

    registered = get_helper(helper_name)
    if registered is None or not registered.schema.skill_doc:
        pytest.skip(f"{helper_name}: no skill_doc set; covered by other tests")

    # Skill doc paths are relative to the library_helpers directory.
    # Skill doc paths are relative to the library_helpers directory.
    skill_path = _SKILLS_DIR / pathlib.Path(registered.schema.skill_doc.path).name
    assert skill_path.exists(), (
        f"Skill doc for {helper_name!r} declared at "
        f"{registered.schema.skill_doc.path!r} but file not found at {skill_path}. "
        f"Create the file or fix the path in SkillDocRef."
    )
    assert skill_path.stat().st_size > 100, (
        f"Skill doc for {helper_name!r} at {skill_path} appears empty (< 100 bytes)."
    )


# ---------------------------------------------------------------------------
# Phase 2 exit gate: all 18 VerifierIssueType parent values must be reachable
# Per impl-plan §16: "18 parent issue types reachable" is the Phase 2 exit gate.
# ---------------------------------------------------------------------------

# Helpers shared by the reachability fixtures below.


def _make_ms(
    section_id: str = "s1",
    rendered_artifacts: list[RenderedArtifact] | None = None,
    warnings: list[VerifierIssue] | None = None,
) -> MaterializedSection:
    return MaterializedSection(
        section_id=section_id,
        title="Test Section",
        rendered_artifacts=rendered_artifacts or [],
        materialization_warnings=warnings or [],
    )


def _make_ra(artifact_id: str) -> RenderedArtifact:
    from openlia.llm.runtime.report_v2_2.enums import Fidelity

    return RenderedArtifact(
        artifact_id=artifact_id,
        artifact_type=artifact_id,
        helper_name="__test__",
        fidelity=Fidelity.FULL,
        content="content",
        raw_data={},
    )


def _warn(issue_type: VerifierIssueType) -> VerifierIssue:
    return VerifierIssue(
        type=issue_type,
        detail_code="test",
        severity="blocking",
        helper="__test__",
        detail="test",
    )


def test_all_18_verifier_issue_types_reachable() -> None:
    """Phase 2 exit gate (impl-plan §16): all 18 VerifierIssueType parent values must be
    reachable via actual Verifier.verify() calls or materialization_warnings carry-through.

    This test builds minimal synthetic inputs that trigger each issue type and asserts
    that VerifierIssueType has exactly 18 members — no more, no less.
    """
    verifier = Verifier()
    produced: set[VerifierIssueType] = set()

    # CONTENT_TOO_SPARSE — min_words not met.
    issues = verifier.verify(_make_ms(), "short", {}, min_words=500)
    produced.update(i.type for i in issues)

    # DIRECTIVE_UNMET — word count out of budget range.
    issues = verifier.verify(_make_ms(), " ".join(["w"] * 10), {}, word_budget=500, tolerance_pct=5)
    produced.update(i.type for i in issues)

    # ARTIFACT_MISSING — rendered artifact not referenced in draft.
    issues = verifier.verify(_make_ms(rendered_artifacts=[_make_ra("art1")]), "no mention", {})
    produced.update(i.type for i in issues)

    # NUMERIC_INCONSISTENCY — number in draft absent from helper outputs.
    issues = verifier.verify(_make_ms(), "Revenue was $999.99 billion.", {"other": {"x": 1}})
    produced.update(i.type for i in issues)

    # BLOCK_PLAN_ARTIFACT_MISSING — carried from materialization_warnings.
    w = _warn(VerifierIssueType.BLOCK_PLAN_ARTIFACT_MISSING)
    issues = verifier.verify(_make_ms(warnings=[w]), "draft", {})
    produced.update(i.type for i in issues)

    # BLOCK_ARTIFACT_TOO_LARGE — carried from materialization_warnings.
    w = _warn(VerifierIssueType.BLOCK_ARTIFACT_TOO_LARGE)
    issues = verifier.verify(_make_ms(warnings=[w]), "draft", {})
    produced.update(i.type for i in issues)

    # BLOCK_SECTION_PLAN_INVALID — carried from materialization_warnings.
    w = _warn(VerifierIssueType.BLOCK_SECTION_PLAN_INVALID)
    issues = verifier.verify(_make_ms(warnings=[w]), "draft", {})
    produced.update(i.type for i in issues)

    # BLOCK_HEADLINE_MISSING_QUANTITATIVE — carried from materialization_warnings.
    w = _warn(VerifierIssueType.BLOCK_HEADLINE_MISSING_QUANTITATIVE)
    issues = verifier.verify(_make_ms(warnings=[w]), "draft", {})
    produced.update(i.type for i in issues)

    # BLOCK_SHAPE — carried from materialization_warnings.
    w = _warn(VerifierIssueType.BLOCK_SHAPE)
    issues = verifier.verify(_make_ms(warnings=[w]), "draft", {})
    produced.update(i.type for i in issues)

    # TOMBSTONE — carried from materialization_warnings.
    w = _warn(VerifierIssueType.TOMBSTONE)
    issues = verifier.verify(_make_ms(warnings=[w]), "draft", {})
    produced.update(i.type for i in issues)

    # CITATION_MISSING — carried from materialization_warnings.
    w = _warn(VerifierIssueType.CITATION_MISSING)
    issues = verifier.verify(_make_ms(warnings=[w]), "draft", {})
    produced.update(i.type for i in issues)

    # FACTUAL_INCONSISTENCY — carried from materialization_warnings.
    w = _warn(VerifierIssueType.FACTUAL_INCONSISTENCY)
    issues = verifier.verify(_make_ms(warnings=[w]), "draft", {})
    produced.update(i.type for i in issues)

    # REQUIRED_PARAM_UNRESOLVABLE — carried from materialization_warnings.
    w = _warn(VerifierIssueType.REQUIRED_PARAM_UNRESOLVABLE)
    issues = verifier.verify(_make_ms(warnings=[w]), "draft", {})
    produced.update(i.type for i in issues)

    # YEAR_SLIP — FY year token with drift >= 2 from as_of_year.
    issues = verifier.verify(_make_ms(), "FY2015 revenue was strong.", {}, as_of_year=2025)
    produced.update(i.type for i in issues)

    # CITATION_UNRESOLVED — [^marker] with no matching artifact.
    issues = verifier.verify(_make_ms(), "See [^ghost_artifact].", {})
    produced.update(i.type for i in issues)

    # CITATION_ORPHANED — rendered artifact never cited.
    ms = _make_ms(rendered_artifacts=[_make_ra("orphan_art")])
    issues = verifier.verify(ms, "No citation here.", {})
    produced.update(i.type for i in issues)

    # HELPER_UNAVAILABLE — section_plan references unregistered helper.
    plan = ReportSectionPlan(
        template_id="test",
        sections=[
            SectionPlan(
                section_id="s1",
                title="S1",
                artifacts=[SectionArtifactRef(artifact_id="__no_such_helper__", fidelity="full")],
            )
        ],
    )
    issues = verifier.verify(_make_ms(section_id="s1"), "draft", {}, section_plan=plan)
    produced.update(i.type for i in issues)

    # INCOHERENT_PROSE — run-on sentence > 60 words.
    long_sent = " ".join(["word"] * 65) + "."
    issues = verifier.verify(_make_ms(), long_sent, {})
    produced.update(i.type for i in issues)

    # Assert all 18 enum values were produced.
    all_types = set(VerifierIssueType)
    missing = all_types - produced
    assert not missing, (
        f"Phase 2 exit gate (impl-plan §16): {len(missing)} VerifierIssueType value(s) "
        f"were never produced by any Verifier.verify() call: "
        f"{sorted(str(t) for t in missing)}. "
        f"Each of the 18 parent issue types must be reachable."
    )

    assert len(all_types) == 18, (
        f"VerifierIssueType must have exactly 18 values per impl-plan §16, "
        f"got {len(all_types)}: {sorted(str(t) for t in all_types)}"
    )
