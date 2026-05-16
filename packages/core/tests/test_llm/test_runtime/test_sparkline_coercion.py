"""Sparkline point coercion contracts.

`rail.sparkline.points` requires `[{"x": float, "y": float}, ...]` per the
strict Pydantic schema. Models frequently emit:

- a flat numeric array: `[120.5, 121.2, 119.8, ...]`
- an array of [x, y] tuples encoded as JSON lists: `[[1, 120.5], [2, 121.2], ...]`
- a mix of the above with already-correct dicts

The last-resort coercion fallback must rescue each of these forms so the
report renders instead of dying at strict validation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from openlia.llm.runtime.report import (
    _apply_coercion_fallback,
    _inject_server_fields,
)
from openlia.reports.validator import validate_report_payload


def _payload_with_sparkline_points(points: Any) -> dict[str, Any]:
    """Minimal strict-shape payload with a rail sparkline whose `points` is
    whatever the caller supplies (intentionally allowed to be malformed)."""
    return {
        "cover": {
            "title": "AAPL",
            "subtitle": "Coverage",
            "tagline": "x",
        },
        "rail": {
            "sparkline": {
                "label": "Last 60 days",
                "points": points,
            }
        },
        "sections": [],
    }


def _normalize_and_validate(raw: dict[str, Any]) -> Any:
    payload = _inject_server_fields(
        raw,
        department_id="equity_research",
        generated_at=datetime(2026, 5, 14, tzinfo=UTC),
    )
    payload = _apply_coercion_fallback(payload)
    return validate_report_payload(payload)


def test_sparkline_flat_numeric_array_validates_after_coercion() -> None:
    """Flat array of numbers — model emitted `[y0, y1, y2, ...]`. Coerce to
    `[{"x": 0.0, "y": y0}, {"x": 1.0, "y": y1}, ...]` using index as x."""
    raw = _payload_with_sparkline_points([120.5, 121.2, 119.8, 120.1])
    report = _normalize_and_validate(raw)
    points = report.rail.sparkline.points
    assert len(points) == 4
    assert [(p.x, p.y) for p in points] == [
        (0.0, 120.5),
        (1.0, 121.2),
        (2.0, 119.8),
        (3.0, 120.1),
    ]


def test_sparkline_list_of_pairs_validates_after_coercion() -> None:
    """List of two-element lists — model emitted `[[x, y], [x, y], ...]`."""
    raw = _payload_with_sparkline_points([[1, 120.5], [2, 121.2], [3, 119.8]])
    report = _normalize_and_validate(raw)
    points = report.rail.sparkline.points
    assert [(p.x, p.y) for p in points] == [(1.0, 120.5), (2.0, 121.2), (3.0, 119.8)]


def test_sparkline_mixed_dicts_and_pairs_is_idempotent() -> None:
    """Already-correct `{x, y}` dicts must pass through unchanged; only the
    malformed entries are rewritten."""
    raw = _payload_with_sparkline_points(
        [
            {"x": 0.0, "y": 100.0},
            [1, 101.0],
            {"x": 2.0, "y": 102.0},
        ]
    )
    report = _normalize_and_validate(raw)
    points = report.rail.sparkline.points
    assert [(p.x, p.y) for p in points] == [
        (0.0, 100.0),
        (1.0, 101.0),
        (2.0, 102.0),
    ]


def test_sparkline_tuple_pairs_validate_after_coercion() -> None:
    """Python tuples (not lists) for each pair — defensive: JSON would always
    produce lists, but in-process callers may pass tuples."""
    raw = _payload_with_sparkline_points([(1.0, 120.5), (2.0, 121.2)])
    report = _normalize_and_validate(raw)
    assert [(p.x, p.y) for p in report.rail.sparkline.points] == [
        (1.0, 120.5),
        (2.0, 121.2),
    ]


def test_sparkline_absent_when_rail_has_no_sparkline() -> None:
    """No-op when the rail exists but has no sparkline; rail.quick_stats path
    must still work alongside."""
    payload = {
        "cover": {"title": "AAPL", "subtitle": "Coverage", "tagline": "x"},
        "rail": {"quick_stats": [{"label": "Px", "value": 200}]},
        "sections": [],
    }
    report = _normalize_and_validate(payload)
    assert report.rail.sparkline is None
    # Numeric metric value was coerced to string by the existing path.
    assert report.rail.quick_stats[0].value == "200"


def test_strict_valid_sparkline_is_unchanged() -> None:
    """A first-try valid payload (proper `{x, y}` dicts) must not be touched."""
    original = [
        {"x": 0.0, "y": 100.0},
        {"x": 1.0, "y": 101.0},
    ]
    raw = _payload_with_sparkline_points([dict(p) for p in original])
    report = _normalize_and_validate(raw)
    assert [(p.x, p.y) for p in report.rail.sparkline.points] == [
        (0.0, 100.0),
        (1.0, 101.0),
    ]


def test_sparkline_strictness_prompt_documents_point_shape() -> None:
    """The shipped strictness prompt must teach the model the per-point shape
    so it can self-emit correctly without relying on coercion."""
    from pathlib import Path

    import openlia.prompts as prompts_pkg

    prompt_path = Path(prompts_pkg.__file__).parent / "shared" / "report_schema_strictness.yaml.j2"
    text = prompt_path.read_text()
    # Names the field and the per-point shape.
    assert "sparkline" in text.lower()
    assert '"x"' in text and '"y"' in text
