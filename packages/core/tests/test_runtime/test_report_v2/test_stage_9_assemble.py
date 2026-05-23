"""Tests for the v2.2 assembler (build_report_v2).

The assembler returns a structured ReportV2 payload (not HTML) so the
frontend renders v2 reports through v1's React surface. These tests
assert on the typed structure.
"""

from __future__ import annotations

from datetime import UTC, datetime

from openlia.llm.runtime.report_v2.pipeline.stage_9_assemble import build_report_v2
from openlia.llm.runtime.report_v2.schemas.research_pool import Citation
from openlia.llm.runtime.report_v2.schemas.run_summary import RunSummary, TaskOutcome
from openlia.llm.runtime.report_v2.schemas.verification_history import (
    VerificationHistory,
    VerificationHistoryEntry,
)
from openlia.llm.runtime.report_v2.schemas.verifier_issue import VerifierIssue


class _StubTemplateSpec:
    """Mimics the relevant attributes of TemplateSpecV2 for the cover synth."""

    def __init__(
        self,
        template_id: str = "tmpl-001",
        template_name: str = "Standard Equity",
        report_type: str = "stock_initiation",
    ) -> None:
        self.template_id = template_id
        self.template_name = template_name
        self.report_type = report_type


def _make_run_summary(engine_version: str = "2.2") -> RunSummary:
    return RunSummary(
        engine_version=engine_version,
        template_id="tmpl-001",
        template_name="Standard Equity",
        outcomes=[
            TaskOutcome(task_type="section_draft", task_name="intro", status="OK"),
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


def test_build_emits_report_with_template_sections_preserved() -> None:
    sections = _make_sections("See [c:c1] for details.")
    report = build_report_v2(
        sections=sections,
        composer_inputs={"ticker": "AAPL", "prompt": "Initiate"},
        template_spec=_StubTemplateSpec(),
        pool_citations={"c1": _make_citation("c1")},
        run_summary=_make_run_summary(),
        verification_history=_make_verification_history(),
        dev_mode=True,
    )

    assert [s.id for s in report.sections] == ["intro"]
    assert report.sections[0].name == "Introduction"
    # Blocks are passed through unchanged so the frontend can dispatch on type.
    assert report.sections[0].blocks == [{"type": "prose", "text": "See [c:c1] for details."}]


def test_build_preserves_pool_citations_for_frontend_rail() -> None:
    sections = _make_sections("See [c:c1] for details.")
    cit = _make_citation("c1")
    report = build_report_v2(
        sections=sections,
        composer_inputs={"ticker": "AAPL"},
        template_spec=_StubTemplateSpec(),
        pool_citations={"c1": cit},
        run_summary=_make_run_summary(),
        verification_history=VerificationHistory(),
        dev_mode=False,
    )

    assert [c.id for c in report.citations] == ["c1"]
    assert report.citations[0].url == "https://example.com/source"


def test_build_omits_verification_history_when_dev_mode_false() -> None:
    report = build_report_v2(
        sections=_make_sections(),
        composer_inputs={"ticker": "AAPL"},
        template_spec=_StubTemplateSpec(),
        pool_citations={},
        run_summary=_make_run_summary(),
        verification_history=_make_verification_history(),
        dev_mode=False,
    )

    assert report.verification_history is None


def test_build_includes_verification_history_when_dev_mode_true() -> None:
    report = build_report_v2(
        sections=_make_sections(),
        composer_inputs={"ticker": "AAPL"},
        template_spec=_StubTemplateSpec(),
        pool_citations={},
        run_summary=_make_run_summary(),
        verification_history=_make_verification_history(),
        dev_mode=True,
    )

    assert report.verification_history is not None
    assert report.verification_history.total_issues_raised == 1


def test_build_carries_engine_version_and_template_ids() -> None:
    report = build_report_v2(
        sections=_make_sections(),
        composer_inputs={"ticker": "AAPL"},
        template_spec=_StubTemplateSpec(),
        pool_citations={},
        run_summary=_make_run_summary(engine_version="2.2"),
        verification_history=VerificationHistory(),
        dev_mode=False,
    )

    assert report.engine_version == "2.2"
    assert report.template_id == "tmpl-001"
    assert report.template_name == "Standard Equity"


def test_build_synthesises_cover_from_composer_inputs_and_template() -> None:
    report = build_report_v2(
        sections=_make_sections(),
        composer_inputs={"ticker": "aapl", "prompt": "Cover catalysts and risks."},
        template_spec=_StubTemplateSpec(
            template_name="Stock Initiation v2",
            report_type="stock_initiation",
        ),
        pool_citations={},
        run_summary=_make_run_summary(),
        verification_history=VerificationHistory(),
        dev_mode=False,
    )

    assert report.cover.ticker == "AAPL"
    assert report.cover.title == "AAPL"
    assert "stock_initiation" in (report.cover.eyebrow or "")
    assert report.cover.tagline == "Cover catalysts and risks."


def test_build_preserves_section_status_skip_and_degraded_reasons() -> None:
    sections = [
        {
            "id": "thesis",
            "name": "Thesis",
            "status": "OK",
            "blocks": [{"type": "prose", "text": "ok"}],
        },
        {
            "id": "macro",
            "name": "Macro",
            "status": "SKIPPED",
            "skip_reason": "condition X not met",
            "blocks": [
                {"type": "skip_banner", "section_name": "Macro", "reason": "X not met"}
            ],
        },
        {
            "id": "risks",
            "name": "Risks",
            "status": "DEGRADED",
            "degraded_reason": "verifier marked degraded",
            "blocks": [{"type": "prose", "text": "partial"}],
        },
    ]
    report = build_report_v2(
        sections=sections,
        composer_inputs={"ticker": "AAPL"},
        template_spec=_StubTemplateSpec(),
        pool_citations={},
        run_summary=_make_run_summary(),
        verification_history=VerificationHistory(),
        dev_mode=False,
    )

    by_id = {s.id: s for s in report.sections}
    assert by_id["thesis"].status == "OK"
    assert by_id["macro"].status == "SKIPPED"
    assert by_id["macro"].skip_reason == "condition X not met"
    assert by_id["risks"].status == "DEGRADED"
    assert by_id["risks"].degraded_reason == "verifier marked degraded"
