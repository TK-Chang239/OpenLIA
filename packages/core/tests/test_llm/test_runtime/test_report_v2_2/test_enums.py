"""Closed enum invariants for report_v2_2."""

from __future__ import annotations

from openlia.llm.runtime.report_v2_2.enums import Category, Fidelity, VerifierIssueType


def test_category_count() -> None:
    assert len(Category) == 19, f"Expected 19 Category values, got {len(Category)}"


def test_verifier_issue_type_count() -> None:
    assert len(VerifierIssueType) == 18, (
        f"Expected 18 VerifierIssueType values, got {len(VerifierIssueType)}"
    )


def test_fidelity_count() -> None:
    assert len(Fidelity) == 3, f"Expected 3 Fidelity values, got {len(Fidelity)}"


def test_category_no_duplicates() -> None:
    values = [m.value for m in Category]
    assert len(values) == len(set(values)), "Category enum has duplicate values"


def test_verifier_issue_type_no_duplicates() -> None:
    values = [m.value for m in VerifierIssueType]
    assert len(values) == len(set(values)), "VerifierIssueType enum has duplicate values"


def test_fidelity_no_duplicates() -> None:
    values = [m.value for m in Fidelity]
    assert len(values) == len(set(values)), "Fidelity enum has duplicate values"


def test_category_values_are_nonempty_strings() -> None:
    for member in Category:
        assert isinstance(member.value, str), f"{member.name} value is not a string"
        assert member.value.strip(), f"{member.name} value is empty or whitespace"


def test_verifier_issue_type_values_are_nonempty_strings() -> None:
    for member in VerifierIssueType:
        assert isinstance(member.value, str), f"{member.name} value is not a string"
        assert member.value.strip(), f"{member.name} value is empty or whitespace"


def test_fidelity_values_are_nonempty_strings() -> None:
    for member in Fidelity:
        assert isinstance(member.value, str), f"{member.name} value is not a string"
        assert member.value.strip(), f"{member.name} value is empty or whitespace"


def test_fidelity_has_expected_members() -> None:
    assert Fidelity.HEADLINE == "headline"
    assert Fidelity.SUMMARY == "summary"
    assert Fidelity.FULL == "full"


def test_category_has_sector_wave1_members() -> None:
    """Wave 1 sector entries must be present per schema-and-skills §3.1."""
    assert Category.SECTOR_BANKS in Category
    assert Category.SECTOR_REITS in Category
    assert Category.SECTOR_PHARMA in Category
    assert Category.SECTOR_ENERGY in Category
    assert Category.SECTOR_INSURANCE in Category


def test_verifier_issue_type_has_four_materialization_types() -> None:
    """The 4 materialization types from artifact-injection §8 must be present."""
    assert VerifierIssueType.BLOCK_ARTIFACT_TOO_LARGE in VerifierIssueType
    assert VerifierIssueType.BLOCK_PLAN_ARTIFACT_MISSING in VerifierIssueType
    assert VerifierIssueType.BLOCK_SECTION_PLAN_INVALID in VerifierIssueType
    assert VerifierIssueType.BLOCK_HEADLINE_MISSING_QUANTITATIVE in VerifierIssueType
