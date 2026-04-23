from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from openlia.reports.schema import (
    ReportSchema,
    TextBlock,
    TableBlock,
    TableHeader,
    MetricCardsBlock,
    Metric,
    GroupBlock,
    KeyFindingBlock,
    RatingBadgeBlock,
    LineChartBlock,
    BarChartBlock,
    CandlestickBlock,
    Cover,
    Section,
    PageFurniture,
)


def test_text_block_parses():
    b = TextBlock(type="text", content="Hello **world**")
    assert b.content == "Hello **world**"


def test_table_block_requires_headers_and_rows():
    t = TableBlock(
        type="table",
        title="Revenue",
        headers=[TableHeader(key="q", label="Quarter", align="left")],
        rows=[{"q": "Q1 2026"}],
    )
    assert t.headers[0].key == "q"
    with pytest.raises(ValidationError):
        TableBlock(type="table", title="x", headers=[], rows=[])


def test_group_block_nests_other_blocks():
    inner = TextBlock(type="text", content="a")
    g = GroupBlock(type="group", columns=2, blocks=[inner, inner])
    assert len(g.blocks) == 2


def test_metric_cards_block_requires_at_least_one_metric():
    m = MetricCardsBlock(
        type="metric_cards",
        metrics=[Metric(label="Rev", value="$1B")],
    )
    assert m.metrics[0].value == "$1B"
    with pytest.raises(ValidationError):
        MetricCardsBlock(type="metric_cards", metrics=[])


def test_line_chart_requires_series():
    c = LineChartBlock(
        type="line_chart",
        title="Margin",
        series=[{"name": "M%", "data": [{"x": "Q1", "y": 46.6}]}],
    )
    assert c.series[0]["name"] == "M%"


def test_bar_chart_requires_categories_and_series():
    b = BarChartBlock(
        type="bar_chart",
        title="Rev",
        categories=["Q1"],
        series=[{"name": "Rev", "values": [1.0]}],
    )
    assert b.categories == ["Q1"]


def test_candlestick_has_ohlc_data():
    c = CandlestickBlock(
        type="candlestick_chart",
        title="AAPL",
        data=[{"date": "2026-04-01", "open": 1, "high": 2, "low": 0.5, "close": 1.8}],
    )
    assert len(c.data) == 1


def test_full_schema_parses():
    schema = ReportSchema(
        schema_version="1.0",
        department="equity_research",
        generated_at=datetime.now(timezone.utc),
        page_furniture=PageFurniture(
            header={"left": "OpenLIA", "right": "Equity Research"},
            footer={"left": "Generated", "center": "Page {page}", "right": "Internal"},
            disclaimer="Not advice.",
        ),
        cover=Cover(
            title="Apple Inc.",
            subtitle="Q1 2026",
            ticker="AAPL",
            tagline="Strong quarter.",
            key_metrics=[Metric(label="Price", value="$198.50")],
            stats_panel=[Metric(label="Sector", value="Technology")],
        ),
        sections=[
            Section(
                id="fin",
                title="Financial Overview",
                blocks=[TextBlock(type="text", content="Apple reported...")],
            )
        ],
    )
    assert schema.schema_version == "1.0"
    assert schema.cover.ticker == "AAPL"


def test_schema_rejects_unknown_version():
    with pytest.raises(ValidationError):
        ReportSchema(
            schema_version="2.0",
            department="equity_research",
            generated_at=datetime.now(timezone.utc),
            cover=Cover(title="x", subtitle="x", ticker="AAPL", tagline="x"),
            sections=[],
        )


def test_rating_badge_block_parses():
    r = RatingBadgeBlock(
        type="rating_badge",
        rating="Overweight",
        previous_rating="Equal Weight",
        change_date="2026-04-11",
    )
    assert r.rating == "Overweight"


def test_key_finding_block_parses():
    k = KeyFindingBlock(type="key_finding", content="iPhone up 49%.")
    assert "iPhone" in k.content
