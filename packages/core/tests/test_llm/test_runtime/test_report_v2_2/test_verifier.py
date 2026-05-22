"""Tests for Stage 8 verifier: word count, min words, missing/oversize artifacts."""

from __future__ import annotations

from openlia.llm.runtime.report_v2_2.enums import Fidelity, VerifierIssueType
from openlia.llm.runtime.report_v2_2.materialize import MaterializedSection, RenderedArtifact
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
