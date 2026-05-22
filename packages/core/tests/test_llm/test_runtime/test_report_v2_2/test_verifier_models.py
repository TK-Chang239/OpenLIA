"""VerifierIssue model tests."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2_2.enums import VerifierIssueType
from openlia.llm.runtime.report_v2_2.verifier_models import VerifierIssue
from pydantic import ValidationError


def test_instantiate_with_all_fields() -> None:
    issue = VerifierIssue(
        type=VerifierIssueType.BLOCK_SHAPE,
        detail_code="tv_pct_high",
        severity="advisory",
        helper="dcf_engine",
        detail="Terminal value is 87% of EV; exceeds typical threshold.",
    )
    assert issue.type == VerifierIssueType.BLOCK_SHAPE
    assert issue.detail_code == "tv_pct_high"
    assert issue.severity == "advisory"
    assert issue.helper == "dcf_engine"
    assert "87%" in issue.detail


def test_detail_code_defaults_to_none() -> None:
    issue = VerifierIssue(
        type=VerifierIssueType.NUMERIC_INCONSISTENCY,
        helper="dcf_engine",
        detail="Numbers don't add up.",
    )
    assert issue.detail_code is None


def test_severity_defaults_to_blocking() -> None:
    issue = VerifierIssue(
        type=VerifierIssueType.TOMBSTONE,
        helper="forensic_panel",
        detail="Helper returned no output.",
    )
    assert issue.severity == "blocking"


def test_parent_type_with_materialization_issue() -> None:
    issue = VerifierIssue(
        type=VerifierIssueType.BLOCK_PLAN_ARTIFACT_MISSING,
        detail_code=None,
        severity="blocking",
        helper="stage_7a",
        detail="Artifact 'dcf_base_valuation' referenced in section_plan not in Stage 6 output.",
    )
    assert issue.type == VerifierIssueType.BLOCK_PLAN_ARTIFACT_MISSING


def test_invalid_severity_raises() -> None:
    with pytest.raises(ValidationError):
        VerifierIssue(
            type=VerifierIssueType.BLOCK_SHAPE,
            severity="critical",  # not in Literal["blocking", "advisory"]
            helper="test",
            detail="Bad severity.",
        )


def test_invalid_type_raises() -> None:
    with pytest.raises(ValidationError):
        VerifierIssue(
            type="not_a_real_type",  # type: ignore[arg-type]
            helper="test",
            detail="Bad type.",
        )


def test_missing_helper_raises() -> None:
    with pytest.raises(ValidationError):
        VerifierIssue(
            type=VerifierIssueType.BLOCK_SHAPE,
            detail="Missing helper field.",
        )  # type: ignore[call-arg]


def test_missing_detail_raises() -> None:
    with pytest.raises(ValidationError):
        VerifierIssue(
            type=VerifierIssueType.BLOCK_SHAPE,
            helper="some_helper",
        )  # type: ignore[call-arg]


def test_all_parent_types_usable() -> None:
    """Every VerifierIssueType can be instantiated as the type field."""
    for issue_type in VerifierIssueType:
        issue = VerifierIssue(
            type=issue_type,
            helper="test_helper",
            detail=f"Test issue of type {issue_type.value}.",
        )
        assert issue.type == issue_type
