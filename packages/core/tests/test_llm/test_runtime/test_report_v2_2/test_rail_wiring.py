"""Test carry-over wiring 5a: enforce_required_rail is now template-driven.

Verifies:
- Template with rail.required_quick_stats → enforce_required_rail raises when labels missing.
- Template with rail.required_quick_stats → passes when labels present.
- Template without rail block → skips silently.
- No framework_template_spec in request → skips silently.
"""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report import _required_rail_labels
from openlia.reports.validator import (
    ReportValidationError,
    enforce_required_rail,
    validate_report_payload,
)

# ---- Helper: build minimal ReportRequest-like object ----


class _FakeRequest:
    def __init__(self, framework_template_spec=None):
        self.framework_template_spec = framework_template_spec


# ---- Helper: build minimal valid report payload ----


def _good_payload() -> dict:
    return {
        "schema_version": "2.0",
        "department": "equity_research",
        "generated_at": "2026-05-22T00:00:00Z",
        "cover": {
            "title": "Microsoft Corp.",
            "subtitle": "Initiation",
            "ticker": "MSFT",
            "tagline": "Strong platform.",
        },
        "sections": [
            {
                "id": "overview",
                "title": "Overview",
                "blocks": [{"type": "text", "content": "MSFT analysis."}],
            }
        ],
    }


def _payload_with_rail(labels: list[str]) -> dict:
    payload = _good_payload()
    payload["rail"] = {
        "verdict": {"rating": "Buy", "target": "$450"},
        "quick_stats": [{"label": lbl, "value": "x"} for lbl in labels],
    }
    return payload


# ---- Template spec dicts ----


def _spec_with_required_labels(*labels: str) -> dict:
    return {
        "template_id": "stock_initiation_v2",
        "template_name": "Stock Initiation",
        "department": "equity_research",
        "report_type": "stock_initiation",
        "engine_version_compat": "2.2",
        "sections": [{"id": "s", "name": "S", "directive": "Write."}],
        "rail": {"required_quick_stats": list(labels)},
    }


def _spec_without_rail() -> dict:
    return {
        "template_id": "morning_briefing_v2",
        "template_name": "Morning Briefing",
        "department": "morning_briefing",
        "report_type": "morning_briefing",
        "engine_version_compat": "2.2",
        "sections": [{"id": "s", "name": "S", "directive": "Write."}],
    }


# ---- _required_rail_labels helper ----


def test_required_rail_labels_returns_labels_from_spec() -> None:
    req = _FakeRequest(framework_template_spec=_spec_with_required_labels("Market Cap", "Sector"))
    labels = _required_rail_labels(req)
    assert labels == ["Market Cap", "Sector"]


def test_required_rail_labels_returns_none_when_no_spec() -> None:
    req = _FakeRequest(framework_template_spec=None)
    assert _required_rail_labels(req) is None


def test_required_rail_labels_returns_none_when_no_rail_block() -> None:
    req = _FakeRequest(framework_template_spec=_spec_without_rail())
    assert _required_rail_labels(req) is None


def test_required_rail_labels_returns_none_on_invalid_spec() -> None:
    req = _FakeRequest(framework_template_spec={"bad": "data"})
    # Should not raise; returns None so rail check is skipped.
    result = _required_rail_labels(req)
    assert result is None


def test_required_rail_labels_returns_none_when_spec_is_not_dict() -> None:
    req = _FakeRequest(framework_template_spec="not a dict")
    assert _required_rail_labels(req) is None


# ---- enforce_required_rail integration ----


def test_enforce_passes_when_all_labels_present() -> None:
    labels = ["Market Cap", "Sector"]
    schema = validate_report_payload(_payload_with_rail(labels))
    req = _FakeRequest(framework_template_spec=_spec_with_required_labels(*labels))
    required = _required_rail_labels(req)
    enforce_required_rail(schema, department_id="equity_research", required_labels=required)


def test_enforce_raises_when_label_missing() -> None:
    schema = validate_report_payload(_payload_with_rail(["Market Cap"]))
    req = _FakeRequest(
        framework_template_spec=_spec_with_required_labels("Market Cap", "Sector", "Exchange")
    )
    required = _required_rail_labels(req)
    with pytest.raises(ReportValidationError) as exc_info:
        enforce_required_rail(schema, department_id="equity_research", required_labels=required)
    msg = str(exc_info.value)
    assert "Sector" in msg or "Exchange" in msg


def test_enforce_skips_when_no_spec() -> None:
    schema = validate_report_payload(_good_payload())  # no rail
    req = _FakeRequest(framework_template_spec=None)
    required = _required_rail_labels(req)
    # required is None → should skip entirely without raising.
    enforce_required_rail(schema, department_id="equity_research", required_labels=required)


def test_enforce_skips_when_no_rail_in_template() -> None:
    schema = validate_report_payload(_good_payload())  # no rail
    req = _FakeRequest(framework_template_spec=_spec_without_rail())
    required = _required_rail_labels(req)
    assert required is None
    # Should not raise.
    enforce_required_rail(schema, department_id="morning_briefing", required_labels=required)


def test_enforce_skips_when_required_quick_stats_is_null() -> None:
    spec = _spec_with_required_labels()  # empty list
    spec["rail"]["required_quick_stats"] = None  # type: ignore[index]
    schema = validate_report_payload(_good_payload())
    req = _FakeRequest(framework_template_spec=spec)
    required = _required_rail_labels(req)
    assert required is None
    enforce_required_rail(schema, department_id="equity_research", required_labels=required)
