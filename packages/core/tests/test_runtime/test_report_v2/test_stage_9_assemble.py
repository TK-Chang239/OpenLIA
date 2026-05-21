"""Tests for O5 stage 9 assembler.

Task O5 — Equity Research v2.2 pipeline.
"""

from __future__ import annotations

from datetime import UTC, datetime

# Import via the stage module (re-export)
from openlia.llm.runtime.report_v2.pipeline.stage_9_assemble import assemble_report
from openlia.llm.runtime.report_v2.schemas.research_pool import Citation
from openlia.llm.runtime.report_v2.schemas.run_summary import RunSummary, TaskOutcome
from openlia.llm.runtime.report_v2.schemas.verification_history import (
    VerificationHistory,
    VerificationHistoryEntry,
)
from openlia.llm.runtime.report_v2.schemas.verifier_issue import VerifierIssue

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run_summary(engine_version: str = "2.2") -> RunSummary:
    return RunSummary(
        engine_version=engine_version,
        template_id="tmpl-001",
        template_name="Standard Equity",
        outcomes=[
            TaskOutcome(
                task_type="section_draft",
                task_name="intro",
                status="OK",
            )
        ],
    )


def _make_verification_history() -> VerificationHistory:
    issue = VerifierIssue(
        issue_type="content_too_sparse",
        section_id="intro",
        severity="warning",
        evidence="Too short",
        suggested_fix="Expand prose",
        detector="deterministic",
    )
    entry = VerificationHistoryEntry(
        issue=issue,
        raised_at_round=1,
        final_resolution="resolved",
        resolved_in_round=2,
    )
    return VerificationHistory(
        entries=[entry],
        total_issues_raised=1,
        resolved_on_first_retry=0,
        resolved_on_subsequent_retry=1,
        persisted_to_degraded=0,
        warnings_open=0,
    )


def _make_citation(cid: str = "c1") -> Citation:
    return Citation(
        id=cid,
        source_type="tool_call",
        tool="eodhd",
        url="https://example.com/source",
        title="Sample Source Title",
        retrieved_at=datetime(2026, 5, 21, tzinfo=UTC),
    )


def _make_sections(prose: str = "Hello world") -> list[dict]:
    return [
        {
            "id": "intro",
            "name": "Introduction",
            "blocks": [{"type": "prose", "text": prose}],
        }
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_assemble_emits_html_with_correct_section_order() -> None:
    """Template sections < Sources < Run Summary < Verification History (dev_mode=True)."""
    sections = _make_sections("See [c:c1] for details.")
    pool_citations = {"c1": _make_citation("c1")}
    run_summary = _make_run_summary()
    verification_history = _make_verification_history()

    html = assemble_report(
        sections=sections,
        pool_citations=pool_citations,
        run_summary=run_summary,
        verification_history=verification_history,
        dev_mode=True,
    )

    intro_pos = html.index('<section id="intro">')
    sources_pos = html.index('<section id="sources">')
    run_summary_pos = html.index('<section id="run_summary">')
    verification_pos = html.index('<section id="verification_history"')

    assert intro_pos < sources_pos < run_summary_pos < verification_pos


def test_assemble_substitutes_citation_markers_in_section_prose() -> None:
    """[c:c1] marker in prose is replaced with [1] superscript + cite-1 anchor."""
    sections = _make_sections("See [c:c1] for details.")
    pool_citations = {"c1": _make_citation("c1")}
    run_summary = _make_run_summary()
    verification_history = VerificationHistory()

    html = assemble_report(
        sections=sections,
        pool_citations=pool_citations,
        run_summary=run_summary,
        verification_history=verification_history,
        dev_mode=False,
    )

    # Substituted inline superscript
    assert "[1]" in html
    # Cite anchor in the sources footer
    assert "cite-1" in html


def test_assemble_omits_verification_history_when_dev_mode_false() -> None:
    """dev_mode=False → Verification History section is absent."""
    sections = _make_sections()
    pool_citations = {}
    run_summary = _make_run_summary()
    verification_history = _make_verification_history()

    html = assemble_report(
        sections=sections,
        pool_citations=pool_citations,
        run_summary=run_summary,
        verification_history=verification_history,
        dev_mode=False,
    )

    assert "Verification History" not in html


def test_assemble_omits_sources_when_no_citations() -> None:
    """pool_citations={} → no <section id="sources"> in output."""
    sections = _make_sections("No citations here.")
    pool_citations: dict = {}
    run_summary = _make_run_summary()
    verification_history = VerificationHistory()

    html = assemble_report(
        sections=sections,
        pool_citations=pool_citations,
        run_summary=run_summary,
        verification_history=verification_history,
        dev_mode=False,
    )

    assert '<section id="sources">' not in html


def test_assemble_includes_engine_version_in_footer() -> None:
    """Engine version appears in the article footer."""
    sections = _make_sections()
    pool_citations = {}
    run_summary = _make_run_summary(engine_version="2.2")
    verification_history = VerificationHistory()

    html = assemble_report(
        sections=sections,
        pool_citations=pool_citations,
        run_summary=run_summary,
        verification_history=verification_history,
        dev_mode=False,
    )

    assert "Engine v2.2" in html


def test_assemble_wraps_each_section_with_id_and_name_header() -> None:
    """Each section is wrapped in <section id=...><h2>name</h2>..."""
    sections = [
        {
            "id": "intro",
            "name": "Introduction",
            "blocks": [{"type": "prose", "text": "Opening paragraph."}],
        }
    ]
    pool_citations = {}
    run_summary = _make_run_summary()
    verification_history = VerificationHistory()

    html = assemble_report(
        sections=sections,
        pool_citations=pool_citations,
        run_summary=run_summary,
        verification_history=verification_history,
        dev_mode=False,
    )

    assert '<section id="intro"><h2>Introduction</h2>' in html
