from __future__ import annotations

from unittest.mock import MagicMock

from openlia.llm.runtime.report_v2.pipeline.verifier_llm import LLMVerifier
from openlia.llm.runtime.report_v2.schemas.verifier_issue import VerifierIssue


def _make_pool(strands: dict | None = None):
    pool = MagicMock()
    pool.findings_by_strand = strands or {"macro": "GDP growth remains solid."}
    return pool


def _make_artifacts(items: list | None = None):
    if items is None:
        art = MagicMock()
        art.spec.id = "dcf_model"
        art.spec.description = "DCF valuation model"
        return [art]
    return items


def test_llm_verifier_returns_parsed_issues():
    llm = MagicMock()
    llm.call.return_value = {
        "issues": [
            {
                "issue_type": "content_too_sparse",
                "severity": "blocker",
                "evidence": "Only one sentence provided.",
                "suggested_fix": "Expand with three supporting data points.",
            }
        ]
    }
    verifier = LLMVerifier(llm)
    issues = verifier.verify_section(
        section_id="s1",
        blocks=[{"type": "prose", "text": "Revenue grew."}],
        research_pool=_make_pool(),
        model_artifacts=_make_artifacts(),
        directive="Provide a detailed analysis of revenue trends.",
    )
    assert len(issues) == 1
    issue = issues[0]
    assert isinstance(issue, VerifierIssue)
    assert issue.issue_type == "content_too_sparse"
    assert issue.section_id == "s1"
    assert issue.detector == "llm"
    assert issue.severity == "blocker"


def test_llm_verifier_returns_empty_list_on_error():
    llm = MagicMock()
    llm.call.side_effect = RuntimeError("LLM timeout")
    verifier = LLMVerifier(llm)
    issues = verifier.verify_section(
        section_id="s2",
        blocks=[{"type": "prose", "text": "Revenue grew."}],
        research_pool=_make_pool(),
        model_artifacts=_make_artifacts(),
        directive="Analyze margins.",
    )
    assert issues == []
