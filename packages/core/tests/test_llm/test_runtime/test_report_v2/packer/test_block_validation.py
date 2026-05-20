"""WS8 block shape validation gates.

One positive + one negative case per gate, plus dispatcher and dedup tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

# Importing the assembler eagerly ensures every block module is registered.
from openlia.llm.runtime.report_v2.packer import assembler  # noqa: F401
from openlia.llm.runtime.report_v2.packer.block_shape import (
    BlockShapeError,
    dedupe_by_purpose_tag,
    enforce_block_shapes,
    validate_block_shapes,
)
from openlia.llm.runtime.report_v2.packer.blocks.registry import default_block_registry
from openlia.llm.runtime.report_v2.packer.parser import (
    FencedBlockSegment,
    ParsedSection,
    TextSegment,
)
from openlia.llm.runtime.report_v2.sections.dispatcher import (
    SectionDispatch,
    dispatch_sections,
)
from openlia.llm.runtime.report_v2.types import SectionTerminalState


def _validator(block_type: str):
    entry = default_block_registry.get(block_type)
    assert entry is not None, f"{block_type} not registered"
    assert entry.validate_shape is not None, f"{block_type} missing validate_shape"
    return entry.validate_shape


# ---------------------------------------------------------------------------
# table — minimum row gates for purpose-tagged peer/comp/historical tables
# ---------------------------------------------------------------------------


def test_table_peer_comparison_three_rows_passes() -> None:
    block = {
        "title": "Peer multiples",
        "headers": [{"key": "company", "label": "Company"}, {"key": "pe", "label": "P/E"}],
        "rows": [
            {"company": "MSFT", "pe": "38.2x"},
            {"company": "ORCL", "pe": "25.1x"},
            {"company": "SAP", "pe": "30.0x"},
        ],
        "purpose_tag": "peer_comparison",
    }
    assert _validator("table")(block) == []


def test_table_peer_comparison_single_row_fails() -> None:
    block = {
        "title": "Peer multiples",
        "headers": [{"key": "company", "label": "Company"}],
        "rows": [{"company": "NVDA"}],
        "purpose_tag": "peer_comparison",
    }
    errors = _validator("table")(block)
    assert errors and "peer/comp tables require >=3" in errors[0]


def test_table_historical_three_year_columns_passes() -> None:
    block = {
        "title": "Income statement",
        "headers": [
            {"key": "metric", "label": "Metric"},
            {"key": "fy22", "label": "FY22"},
            {"key": "fy23", "label": "FY23"},
            {"key": "fy24", "label": "FY24"},
        ],
        "rows": [{"metric": "Revenue", "fy22": 100, "fy23": 120, "fy24": 150}],
        "purpose_tag": "historical_financials",
    }
    assert _validator("table")(block) == []


def test_table_historical_two_year_columns_fails() -> None:
    block = {
        "title": "Income statement",
        "headers": [
            {"key": "metric", "label": "Metric"},
            {"key": "fy23", "label": "FY23"},
            {"key": "fy24", "label": "FY24"},
        ],
        "rows": [{"metric": "Revenue", "fy23": 120, "fy24": 150}],
        "purpose_tag": "historical_financials",
    }
    errors = _validator("table")(block)
    assert errors and "historical tables require >=3 year columns" in errors[0]


def test_table_without_purpose_tag_is_unconstrained() -> None:
    block = {
        "title": "Random one-pager",
        "headers": [{"key": "k", "label": "K"}],
        "rows": [{"k": "v"}],
    }
    assert _validator("table")(block) == []


# ---------------------------------------------------------------------------
# chart:scatter — >=3 points per series
# ---------------------------------------------------------------------------


def test_scatter_three_points_passes() -> None:
    block = {
        "title": "P/E vs growth",
        "series": [
            {
                "name": "Peers",
                "points": [
                    {"x": 12.5, "y": 30.1},
                    {"x": 18.3, "y": 42.6},
                    {"x": 24.0, "y": 55.0},
                ],
            }
        ],
    }
    assert _validator("chart:scatter")(block) == []


def test_scatter_single_point_fails() -> None:
    block = {
        "title": "P/E vs growth",
        "series": [{"name": "Peers", "points": [{"x": 1, "y": 2}]}],
    }
    errors = _validator("chart:scatter")(block)
    assert errors and "1 point" in errors[0]


# ---------------------------------------------------------------------------
# chart:bar / line / area / combo — real axes, numeric values
# ---------------------------------------------------------------------------


def test_bar_real_fy_categories_passes() -> None:
    block = {
        "title": "Revenue by segment",
        "categories": ["FY2022", "FY2023", "FY2024"],
        "series": [{"name": "Revenue", "values": [100.0, 120.0, 150.0]}],
    }
    assert _validator("chart:bar")(block) == []


def test_bar_placeholder_axis_fails() -> None:
    block = {
        "title": "Revenue trend",
        "categories": ["Year 1", "Year 2", "TTM/Late"],
        "series": [{"name": "Revenue", "values": [100.0, 120.0, 150.0]}],
    }
    errors = _validator("chart:bar")(block)
    assert any("placeholder label" in e for e in errors)


def test_bar_string_value_fails() -> None:
    block = {
        "title": "Revenue",
        "categories": ["2022", "2023", "2024"],
        "series": [{"name": "Revenue", "values": [100, "120", 150]}],
    }
    errors = _validator("chart:bar")(block)
    assert any("must be a number" in e for e in errors)


def test_bar_empty_values_fails() -> None:
    block = {
        "title": "Empty",
        "categories": ["2022", "2023", "2024"],
        "series": [{"name": "Revenue", "values": []}],
    }
    errors = _validator("chart:bar")(block)
    assert any("non-empty 'values'" in e for e in errors)


def test_line_real_axis_passes() -> None:
    block = {
        "title": "Trend",
        "categories": ["2020", "2021", "2022", "2023", "2024"],
        "series": [{"name": "Revenue", "values": [1, 2, 3, 4, 5]}],
    }
    assert _validator("chart:line")(block) == []


def test_line_placeholder_axis_fails() -> None:
    block = {
        "title": "Trend",
        "categories": ["Period 1", "Period 2", "Period 3"],
        "series": [{"name": "Revenue", "values": [1, 2, 3]}],
    }
    errors = _validator("chart:line")(block)
    assert any("placeholder label" in e for e in errors)


def test_area_passes() -> None:
    block = {
        "title": "Cumulative",
        "categories": ["2020", "2021", "2022", "2023"],
        "series": [{"name": "Customers", "values": [1, 2, 3, 4]}],
    }
    assert _validator("chart:area")(block) == []


def test_area_with_null_values_passes() -> None:
    block = {
        "title": "Cumulative",
        "categories": ["2020", "2021", "2022", "2023"],
        "series": [{"name": "Customers", "values": [1, None, 3, 4]}],
    }
    assert _validator("chart:area")(block) == []


def test_combo_passes_with_bar_and_line_series() -> None:
    block = {
        "title": "Revenue vs margin",
        "categories": ["2022", "2023", "2024"],
        "bar_series": [{"name": "Revenue", "values": [100, 120, 150]}],
        "line_series": [{"name": "Margin", "values": [0.6, 0.62, 0.65]}],
    }
    assert _validator("chart:combo")(block) == []


def test_combo_empty_series_fails() -> None:
    block = {
        "title": "Revenue vs margin",
        "categories": ["2022", "2023", "2024"],
        "bar_series": [],
        "line_series": [{"name": "Margin", "values": [0.6, 0.62, 0.65]}],
    }
    errors = _validator("chart:combo")(block)
    assert any("at least one series required" in e for e in errors)


# ---------------------------------------------------------------------------
# chart:waterfall — sum-check, no running balance above starting total
# ---------------------------------------------------------------------------


def test_waterfall_sums_to_total_passes() -> None:
    block = {
        "title": "FY24 revenue bridge",
        "items": [
            {"label": "FY23 revenue", "value": 8971, "type": "total"},
            {"label": "Expansion", "value": 1645, "type": "increase"},
            {"label": "New logos", "value": 882, "type": "increase"},
            {"label": "Churn", "value": -220, "type": "decrease"},
            {"label": "FY24 revenue", "value": 11278, "type": "total"},
        ],
    }
    # 8971 + 1645 + 882 - 220 = 11278.
    assert _validator("chart:waterfall")(block) == []


def test_waterfall_sum_disagreement_fails() -> None:
    block = {
        "title": "FY24 revenue bridge",
        "items": [
            {"label": "FY23 revenue", "value": 8971, "type": "total"},
            {"label": "Expansion", "value": 100, "type": "increase"},
            {"label": "FY24 revenue", "value": 11278, "type": "total"},
        ],
    }
    errors = _validator("chart:waterfall")(block)
    assert any("disagrees with running sum" in e for e in errors)


def test_waterfall_decrease_below_zero_fails() -> None:
    """NVDA-class: Cost of Revenue floats above 100% of revenue.

    A decrease bar larger than the starting total drives the running
    balance below zero, which the packer rejects.
    """
    block = {
        "title": "Broken margin bridge",
        "items": [
            {"label": "Revenue", "value": 100, "type": "total"},
            # Cost of Revenue tagged as decrease but its absolute magnitude
            # exceeds revenue — that's the NVDA bug.
            {"label": "Cost of Revenue", "value": 120, "type": "decrease"},
            {"label": "Gross Profit", "value": -20, "type": "total"},
        ],
    }
    errors = _validator("chart:waterfall")(block)
    assert any("fell below zero" in e for e in errors)


# ---------------------------------------------------------------------------
# chart:pie and chart:treemap — segments sum to 100% or a declared total
# ---------------------------------------------------------------------------


def test_pie_segments_sum_to_100_passes() -> None:
    block = {
        "title": "Geography mix",
        "segments": [
            {"label": "NA", "value": 65},
            {"label": "EMEA", "value": 22},
            {"label": "APAC", "value": 13},
        ],
    }
    assert _validator("chart:pie")(block) == []


def test_pie_segments_dont_sum_fails() -> None:
    block = {
        "title": "Geography mix",
        "segments": [
            {"label": "NA", "value": 50},
            {"label": "EMEA", "value": 20},
        ],
    }
    errors = _validator("chart:pie")(block)
    assert any("segments sum to" in e for e in errors)


def test_pie_with_declared_total_passes() -> None:
    block = {
        "title": "Revenue $B",
        "segments": [
            {"label": "DC", "value": 115.2},
            {"label": "Gaming", "value": 13.4},
            {"label": "Auto", "value": 1.4},
        ],
        "total": 130.0,
    }
    assert _validator("chart:pie")(block) == []


def test_treemap_sums_to_100_passes() -> None:
    block = {
        "title": "Mix",
        "data": [
            {"name": "A", "value": 60},
            {"name": "B", "value": 30},
            {"name": "C", "value": 10},
        ],
    }
    assert _validator("chart:treemap")(block) == []


def test_treemap_doesnt_sum_fails() -> None:
    block = {
        "title": "Mix",
        "data": [{"name": "A", "value": 60}, {"name": "B", "value": 25}],
    }
    errors = _validator("chart:treemap")(block)
    assert any("nodes sum to" in e for e in errors)


# ---------------------------------------------------------------------------
# data_labels default — chart with <=8 points gets data_labels=True
# ---------------------------------------------------------------------------


def test_bar_default_data_labels_for_small_chart() -> None:
    block = {
        "title": "Small",
        "categories": ["2022", "2023", "2024"],
        "series": [{"name": "rev", "values": [1, 2, 3]}],
    }
    _validator("chart:bar")(block)
    assert block.get("data_labels") is True


def test_bar_does_not_set_data_labels_for_large_chart() -> None:
    block = {
        "title": "Big",
        "categories": [str(2010 + i) for i in range(15)],
        "series": [{"name": "rev", "values": list(range(15))}],
    }
    _validator("chart:bar")(block)
    # >8 data points so default does not kick in.
    assert "data_labels" not in block or block.get("data_labels") is not True


def test_bar_respects_existing_data_labels() -> None:
    block = {
        "title": "Tiny",
        "categories": ["2022", "2023", "2024"],
        "series": [{"name": "rev", "values": [1, 2, 3]}],
        "data_labels": False,
    }
    _validator("chart:bar")(block)
    assert block["data_labels"] is False


# ---------------------------------------------------------------------------
# metric_cards — delta_direction must agree with the sign of delta
# ---------------------------------------------------------------------------


def test_metric_cards_positive_delta_up_passes() -> None:
    block = {
        "metrics": [{"label": "P/E", "value": "245x", "delta": "+12%", "delta_direction": "up"}]
    }
    assert _validator("metric_cards")(block) == []


def test_metric_cards_negative_delta_up_fails() -> None:
    """CRM bug: "-10%" rendered as red but tagged as direction=up."""
    block = {
        "metrics": [
            {"label": "Revenue", "value": "$200B", "delta": "-10%", "delta_direction": "up"}
        ]
    }
    errors = _validator("metric_cards")(block)
    assert any("is negative but" in e for e in errors)


def test_metric_cards_accounting_parens_treated_as_negative() -> None:
    block = {
        "metrics": [{"label": "EPS", "value": "$3", "delta": "(15%)", "delta_direction": "up"}]
    }
    errors = _validator("metric_cards")(block)
    assert any("is negative but" in e for e in errors)


def test_metric_cards_no_delta_passes() -> None:
    block = {"metrics": [{"label": "Cash", "value": "$10B"}]}
    assert _validator("metric_cards")(block) == []


# ---------------------------------------------------------------------------
# Section-level dedup by purpose_tag
# ---------------------------------------------------------------------------


def _make_parsed(segments: list) -> ParsedSection:
    return ParsedSection(frontmatter={"section_id": "x"}, segments=segments)


def test_dedup_strips_second_purpose_tag_and_logs() -> None:
    seg_a = FencedBlockSegment(
        block_type="chart:pie",
        data={
            "title": "Mix A",
            "segments": [
                {"label": "NA", "value": 60},
                {"label": "EMEA", "value": 30},
                {"label": "APAC", "value": 10},
            ],
            "purpose_tag": "segment_mix:FY2026",
        },
    )
    seg_b = FencedBlockSegment(
        block_type="chart:pie",
        data={
            "title": "Mix B",
            "segments": [
                {"label": "NA", "value": 70},
                {"label": "EMEA", "value": 20},
                {"label": "APAC", "value": 10},
            ],
            "purpose_tag": "segment_mix:FY2026",
        },
    )
    parsed = _make_parsed([seg_a, seg_b])
    log = dedupe_by_purpose_tag(parsed)
    assert len(parsed.segments) == 1
    assert parsed.segments[0] is seg_a
    assert log and "segment_mix:FY2026" in log[0]


def test_dedup_keeps_distinct_purpose_tags() -> None:
    seg_a = FencedBlockSegment(
        block_type="chart:pie",
        data={
            "title": "Mix A",
            "segments": [
                {"label": "NA", "value": 60},
                {"label": "EMEA", "value": 30},
                {"label": "APAC", "value": 10},
            ],
            "purpose_tag": "segment_mix:FY2025",
        },
    )
    seg_b = FencedBlockSegment(
        block_type="chart:pie",
        data={
            "title": "Mix B",
            "segments": [
                {"label": "NA", "value": 70},
                {"label": "EMEA", "value": 20},
                {"label": "APAC", "value": 10},
            ],
            "purpose_tag": "segment_mix:FY2026",
        },
    )
    parsed = _make_parsed([seg_a, seg_b])
    log = dedupe_by_purpose_tag(parsed)
    assert len(parsed.segments) == 2
    assert log == []


def test_enforce_block_shapes_raises_on_defect() -> None:
    seg = FencedBlockSegment(
        block_type="chart:scatter",
        data={"title": "x", "series": [{"name": "S", "points": [{"x": 1, "y": 2}]}]},
    )
    parsed = _make_parsed([seg])
    with pytest.raises(BlockShapeError) as exc:
        enforce_block_shapes(parsed)
    assert any("1 point" in d for d in exc.value.defects)


def test_validate_block_shapes_returns_defect_list() -> None:
    seg = FencedBlockSegment(
        block_type="table",
        data={
            "title": "x",
            "headers": [{"key": "k", "label": "K"}],
            "rows": [{"k": "v"}],
            "purpose_tag": "peer_comparison",
        },
    )
    parsed = _make_parsed([seg])
    defects = validate_block_shapes(parsed)
    assert defects and "peer/comp" in defects[0]


def test_enforce_block_shapes_skips_text_segments() -> None:
    parsed = _make_parsed([TextSegment(text="some prose", citation_ids=[1])])
    # Should not raise.
    log = enforce_block_shapes(parsed)
    assert log == []


# ---------------------------------------------------------------------------
# Dispatcher integration — BlockShapeError triggers retry with defect in prompt
# ---------------------------------------------------------------------------


_BAD_SCATTER_MD = """---
section_id: company_overview
title: Company Overview
sources_used: [1]
synthesis_hooks:
  thesis_contribution: "x"
  bull_case_inputs: ["a [1]"]
  bear_case_inputs: ["b [1]"]
