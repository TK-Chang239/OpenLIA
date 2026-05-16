import pytest
from openlia.reports.validator import (
    ReportValidationError,
    enforce_required_rail,
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


def _good_with_rail(department: str) -> dict:
    payload = _good()
    payload["department"] = department
    payload["rail"] = {
        "verdict": {"rating": "Buy", "target": "$245", "as_of": "2026-05-16"},
        "quick_stats": [
            {"label": "Market Cap", "value": "$3.5T"},
            {"label": "Sector", "value": "Tech"},
            {"label": "Exchange", "value": "NASDAQ"},
            {"label": "52W Range", "value": "$170-$245"},
            {"label": "ADTV (3mo)", "value": "55M"},
            {"label": "P/E (fwd)", "value": "28x"},
        ],
    }
    return payload


def test_enforce_required_rail_passes_when_complete():
    schema = validate_report_payload(_good_with_rail("stock_initiation"))
    enforce_required_rail(schema, department_id="stock_initiation")


def test_enforce_required_rail_skips_unconfigured_departments():
    schema = validate_report_payload(_good())  # no rail
    enforce_required_rail(schema, department_id="morning_briefing")
    enforce_required_rail(schema, department_id="equity_research")


def test_enforce_required_rail_fails_on_missing_verdict():
    payload = _good_with_rail("stock_initiation")
    payload["rail"]["verdict"] = None
    schema = validate_report_payload(payload)
    with pytest.raises(ReportValidationError) as exc:
        enforce_required_rail(schema, department_id="stock_initiation")
    assert any("rail.verdict" in p for p, _ in exc.value.errors)


def test_enforce_required_rail_fails_on_missing_quick_stat_label():
    payload = _good_with_rail("stock_initiation")
    payload["rail"]["quick_stats"] = [
        m for m in payload["rail"]["quick_stats"] if m["label"] != "Sector"
    ]
    schema = validate_report_payload(payload)
    with pytest.raises(ReportValidationError) as exc:
        enforce_required_rail(schema, department_id="stock_initiation")
    msgs = " ".join(m for _, m in exc.value.errors)
    assert "'Sector'" in msgs


def test_enforce_required_rail_label_match_is_case_insensitive():
    payload = _good_with_rail("stock_initiation")
    for m in payload["rail"]["quick_stats"]:
        m["label"] = m["label"].upper()
    schema = validate_report_payload(payload)
    enforce_required_rail(schema, department_id="stock_initiation")


def test_enforce_required_rail_earnings_update_required_labels():
    payload = _good_with_rail("earnings_update")
    payload["rail"]["quick_stats"] = [
        {"label": "Period", "value": "Q1 FY26"},
        {"label": "Market Cap", "value": "$3.5T"},
        {"label": "EPS Surprise", "value": "+4.2%"},
        {"label": "Revenue Surprise", "value": "+3.1%"},
        {"label": "Beats", "value": "3"},
        {"label": "Misses", "value": "0"},
    ]
    schema = validate_report_payload(payload)
    enforce_required_rail(schema, department_id="earnings_update")
