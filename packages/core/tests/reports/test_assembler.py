from datetime import UTC, datetime

import pytest
from openlia.reports.assembler import PageFurnitureConfig, assemble_report
from openlia.reports.validator import ReportValidationError

DEFAULT_FURNITURE = PageFurnitureConfig(
    header_left="OpenLIA",
    header_right_by_department={"equity_research": "Equity Research Department"},
    footer_left_fmt="Generated {date}",
    footer_center="Page {page}",
    footer_right="For internal use only",
    disclaimer="This report is AI-generated. Verify before acting.",
)


def _raw() -> dict:
    return {
        "schema_version": "2.0",
        "department": "equity_research",
        "cover": {
            "instructions": "Fill in cover",
            "title": "Apple Inc.",
            "subtitle": "Q1 2026",
            "ticker": "AAPL",
            "tagline": "Strong quarter.",
        },
        "sections": [
            {
                "id": "fin",
                "title": "Financial Overview",
                "instructions": "Cover revenue, margins.",
                "blocks": [{"type": "text", "content": "Apple reported..."}],
            }
        ],
    }


def test_assemble_strips_instructions_and_applies_furniture():
    raw = _raw()
    schema = assemble_report(
        raw,
        department="equity_research",
        furniture=DEFAULT_FURNITURE,
        now=datetime(2026, 4, 11, 9, 30, tzinfo=UTC),
    )
    assert schema.page_furniture is not None
    assert schema.page_furniture.header["right"] == "Equity Research Department"
    assert schema.page_furniture.footer["center"] == "Page {page}"
    assert schema.page_furniture.footer["left"] == "Generated 2026-04-11"
    assert schema.sections[0].title == "Financial Overview"
    assert "instructions" not in schema.sections[0].model_dump()


def test_assemble_overwrites_llm_supplied_furniture():
    raw = _raw()
    raw["page_furniture"] = {
        "header": {"left": "EVIL", "right": "EVIL"},
        "footer": {"left": "EVIL", "center": "EVIL", "right": "EVIL"},
        "disclaimer": "EVIL",
    }
    schema = assemble_report(
        raw,
        department="equity_research",
        furniture=DEFAULT_FURNITURE,
        now=datetime(2026, 4, 11, 9, 30, tzinfo=UTC),
    )
    assert schema.page_furniture.header["left"] == "OpenLIA"
    assert schema.page_furniture.disclaimer.startswith("This report is AI-generated")


def test_assemble_raises_on_invalid_payload():
    raw = _raw()
    raw["cover"].pop("title")
    with pytest.raises(ReportValidationError):
        assemble_report(
            raw,
            department="equity_research",
            furniture=DEFAULT_FURNITURE,
            now=datetime(2026, 4, 11, 9, 30, tzinfo=UTC),
        )


def test_assemble_falls_back_to_default_header_for_unknown_department():
    raw = _raw()
    raw["department"] = "secretary"
    schema = assemble_report(
        raw,
        department="secretary",
        furniture=DEFAULT_FURNITURE,
        now=datetime(2026, 4, 11, tzinfo=UTC),
    )
    assert schema.page_furniture.header["right"] == "OpenLIA Report"


def test_rejects_unsubstituted_tool_placeholder():
    from openlia.reports.assembler import ReportAssemblyError

    raw = _raw()
    raw["sections"][0]["blocks"].append({"type": "text", "content": "{{tool:stock_quote}}"})
    with pytest.raises(ReportAssemblyError):
        assemble_report(
            raw,
            department="equity_research",
            furniture=DEFAULT_FURNITURE,
            now=datetime(2026, 4, 11, tzinfo=UTC),
        )