---

## Company Overview

Some prose [1].

```chart:scatter
title: Bad scatter
series:
  - name: Peers
    points:
      - {x: 1.0, y: 2.0}
sources: [1]
```
"""


_GOOD_MD_TEMPLATE = (
    """---
section_id: company_overview
title: Company Overview
sources_used: [1]
synthesis_hooks:
  thesis_contribution: "x"
  bull_case_inputs: ["a [1]"]
  bear_case_inputs: ["b [1]"]
---

## Company Overview

Some prose [1]. """
    + " ".join(["word"] * 500)
    + """
"""
)


@pytest.mark.asyncio
async def test_dispatcher_retries_on_block_shape_error_with_defect_in_prompt() -> None:
    writer = AsyncMock()
    writer.write.side_effect = [_BAD_SCATTER_MD, _GOOD_MD_TEMPLATE]
    dispatch = SectionDispatch(
        section_id="company_overview",
        prompt="ORIGINAL PROMPT",
        target_word_count=600,
        facts_slice={},
    )
    results = await dispatch_sections(
        dispatches=[dispatch],
        writer=writer,
        validator=lambda p, **kw: [],
        max_retries=2,
        known_block_tags=["text", "chart:scatter"],
    )
    assert results[0].state == SectionTerminalState.DEGRADED
    assert results[0].attempts == 2
    # The retry prompt must carry the defect.
    second_prompt = writer.write.await_args_list[1].args[0]
    assert "BLOCK SHAPE" in second_prompt
    assert "1 point" in second_prompt or "point(s)" in second_prompt


@pytest.mark.asyncio
async def test_dispatcher_exhausts_when_block_shape_keeps_failing() -> None:
    writer = AsyncMock()
    writer.write.return_value = _BAD_SCATTER_MD
    dispatch = SectionDispatch(
        section_id="company_overview",
        prompt="ORIGINAL PROMPT",
        target_word_count=600,
        facts_slice={},
    )
    results = await dispatch_sections(
        dispatches=[dispatch],
        writer=writer,
        validator=lambda p, **kw: [],
        max_retries=1,
        known_block_tags=["text", "chart:scatter"],
    )
    assert results[0].state == SectionTerminalState.EXHAUSTED
    # Defect message should appear in validation_errors.
    assert any("scatter" in e for e in results[0].validation_errors)
