"""Tests for Stage 8 verifier: word count, min words, missing/oversize artifacts,
year slip, citation resolution, helper availability, and prose coherence."""

from __future__ import annotations

from openlia.llm.runtime.report_v2_2.enums import Fidelity, VerifierIssueType
from openlia.llm.runtime.report_v2_2.materialize import MaterializedSection, RenderedArtifact
from openlia.llm.runtime.report_v2_2.section_plan import (
    ReportSectionPlan,
    SectionArtifactRef,
    SectionPlan,
)
from openlia.llm.runtime.report_v2_2.verifier import Verifier
from openlia.llm.runtime.report_v2_2.verifier_models import VerifierIssue


def _make_section(
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


def _make_artifact(artifact_id: str, content: str) -> RenderedArtifact:
    return RenderedArtifact(
        artifact_id=artifact_id,
        artifact_type=artifact_id,
        helper_name="test_helper",
        fidelity=Fidelity.FULL,
        content=content,
        raw_data={"revenue": 100},
    )


def _warning(issue_type: VerifierIssueType, detail_code: str = "test") -> VerifierIssue:
    return VerifierIssue(
        type=issue_type,
        detail_code=detail_code,
        severity="blocking",
        helper="__test__",
        detail="test issue",
    )


# ---- Word count: too sparse ----


def test_min_words_not_met() -> None:
    verifier = Verifier()
    # Draft with only 10 words, min_words = 200.
    draft = "This is a very short draft. Only ten words here."
    section = _make_section()
    issues = verifier.verify(section, draft, {}, min_words=200)

    issue_types = [i.type for i in issues]
    assert VerifierIssueType.CONTENT_TOO_SPARSE in issue_types

    sparse = next(i for i in issues if i.type == VerifierIssueType.CONTENT_TOO_SPARSE)
    assert sparse.detail_code == "min_words_not_met"
    assert sparse.severity == "blocking"


def test_min_words_met_no_issue() -> None:
    verifier = Verifier()
    draft = " ".join(["word"] * 250)
    section = _make_section()
    issues = verifier.verify(section, draft, {}, min_words=200)
    sparse_issues = [i for i in issues if i.type == VerifierIssueType.CONTENT_TOO_SPARSE]
    assert len(sparse_issues) == 0


# ---- Word count: out of tolerance range ----


def test_word_count_out_of_range() -> None:
    verifier = Verifier()
    # Budget 500 words, tolerance 10% → range [450, 550].
    # Draft has only 100 words → out of range.
    draft = " ".join(["word"] * 100)
    section = _make_section()
    issues = verifier.verify(section, draft, {}, word_budget=500, tolerance_pct=10)

    directive_issues = [i for i in issues if i.type == VerifierIssueType.DIRECTIVE_UNMET]
    assert len(directive_issues) == 1
    assert directive_issues[0].detail_code == "word_count_out_of_range"
    assert directive_issues[0].severity == "advisory"


def test_word_count_within_tolerance_no_issue() -> None:
    verifier = Verifier()
    draft = " ".join(["word"] * 490)  # within 500 ± 10% = [450, 550]
    section = _make_section()
    issues = verifier.verify(section, draft, {}, word_budget=500, tolerance_pct=10)
    directive_issues = [i for i in issues if i.type == VerifierIssueType.DIRECTIVE_UNMET]
    assert len(directive_issues) == 0


# ---- Carry-through of materialization warnings ----


def test_block_plan_artifact_missing_carried() -> None:
    warn = _warning(VerifierIssueType.BLOCK_PLAN_ARTIFACT_MISSING, detail_code="ghost")
    section = _make_section(warnings=[warn])
    verifier = Verifier()
    issues = verifier.verify(section, "some draft", {})
    assert any(i.type == VerifierIssueType.BLOCK_PLAN_ARTIFACT_MISSING for i in issues)


def test_block_artifact_too_large_carried() -> None:
    warn = _warning(VerifierIssueType.BLOCK_ARTIFACT_TOO_LARGE, detail_code="oversize")
    section = _make_section(warnings=[warn])
    verifier = Verifier()
    issues = verifier.verify(section, "some draft", {})
    assert any(i.type == VerifierIssueType.BLOCK_ARTIFACT_TOO_LARGE for i in issues)


# ---- Artifact citation check ----


def test_artifact_not_referenced_emits_advisory() -> None:
    art = _make_artifact("dcf_output", "DCF content here")
    section = _make_section(rendered_artifacts=[art])
    # Draft doesn't mention dcf_output.
    draft = "General prose without citing the artifact."
    verifier = Verifier()
    issues = verifier.verify(section, draft, {})
    advisory = [i for i in issues if i.type == VerifierIssueType.ARTIFACT_MISSING]
    assert len(advisory) == 1


def test_artifact_referenced_no_advisory() -> None:
    art = _make_artifact("dcf_output", "DCF content here")
    section = _make_section(rendered_artifacts=[art])
    # Draft mentions the artifact_id.
    draft = "As shown in dcf_output, the fair value is $312."
    verifier = Verifier()
    issues = verifier.verify(section, draft, {})
    advisory = [i for i in issues if i.type == VerifierIssueType.ARTIFACT_MISSING]
    assert len(advisory) == 0


# ---- Clean case ----


def test_clean_draft_returns_empty_issues() -> None:
    art = _make_artifact("dcf_output", "- **dcf_value**: $312\n- **wacc**: 9.8%")
    section = _make_section(rendered_artifacts=[art])
    draft = (
        "dcf_output shows DCF fair value = $312, wacc = 9.8%. "
        + " ".join(["Analysis."] * 60)  # ~120 words
    )
    verifier = Verifier()
    issues = verifier.verify(section, draft, {"dcf_output": {"dcf_value": 312, "wacc": 9.8}})
    # No blocking issues expected for a well-formed draft.
    blocking = [i for i in issues if i.severity == "blocking"]
    assert len(blocking) == 0


# ---- Multiple issues can coexist ----


def test_multiple_issues_accumulate() -> None:
    warn = _warning(VerifierIssueType.BLOCK_PLAN_ARTIFACT_MISSING, detail_code="ghost")
    section = _make_section(warnings=[warn])
    # Also: min_words not met.
    draft = "Short draft."
    verifier = Verifier()
    issues = verifier.verify(section, draft, {}, min_words=300)
    issue_types = {i.type for i in issues}
    assert VerifierIssueType.BLOCK_PLAN_ARTIFACT_MISSING in issue_types
    assert VerifierIssueType.CONTENT_TOO_SPARSE in issue_types


# ---- YEAR_SLIP ----


def test_year_slip_detected_when_year_mismatch() -> None:
    """FY year token drifting >= 2 years from as_of_year triggers YEAR_SLIP."""
    section = _make_section()
    # Draft mentions FY2019 but report as_of_year is 2025 — drift = 6 years.
    draft = "Revenue grew strongly in FY2019, marking a record year."
    verifier = Verifier()
    issues = verifier.verify(section, draft, {}, as_of_year=2025)
    year_slip = [i for i in issues if i.type == VerifierIssueType.YEAR_SLIP]
    assert len(year_slip) >= 1
    assert year_slip[0].detail_code == "fy_year_drift"


def test_year_slip_not_triggered_for_adjacent_year() -> None:
    """FY year within 1 year of as_of_year must NOT trigger YEAR_SLIP."""
    section = _make_section()
    draft = "Revenue grew in FY2024, up 12% year-over-year."
    verifier = Verifier()
    issues = verifier.verify(section, draft, {}, as_of_year=2025)
    year_slip = [i for i in issues if i.type == VerifierIssueType.YEAR_SLIP]
    assert len(year_slip) == 0


def test_year_slip_skipped_when_no_as_of_year_and_no_artifacts() -> None:
    """Without as_of_year and no artifact year hints, check is skipped cleanly."""
    section = _make_section()
    draft = "Results for FY2019 were strong."
    verifier = Verifier()
    issues = verifier.verify(section, draft, {}, as_of_year=None)
    year_slip = [i for i in issues if i.type == VerifierIssueType.YEAR_SLIP]
    assert len(year_slip) == 0


# ---- CITATION_UNRESOLVED ----


def test_citation_unresolved_when_marker_has_no_artifact() -> None:
    """[^foo] citation with no matching rendered artifact emits CITATION_UNRESOLVED."""
    section = _make_section(rendered_artifacts=[])
    draft = "As noted in [^dcf_output], fair value is $312."
    verifier = Verifier()
    issues = verifier.verify(section, draft, {})
    unresolved = [i for i in issues if i.type == VerifierIssueType.CITATION_UNRESOLVED]
    assert len(unresolved) == 1
    assert unresolved[0].detail_code == "marker_no_artifact"
    assert "dcf_output" in unresolved[0].detail


def test_citation_unresolved_not_triggered_when_artifact_matches() -> None:
    """[^art_id] with a matching rendered artifact must NOT emit CITATION_UNRESOLVED."""
    art = _make_artifact("dcf_output", "DCF content")
    section = _make_section(rendered_artifacts=[art])
    draft = "As detailed in [^dcf_output], the valuation stands at $312."
    verifier = Verifier()
    issues = verifier.verify(section, draft, {})
    unresolved = [i for i in issues if i.type == VerifierIssueType.CITATION_UNRESOLVED]
    assert len(unresolved) == 0


# ---- CITATION_ORPHANED ----


def test_citation_orphaned_when_artifact_never_referenced() -> None:
    """Artifact in rendered_artifacts but never cited via [^...] emits CITATION_ORPHANED."""
    art = _make_artifact("dcf_output", "DCF content")
    section = _make_section(rendered_artifacts=[art])
    # Draft does NOT cite [^dcf_output].
    draft = "The company looks attractive based on our analysis."
    verifier = Verifier()
    issues = verifier.verify(section, draft, {})
    orphaned = [i for i in issues if i.type == VerifierIssueType.CITATION_ORPHANED]
    assert len(orphaned) == 1
    assert orphaned[0].detail_code == "artifact_never_cited"
    assert "dcf_output" in orphaned[0].detail


def test_citation_orphaned_not_triggered_when_artifact_is_cited() -> None:
    """Artifact cited via [^art_id] must NOT emit CITATION_ORPHANED."""
    art = _make_artifact("dcf_output", "DCF content")
    section = _make_section(rendered_artifacts=[art])
    draft = "Per [^dcf_output], the DCF value is $312."
    verifier = Verifier()
    issues = verifier.verify(section, draft, {})
    orphaned = [i for i in issues if i.type == VerifierIssueType.CITATION_ORPHANED]
    assert len(orphaned) == 0


# ---- HELPER_UNAVAILABLE ----


def test_helper_unavailable_when_section_references_unknown() -> None:
    """SectionPlan referencing an unregistered helper emits HELPER_UNAVAILABLE."""
    section = _make_section(section_id="valuation_dcf")
    plan = ReportSectionPlan(
        template_id="test_tpl",
        sections=[
            SectionPlan(
                section_id="valuation_dcf",
                title="DCF Valuation",
                artifacts=[
                    SectionArtifactRef(
                        artifact_id="__nonexistent_helper_xyz__",
                        fidelity=Fidelity.FULL,
                    )
                ],
            )
        ],
    )
    draft = "Some prose."
    verifier = Verifier()
    issues = verifier.verify(section, draft, {}, section_plan=plan)
    unavailable = [i for i in issues if i.type == VerifierIssueType.HELPER_UNAVAILABLE]
    assert len(unavailable) == 1
    assert unavailable[0].detail_code == "helper_not_registered"
    assert "__nonexistent_helper_xyz__" in unavailable[0].detail


def test_helper_unavailable_not_triggered_when_no_section_plan() -> None:
    """Without a section_plan arg, HELPER_UNAVAILABLE check is skipped."""
    section = _make_section()
    draft = "Some prose."
    verifier = Verifier()
    issues = verifier.verify(section, draft, {}, section_plan=None)
    unavailable = [i for i in issues if i.type == VerifierIssueType.HELPER_UNAVAILABLE]
    assert len(unavailable) == 0


# ---- INCOHERENT_PROSE ----


def test_incoherent_prose_detected_for_run_on_sentence() -> None:
    """Sentence exceeding 60 words triggers INCOHERENT_PROSE with run_on_sentence detail."""
    section = _make_section()
    # Construct a sentence with 70 words.
    long_sentence = " ".join(["The company reported record revenue in the quarter"] * 14) + "."
    draft = f"Introduction paragraph.\n\n{long_sentence}\n\nConclusion."
    verifier = Verifier()
    issues = verifier.verify(section, draft, {})
    incoherent = [i for i in issues if i.type == VerifierIssueType.INCOHERENT_PROSE]
    run_on = [i for i in incoherent if i.detail_code == "run_on_sentence"]
    assert len(run_on) >= 1


def test_incoherent_prose_detected_for_repeated_words() -> None:
    """Word repeated > 5 times consecutively triggers INCOHERENT_PROSE."""
    section = _make_section()
    draft = "The revenue revenue revenue revenue revenue revenue grew last year."
    verifier = Verifier()
    issues = verifier.verify(section, draft, {})
    incoherent = [i for i in issues if i.type == VerifierIssueType.INCOHERENT_PROSE]
    repeated = [i for i in incoherent if i.detail_code == "repeated_consecutive_words"]
    assert len(repeated) >= 1


def test_clean_prose_no_incoherent_issues() -> None:
    """Well-formed prose without run-ons, repetition, or verbless paragraphs is clean."""
    section = _make_section()
    draft = (
        "The company reported strong revenue growth.\n\n"
        "Operating margins expanded by 200 basis points year-over-year.\n\n"
        "Management raised full-year guidance above consensus estimates."
    )
    verifier = Verifier()
    issues = verifier.verify(section, draft, {})
    incoherent = [i for i in issues if i.type == VerifierIssueType.INCOHERENT_PROSE]
    assert len(incoherent) == 0
