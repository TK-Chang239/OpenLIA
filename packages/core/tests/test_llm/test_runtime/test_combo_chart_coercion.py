"""combo_chart series-shape coercion.

`ComboChartBlock.bar_series` and `line_series` items require the strict
shape ``{"name": str, "values": [float, ...]}``. The LLM sometimes drifts
and emits ``data`` instead (the key used by line/area chart series, which
carry ``{x, y}`` points). When that happens the frontend reads
``s.values[0]`` on undefined and the report viewer crashes.

The last-resort coercion fallback must rename ``data`` to ``values`` so
strict validation accepts the payload.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from openlia.llm.runtime.report import (
    _apply_coercion_fallback,
    _inject_server_fields,
)
from openlia.reports.validator import ReportValidationError, validate_report_payload


def _payload_with_combo(bar_series: Any, line_series: Any) -> dict[str, Any]:
    return {
        "cover": {"title": "AAPL", "subtitle": "Coverage", "tagline": "x"},
        "sections": [
            {
                "id": "financials",
                "title": "Financials",
                "blocks": [
                    {
                        "type": "combo_chart",
                        "title": "Revenue and margin",
                        "categories": ["2023", "2024", "2025"],
                        "bar_series": bar_series,
                        "line_series": line_series,
                    }
                ],
            }
        ],
    }


def _normalize_and_validate(raw: dict[str, Any]) -> Any:
    payload = _inject_server_fields(
        raw,
        department_id="equity_research",
        generated_at=datetime(2026, 5, 15, tzinfo=UTC),
    )
    payload = _apply_coercion_fallback(payload)
    return validate_report_payload(payload)


def test_combo_chart_rejects_series_with_data_key_at_strict_validation() -> None:
    """Before coercion, the strict schema must reject series shaped with
    `data` instead of `values` — this is what surfaces the error to the
    repair turn so the LLM has a chance to fix it."""
    raw = _payload_with_combo(
        bar_series=[{"name": "Revenue", "data": [3.2, 5.0, 7.2]}],
        line_series=[{"name": "Margin", "data": [7.0, 10.0, 13.0]}],
    )
    payload = _inject_server_fields(
        raw,
        department_id="equity_research",
        generated_at=datetime(2026, 5, 15, tzinfo=UTC),
    )
    with pytest.raises(ReportValidationError) as exc_info:
        validate_report_payload(payload)
    paths = {d["path"] for d in exc_info.value.details}
    assert "sections.0.blocks.0.combo_chart.bar_series.0.values" in paths
    assert "sections.0.blocks.0.combo_chart.line_series.0.values" in paths


def test_combo_chart_data_key_coerced_to_values() -> None:
    """The fallback renames `data` to `values` so payloads that survived to
    the last-resort path still validate and render."""
    raw = _payload_with_combo(
        bar_series=[{"name": "Revenue", "data": [3.2, 5.0, 7.2]}],
        line_series=[{"name": "Margin", "data": [7.0, 10.0, 13.0]}],
    )
    report = _normalize_and_validate(raw)
    combo = report.sections[0].blocks[0]
    assert combo.bar_series[0].values == [3.2, 5.0, 7.2]
    assert combo.line_series[0].values == [7.0, 10.0, 13.0]


def test_combo_chart_existing_values_pass_through_unchanged() -> None:
    raw = _payload_with_combo(
        bar_series=[{"name": "Revenue", "values": [1.0, 2.0, 3.0]}],
        line_series=[{"name": "Margin", "values": [4.0, 5.0, 6.0]}],
    )
    report = _normalize_and_validate(raw)
    combo = report.sections[0].blocks[0]
    assert combo.bar_series[0].values == [1.0, 2.0, 3.0]
    assert combo.line_series[0].values == [4.0, 5.0, 6.0]


def test_combo_chart_mixed_keys_coerced_per_series() -> None:
    """Coercion runs per-series, not per-block, so a block with one
    correctly-shaped series and one drifted series still validates."""
    raw = _payload_with_combo(
        bar_series=[{"name": "Revenue", "values": [1.0, 2.0, 3.0]}],
        line_series=[{"name": "Margin", "data": [4.0, 5.0, 6.0]}],
    )
    report = _normalize_and_validate(raw)
    combo = report.sections[0].blocks[0]
    assert combo.bar_series[0].values == [1.0, 2.0, 3.0]
    assert combo.line_series[0].values == [4.0, 5.0, 6.0]
