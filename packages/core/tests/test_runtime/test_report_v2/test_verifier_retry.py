from __future__ import annotations

from unittest.mock import MagicMock

from openlia.llm.runtime.report_v2.pipeline.stage_8_verify import (
    Verifier,
)
from openlia.llm.runtime.report_v2.schemas.verifier_issue import VerifierIssue


def _make_pool():
    pool = MagicMock()
    pool.findings_by_strand = {"macro": "GDP solid."}
    return pool


def _make_artifacts():
    art = MagicMock()
    art.spec.id = "dcf"
    art.spec.description = "DCF model"
    return [art]


def _clean_blocks():
    return [{"type": "prose", "text": "Revenue grew 10% YoY in FY2025."}]


def _tombstone_blocks():
    return [{"type": "prose", "text": "[placeholder] data goes here"}]


def _make_llm_verifier_clean():
    v = MagicMock()
    v.verify_section.return_value = []
    return v


def _make_llm_verifier_with_issue():
    v = MagicMock()
    v.verify_section.return_value = [
        VerifierIssue(
            issue_type="content_too_sparse",
            section_id="s1",
            severity="blocker",
            evidence="Only one sentence.",
            suggested_fix="Add more detail.",
            detector="llm",
        )
    ]
    return v


def test_resolved_on_retry_1():
    """Drafter fixes tombstone on first retry — result is OK after round 1."""
    call_count = 0

    def redraft(section_id, blockers, retry_context):
        nonlocal call_count
        call_count += 1
        return _clean_blocks()

    drafter = MagicMock()
    drafter.redraft_with_feedback.side_effect = redraft

    llm_verifier = _make_llm_verifier_clean()

    verifier = Verifier(
        llm_verifier=llm_verifier,
        drafter=drafter,
        section_directives={"s1": "Analyze revenue trends."},
    )

    result = verifier.verify_with_retry(
        section_id="s1",
        blocks=_tombstone_blocks(),
        research_pool=_make_pool(),
        model_artifacts=_make_artifacts(),
        citations={},
        pool_citation_ids=set(),
        required_artifact_ids=set(),
        embedded_artifact_ids=set(),
        retry_context={},
    )

    assert result.final_status == "OK"
    assert len(result.rounds) == 2  # round 0 failed, round 1 passed
    assert drafter.redraft_with_feedback.call_count == 1


def test_persists_to_degraded_after_max_retries():
    """Drafter never fixes the issue — DEGRADED after MAX_RETRIES rounds."""
    drafter = MagicMock()
    drafter.redraft_with_feedback.return_value = _tombstone_blocks()

    llm_verifier = _make_llm_verifier_clean()

    verifier = Verifier(
        llm_verifier=llm_verifier,
        drafter=drafter,
        section_directives={"s1": "Analyze revenue trends."},
    )

    result = verifier.verify_with_retry(
        section_id="s1",
        blocks=_tombstone_blocks(),
        research_pool=_make_pool(),
        model_artifacts=_make_artifacts(),
        citations={},
        pool_citation_ids=set(),
        required_artifact_ids=set(),
        embedded_artifact_ids=set(),
        retry_context={},
    )

    assert result.final_status == "DEGRADED"
    # convergence will trigger on round 1==round 0 so only 2 rounds expected
    # (convergence check fires before MAX_RETRIES is reached)
    assert len(result.rounds) >= 2


def test_convergence_degraded_early():
    """Two consecutive rounds with identical blocker signatures trigger early DEGRADED."""
    # Use an LLM-detected blocker on clean blocks (no deterministic issues)
    # so LLM verifier is called each round
    llm_verifier = _make_llm_verifier_with_issue()

    drafter = MagicMock()
    # Drafter returns same clean blocks each time — LLM still complains each round
    drafter.redraft_with_feedback.return_value = _clean_blocks()

    verifier = Verifier(
        llm_verifier=llm_verifier,
        drafter=drafter,
        section_directives={"s1": "Provide detailed analysis."},
    )

    result = verifier.verify_with_retry(
        section_id="s1",
        blocks=_clean_blocks(),
        research_pool=_make_pool(),
        model_artifacts=_make_artifacts(),
        citations={},
        pool_citation_ids=set(),
        required_artifact_ids=set(),
        embedded_artifact_ids=set(),
        retry_context={},
    )

    assert result.final_status == "DEGRADED"
    # Should stop early — convergence fires after 2 rounds with same signature
    assert len(result.rounds) == 2
    # Drafter called exactly once (between round 0 and round 1)
    assert drafter.redraft_with_feedback.call_count == 1
