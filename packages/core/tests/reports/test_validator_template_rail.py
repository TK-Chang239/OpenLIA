"""PR 0.0 — validator template-rail tests.

Proves that ``enforce_required_rail`` reads required labels from the caller
(template-declared) rather than a hardcoded dict, and that missing labels /
absent declarations behave correctly.
"""

from __future__ import annotations

import pytest
from openlia.reports.validator import (
    ReportValidationError,
    enforce_required_rail,
    validate_report_payload,
)


def _base_payload() -> dict:
    return {
        "schema_version": "2.0",
        "department": "equity_research",
        "generated_at": "2026-04-11T09:30:00Z",
        "cover": {
            "title": "ACME Corp",
            "subtitle": "Q1 2026",
            "tagline": "Test report.",
        },
        "sections": [
            {
                "id": "fin",
                "title": "Financials",
                "blocks": [{"type": "text", "content": "Revenue grew 10%."}],
            }
        ],
        "rail": {
            "verdict": {"rating": "Buy", "target": "$100", "as_of": "2026-05-22"},
            "quick_stats": [
                {"label": "custom_a", "value": "1"},
                {"label": "custom_b", "value": "2"},
            ],
        },
    }


def test_no_required_labels_skips_rail_validation() -> None:
    """Template declares no rail.required_quick_stats — validation skipped silently."""
    schema = validate_report_payload(_base_payload())
    # Should not raise even though the rail has no standard labels.
    enforce_required_rail(schema, department_id="custom_dept")
    enforce_required_rail(schema, department_id="custom_dept", required_labels=None)


def test_custom_template_with_declared_labels_passes_when_present() -> None:
    """Template declares required_quick_stats: [custom_a, custom_b] — both present."""
    schema = validate_report_payload(_base_payload())
    enforce_required_rail(
        schema,
        department_id="custom_dept",
        required_labels=["custom_a", "custom_b"],
    )


def test_custom_template_with_declared_labels_fails_when_missing() -> None:
    """Template declares required_quick_stats: [custom_a, custom_b] — custom_b absent."""
    payload = _base_payload()
    payload["rail"]["quick_stats"] = [{"label": "custom_a", "value": "1"}]
    schema = validate_report_payload(payload)
    with pytest.raises(ReportValidationError) as exc:
        enforce_required_rail(
            schema,
            department_id="custom_dept",
            required_labels=["custom_a", "custom_b"],
        )
    msgs = " ".join(m for _, m in exc.value.errors)
    assert "'custom_b'" in msgs
    assert "'custom_a'" not in msgs


def test_custom_template_fails_when_verdict_absent_and_labels_declared() -> None:
    """Verdict check fires whenever required_labels is non-None."""
    payload = _base_payload()
    payload["rail"]["verdict"] = None
    schema = validate_report_payload(payload)
    with pytest.raises(ReportValidationError) as exc:
        enforce_required_rail(
            schema,
            department_id="custom_dept",
            required_labels=["custom_a"],
        )
    assert any("rail.verdict" in p for p, _ in exc.value.errors)
