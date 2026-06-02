"""Unit tests for the feed summary's `highlights` derivation.

Calls the route module's `_summary` helper directly with an in-memory
`ReportEu` row (no DB session needed) to verify cover_json is projected
into a compact, capped highlights payload.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from openlia_server.db.models.report_eu import ReportEu
from openlia_server.routes.departments import earnings_update_v2 as eu


def _row(cover_json: str | None) -> ReportEu:
    return ReportEu(
        id="r1",
        user_id="local",
        subject="Apple - Q2 beat",
        ticker="AAPL",
        trigger_kind="on_demand",
        fiscal_date="2026-03-31",
        template_id="default",
        language="en",
        length="normal",
        provider_kind="anthropic",
        model="claude",
        status="completed",
        created_at=datetime.now(UTC),
        completed_at=None,
        cover_json=cover_json,
        reasoning_effort=None,
    )


def test_summary_highlights_populated_and_capped() -> None:
    cover = json.dumps(
        {
            "subtitle": "Beat on Services",
            "rating": "Buy",
            "key_metrics": [
                {"label": "Revenue", "value": "$94.2B", "change": "+5.4%", "tone": "positive"},
                {"label": "EPS", "value": "$1.78", "change": "+3.5%", "tone": "positive"},
                {"label": "Services", "value": "$26.8B", "change": "+15.2%", "tone": "positive"},
                {"label": "GM", "value": "46.2%", "change": None, "tone": "neutral"},
                {"label": "Extra", "value": "x", "change": None, "tone": None},
            ],
        }
    )
    out = eu._summary(_row(cover))
    assert out.highlights is not None
    assert out.highlights.subtitle == "Beat on Services"
    assert out.highlights.rating == "Buy"
    assert len(out.highlights.metrics) == 4  # capped at 4
    assert out.highlights.metrics[0].value == "$94.2B"
    assert out.highlights.metrics[0].tone == "positive"


def test_summary_highlights_none_without_cover() -> None:
    assert eu._summary(_row(None)).highlights is None


def test_summary_highlights_none_when_cover_has_no_usable_content() -> None:
    assert eu._summary(_row(json.dumps({"tldr": ["x"]}))).highlights is None


def test_summary_highlights_none_on_invalid_json() -> None:
    assert eu._summary(_row("not json")).highlights is None
