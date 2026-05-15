import pytest
from openlia.reports.validator import (
    ReportValidationError,
    validate_report_payload,
)


def _good() -> dict:
    return {
        "schema_version": "2.0",
        "department": "equity_research",
        "generated_at": "2026-04-11T09:30:00Z",
        "cover": {
            "title": "Apple Inc.",
            "subtitle": "Q1 2026",
            "ticker": "AAPL",
            "tagline": "Strong quarter.",
        },
        "sections": [
            {
                "id": "fin",
                "title": "Financial Overview",
                "blocks": [{"type": "text", "content": "Apple reported..."}],
            }
        ],
    }


def test_validator_returns_schema_on_good_input():
    schema = validate_report_payload(_good())
    assert schema.cover.ticker == "AAPL"


def test_validator_raises_with_path_on_bad_version():
    payload = _good()
    payload["schema_version"] = "999"
    with pytest.raises(ReportValidationError) as exc:
        validate_report_payload(payload)
    assert any("schema_version" in p for p, _ in exc.value.errors)


def test_validator_raises_on_unknown_block_type():
    payload = _good()
    payload["sections"][0]["blocks"] = [{"type": "movie", "url": "nope"}]
    with pytest.raises(ReportValidationError) as exc:
        validate_report_payload(payload)
    assert any("blocks" in p for p, _ in exc.value.errors)


def test_validator_rejects_extra_fields():
    payload = _good()
    payload["cover"]["extra_key"] = "no"
    with pytest.raises(ReportValidationError):
        validate_report_payload(payload)


def test_validator_details_carry_input_value_and_type():
    """The .details list must surface the offending input value and its type
    so trace events and LLM repair feedback can diagnose literal-mismatch
    failures (e.g. chart options.height got `400` instead of one of the
    allowed literals)."""
    payload = _good()
    payload["sections"][0]["blocks"] = [
        {
            "type": "line_chart",
            "title": "Revenue",
            "series": [{"name": "rev", "data": [1, 2, 3]}],
            "options": {"height": 400},
        }
    ]
    with pytest.raises(ReportValidationError) as exc:
        validate_report_payload(payload)
    err = exc.value
    assert hasattr(err, "details") and isinstance(err.details, list)
    height_errs = [d for d in err.details if d["path"].endswith("options.height")]
    assert height_errs, f"expected an options.height error in details, got {err.details}"
    detail = height_errs[0]
    assert "input_value" in detail and "input_type" in detail
    assert "400" in detail["input_value"]
    assert detail["input_type"] == "int"
    # Backward-compat: .errors still a list of (path, message) tuples.
    assert all(isinstance(e, tuple) and len(e) == 2 for e in err.errors)
