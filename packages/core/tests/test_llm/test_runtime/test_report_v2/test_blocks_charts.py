from __future__ import annotations

import pytest

from openlia.llm.runtime.report_v2.packer.blocks import (  # noqa: F401 trigger registration
    chart_area,
    chart_bar,
    chart_candlestick,
    chart_combo,
    chart_heatmap,
    chart_line,
    chart_pie,
    chart_scatter,
    chart_treemap,
    chart_waterfall,
)
from openlia.llm.runtime.report_v2.packer.blocks.registry import default_block_registry
from openlia.reports.schema import (
    AreaChartBlock,
    BarChartBlock,
    CandlestickBlock,
    ComboChartBlock,
    HeatmapBlock,
    LineChartBlock,
    PieChartBlock,
    ScatterBlock,
    TreemapBlock,
    WaterfallBlock,
)


def _resolver(citation_ids):
    return [f"c{i}" for i in citation_ids]


CHART_CASES = [
    (
        "chart:line",
        LineChartBlock,
        {
            "title": "Revenue Trend",
            "series": [{"name": "Revenue", "values": [1.0, 2.0, 3.0]}],
            "x_label": "Year",
            "y_label": "Rev ($B)",
        },
    ),
    (
        "chart:bar",
        BarChartBlock,
        {
            "title": "Quarterly Revenue",
            "categories": ["Q1", "Q2", "Q3"],
            "series": [{"name": "Revenue", "values": [1.0, 1.5, 2.0]}],
        },
    ),
    (
        "chart:area",
        AreaChartBlock,
        {
            "title": "Cumulative Growth",
            "series": [{"name": "Growth", "values": [1.0, 2.0, 4.0]}],
        },
    ),
    (
        "chart:pie",
        PieChartBlock,
        {
            "title": "Revenue Mix",
            "segments": [{"label": "Cloud", "value": 60.0}, {"label": "On-Prem", "value": 40.0}],
        },
    ),
    (
        "chart:combo",
        ComboChartBlock,
        {
            "title": "Revenue & Margin",
            "categories": ["2022", "2023", "2024"],
            "series": [
                {"name": "Revenue", "kind": "bar", "values": [1.0, 2.0, 3.0]},
                {"name": "Margin", "kind": "line", "values": [0.1, 0.12, 0.13]},
            ],
        },
    ),
    (
        "chart:candlestick",
        CandlestickBlock,
        {
            "title": "Price History",
            "data": [
                {"date": "2024-01-01", "open": 100.0, "high": 110.0, "low": 95.0, "close": 105.0},
                {"date": "2024-01-02", "open": 105.0, "high": 115.0, "low": 100.0, "close": 110.0},
            ],
        },
    ),
    (
        "chart:waterfall",
        WaterfallBlock,
        {
            "title": "Revenue Bridge",
            "items": [
                {"label": "Start", "value": 100.0, "type": "total"},
                {"label": "New Biz", "value": 20.0, "type": "increase"},
                {"label": "Churn", "value": -5.0, "type": "decrease"},
                {"label": "End", "value": 115.0, "type": "total"},
            ],
        },
    ),
    (
        "chart:scatter",
        ScatterBlock,
        {
            "title": "P/E vs Growth",
            "series": [{"name": "Tech", "points": [{"x": 1.0, "y": 2.0}]}],
            "x_label": "Growth",
            "y_label": "P/E",
        },
    ),
    (
        "chart:heatmap",
        HeatmapBlock,
        {
            "title": "Correlation Matrix",
            "x_labels": ["A", "B"],
            "y_labels": ["X", "Y"],
            "values": [[1.0, 0.5], [0.5, 1.0]],
        },
    ),
    (
        "chart:treemap",
        TreemapBlock,
        {
            "title": "Market Cap",
            "data": [
                {"name": "Tech", "value": 500.0},
                {"name": "Finance", "value": 300.0},
            ],
        },
    ),
]


@pytest.mark.parametrize("tag,cls,data", CHART_CASES)
def test_chart_assembler_returns_expected_class(tag, cls, data) -> None:
    data = {**data, "sources": [1]}
    entry = default_block_registry.get(tag)
    assert entry is not None, f"{tag} not registered"
    block = entry.assembler(data=data, citation_ids=[], manifest_resolver=_resolver)
    assert isinstance(block, cls)
    assert block.source_ids == ["c1"]
