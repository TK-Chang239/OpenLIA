from __future__ import annotations

from openlia.llm.runtime.report_v2.rendering.verification_history_renderer import (
    _RES_CLASS,
    aggregate_history,
    render_verification_history,
)
from openlia.llm.runtime.report_v2.schemas.verification_history import (
    VerificationHistory,
    VerificationHistoryEntry,
)
from openlia.llm.runtime.report_v2.schemas.verifier_issue import VerifierIssue


def make_issue(
    itype: str = "tombstone",
    sid: str = "s1",
    severity: str = "blocker",
) -> VerifierIssue:
    return VerifierIssue(
        issue_type=itype,
        section_id=sid,
        severity=severity,
        evidence="...",
        detector="llm",
    )


# ---------------------------------------------------------------------------
# aggregate_history tests
# ---------------------------------------------------------------------------


def test_aggregate_classifies_resolved_vs_persisted() -> None:
    issue_a = make_issue("tombstone", "s1")
    issue_b = make_issue("year_slip", "s2")
    raised = [("id_a", issue_a), ("id_b", issue_b)]
    resolved_ids: set[str] = {"id_a"}
    persisted_ids: set[str] = {"id_b"}
    resolution_rounds: dict[str, int] = {"id_a": 1}

    history = aggregate_history(raised, resolved_ids, persisted_ids, resolution_rounds)

    assert len(history.entries) == 2
    by_id = {e.issue.issue_type: e for e in history.entries}
    assert by_id["tombstone"].final_resolution == "resolved"
    assert by_id["tombstone"].resolved_in_round == 1
    assert by_id["year_slip"].final_resolution == "persisted_degraded"
    assert by_id["year_slip"].resolved_in_round is None


def test_aggregate_warning_marks_still_open() -> None:
    issue = make_issue("content_too_sparse", "s3", severity="warning")
    raised = [("id_w", issue)]

    history = aggregate_history(raised, set(), set(), {})

    assert len(history.entries) == 1
    assert history.entries[0].final_resolution == "still_open"


def test_aggregate_blocker_not_resolved_not_persisted_marks_persisted_failed() -> None:
    issue = make_issue("block_shape", "s4", severity="blocker")
    raised = [("id_f", issue)]

    history = aggregate_history(raised, set(), set(), {})

    assert history.entries[0].final_resolution == "persisted_failed"


def test_aggregate_totals_are_correct() -> None:
    issues = [
        ("r1", make_issue("tombstone", "s1")),
        ("r2", make_issue("year_slip", "s2")),
        ("w1", make_issue("content_too_sparse", "s3", severity="warning")),
    ]
    resolved_ids = {"r1"}
    persisted_ids = {"r2"}
    resolution_rounds = {"r1": 1}

    h = aggregate_history(issues, resolved_ids, persisted_ids, resolution_rounds)

    assert h.total_issues_raised == 3
    assert h.resolved_on_first_retry == 1
    assert h.persisted_to_degraded == 1
    assert h.warnings_open == 1


# ---------------------------------------------------------------------------
# render_verification_history tests
# ---------------------------------------------------------------------------


def test_render_omitted_when_dev_mode_false() -> None:
    issue = make_issue("tombstone")
    entry = VerificationHistoryEntry(
        issue=issue,
        raised_at_round=0,
        final_resolution="resolved",
        resolved_in_round=1,
    )
    h = VerificationHistory(entries=[entry], total_issues_raised=1)

    result = render_verification_history(h, dev_mode=False)

    assert result == ""


def test_render_includes_all_entries_when_dev_mode_true() -> None:
    issue = make_issue("tombstone")
    entry = VerificationHistoryEntry(
        issue=issue,
        raised_at_round=0,
        final_resolution="resolved",
        resolved_in_round=1,
    )
    h = VerificationHistory(entries=[entry], total_issues_raised=1)

    result = render_verification_history(h, dev_mode=True)

    assert "Verification History" in result
    assert "tombstone" in result


def test_render_applies_status_class_to_rows() -> None:
    entries = []
    resolutions = ["resolved", "persisted_degraded", "persisted_failed", "still_open"]
    severities = ["blocker", "blocker", "blocker", "warning"]
    for i, (res, sev) in enumerate(zip(resolutions, severities, strict=True)):
        issue = make_issue("tombstone", f"s{i}", severity=sev)
        entry = VerificationHistoryEntry(
            issue=issue,
            raised_at_round=0,
            final_resolution=res,
            resolved_in_round=1 if res == "resolved" else None,
        )
        entries.append(entry)

    h = VerificationHistory(entries=entries, total_issues_raised=len(entries))
    result = render_verification_history(h, dev_mode=True)

    for css_class in _RES_CLASS.values():
        assert css_class in result


def test_html_escape_in_evidence_prevents_xss() -> None:
    issue = VerifierIssue(
        issue_type="tombstone",
        section_id="s1",
        severity="blocker",
        evidence="<script>alert(1)</script>",
        suggested_fix="<b>fix</b>",
        detector="llm",
    )
    entry = VerificationHistoryEntry(
        issue=issue,
        raised_at_round=0,
        final_resolution="resolved",
        resolved_in_round=1,
    )
    h = VerificationHistory(entries=[entry], total_issues_raised=1)

    result = render_verification_history(h, dev_mode=True)

    assert "<script>" not in result
    assert "&lt;script&gt;" in result
