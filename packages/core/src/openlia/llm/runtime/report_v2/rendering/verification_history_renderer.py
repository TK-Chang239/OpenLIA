from __future__ import annotations

import html

from openlia.llm.runtime.report_v2.schemas.verification_history import (
    FinalResolution,
    VerificationHistory,
    VerificationHistoryEntry,
)
from openlia.llm.runtime.report_v2.schemas.verifier_issue import VerifierIssue

_RES_CLASS: dict[str, str] = {
    "resolved": "resolved",
    "persisted_degraded": "degraded",
    "persisted_failed": "failed",
    "still_open": "warning-open",
}


def aggregate_history(
    raised: list[tuple[str, VerifierIssue]],
    resolved_ids: set[str],
    persisted_ids: set[str],
    resolution_rounds: dict[str, int],
) -> VerificationHistory:
    entries: list[VerificationHistoryEntry] = []
    total = len(raised)
    resolved_first = 0
    resolved_subsequent = 0
    degraded = 0
    warnings_open = 0

    for issue_id, issue in raised:
        final_resolution: FinalResolution
        resolved_in_round: int | None = None

        if issue_id in resolved_ids:
            final_resolution = "resolved"
            resolved_in_round = resolution_rounds.get(issue_id)
            if resolved_in_round == 1:
                resolved_first += 1
            else:
                resolved_subsequent += 1
        elif issue_id in persisted_ids:
            final_resolution = "persisted_degraded"
            degraded += 1
        elif issue.severity == "warning":
            final_resolution = "still_open"
            warnings_open += 1
        else:
            final_resolution = "persisted_failed"

        entries.append(
            VerificationHistoryEntry(
                issue=issue,
                raised_at_round=0,
                final_resolution=final_resolution,
                resolved_in_round=resolved_in_round,
            )
        )

    return VerificationHistory(
        entries=entries,
        total_issues_raised=total,
        resolved_on_first_retry=resolved_first,
        resolved_on_subsequent_retry=resolved_subsequent,
        persisted_to_degraded=degraded,
        warnings_open=warnings_open,
    )


def render_verification_history(h: VerificationHistory, dev_mode: bool) -> str:
    if not dev_mode:
        return ""

    rows = []
    for entry in h.entries:
        issue = entry.issue
        css = _RES_CLASS[entry.final_resolution]
        section_id = html.escape(issue.section_id or "")
        issue_type = html.escape(issue.issue_type)
        severity = html.escape(issue.severity)
        detector = html.escape(issue.detector)
        raised = str(entry.raised_at_round)
        resolution = html.escape(entry.final_resolution)
        evidence = html.escape(issue.evidence)
        suggested_fix = html.escape(issue.suggested_fix or "")
        rows.append(
            f'<tr class="{css}">'
            f"<td>{section_id}</td>"
            f"<td>{issue_type}</td>"
            f"<td>{severity}</td>"
            f"<td>{detector}</td>"
            f"<td>{raised}</td>"
            f"<td>{resolution}</td>"
            f"<td>{evidence}</td>"
            f"<td>{suggested_fix}</td>"
            f"</tr>"
        )

    summary = (
        f"Total raised: {h.total_issues_raised} | "
        f"Resolved first retry: {h.resolved_on_first_retry} | "
        f"Resolved subsequent: {h.resolved_on_subsequent_retry} | "
        f"Degraded: {h.persisted_to_degraded} | "
        f"Warnings open: {h.warnings_open}"
    )

    table_header = (
        "<tr>"
        "<th>Section</th>"
        "<th>Issue</th>"
        "<th>Severity</th>"
        "<th>Detector</th>"
        "<th>Raised</th>"
        "<th>Resolution</th>"
        "<th>Evidence</th>"
        "<th>Suggested fix</th>"
        "</tr>"
    )

    rows_html = "\n".join(rows)

    return (
        '<section id="verification_history" class="dev-only">'
        "<h2>Verification History</h2>"
        f"<p>{summary}</p>"
        "<table>"
        f"<thead>{table_header}</thead>"
        f"<tbody>{rows_html}</tbody>"
        "</table>"
        "</section>"
    )
