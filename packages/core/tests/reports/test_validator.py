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
