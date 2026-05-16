from datetime import UTC, datetime

import pytest
from openlia.reports.schema import (
    Cover,
    Metric,
    PageFurniture,
    ReportSchema,
    Section,
    TextBlock,
)
from openlia_server.db.models.content import Report
from openlia_server.services.reports import (
    ReportNotFoundError,
    create_report,
    derive_report_title,
    get_report,
)


def _sample_schema() -> ReportSchema:
    return ReportSchema(
        schema_version="2.0",
        department="equity_research",
        generated_at=datetime(2026, 4, 11, tzinfo=UTC),
        page_furniture=PageFurniture(
            header={"left": "OpenLIA", "right": "ER"},
            footer={"left": "Gen", "center": "Page {page}", "right": "Internal"},
            disclaimer="Not advice.",
        ),
        cover=Cover(
            title="Apple Inc.",
            subtitle="Q1 2026",
            ticker="AAPL",
            tagline="Strong quarter.",
            key_metrics=[Metric(label="P", value="$198")],
        ),
        sections=[
            Section(
                id="fin",
                title="Financial Overview",
                blocks=[TextBlock(type="text", content="Apple reported...")],
            )
        ],
    )


def test_create_then_get_roundtrip(db_session, seeded_user):
    schema = _sample_schema()
    report_id = create_report(
        db_session,
        user_id=seeded_user.id,
        department="equity_research",
        mode="initiation",
        schema=schema,
    )
    assert isinstance(report_id, str) and len(report_id) >= 10

    loaded = get_report(db_session, report_id=report_id, user_id=seeded_user.id)
    assert loaded.cover.ticker == "AAPL"
    assert loaded.sections[0].title == "Financial Overview"


def test_get_report_raises_when_missing(db_session, seeded_user):
    with pytest.raises(ReportNotFoundError):
        get_report(db_session, report_id="does-not-exist", user_id=seeded_user.id)


def _cover(**overrides) -> Cover:
    base = dict(
        title="Stock Initiation Report",
        subtitle="Apple Inc.",
        ticker="AAPL",
        eyebrow="Stock Initiation · May 16, 2026",
        tagline="Strong setup.",
        key_metrics=[],
    )
    base.update(overrides)
    return Cover(**base)


def _schema_with_cover(cover: Cover) -> ReportSchema:
    return ReportSchema(
        schema_version="2.0",
        department="equity_research",
        generated_at=datetime(2026, 5, 16, tzinfo=UTC),
        page_furniture=PageFurniture(
            header={"left": "OpenLIA", "right": "ER"},
            footer={"left": "Gen", "center": "Page {page}", "right": "Internal"},
            disclaimer="Not advice.",
        ),
        cover=cover,
        sections=[
            Section(id="s", title="S", blocks=[TextBlock(type="text", content="x")])
        ],
    )


def test_derive_title_stock_initiation():
    schema = _schema_with_cover(_cover())
    assert derive_report_title("stock_initiation", schema) == "AAPL — Initiation"


def test_derive_title_stock_update():
    schema = _schema_with_cover(_cover())
    assert derive_report_title("stock_update", schema) == "AAPL — Update"


def test_derive_title_sector_research():
    schema = _schema_with_cover(_cover(ticker=None, subtitle="Semiconductors"))
    assert derive_report_title("sector_research", schema) == "Semiconductors — Sector Research"


def test_derive_title_earnings_with_period():
    schema = _schema_with_cover(
        _cover(eyebrow="Earnings Update · Q1 FY2026 · 16:30 ET")
    )
    assert derive_report_title("earnings_analysis", schema) == "AAPL Q1 FY2026 Earnings"


def test_derive_title_earnings_without_period():
    schema = _schema_with_cover(_cover(eyebrow="Earnings · May 16, 2026"))
    assert derive_report_title("earnings_analysis", schema) == "AAPL Earnings"


def test_derive_title_returns_none_when_ticker_missing():
    schema = _schema_with_cover(_cover(ticker=None))
    assert derive_report_title("stock_initiation", schema) is None


def test_derive_title_unknown_mode():
    schema = _schema_with_cover(_cover())
    assert derive_report_title("background", schema) is None


def test_create_report_uses_derived_title(db_session, seeded_user):
    schema = _schema_with_cover(_cover())
    report_id = create_report(
        db_session,
        user_id=seeded_user.id,
        department="equity_research",
        mode="stock_initiation",
        schema=schema,
    )
    row = db_session.get(Report, report_id)
    assert row.title == "AAPL — Initiation"


def test_create_report_falls_back_to_cover_title_when_no_ticker(db_session, seeded_user):
    schema = _schema_with_cover(_cover(ticker=None))
    report_id = create_report(
        db_session,
        user_id=seeded_user.id,
        department="equity_research",
        mode="stock_initiation",
        schema=schema,
    )
    row = db_session.get(Report, report_id)
    assert row.title == "Stock Initiation Report"


def test_create_report_explicit_title_wins(db_session, seeded_user):
    schema = _schema_with_cover(_cover())
    report_id = create_report(
        db_session,
        user_id=seeded_user.id,
        department="morning_briefing",
        mode="morning_briefing",
        schema=schema,
        title="05/16/2026 Morning",
    )
    row = db_session.get(Report, report_id)
    assert row.title == "05/16/2026 Morning"


def test_get_report_scoped_to_owner(db_session, seeded_user, other_user):
    schema = _sample_schema()
    report_id = create_report(
        db_session,
        user_id=seeded_user.id,
        department="equity_research",
        mode="initiation",
        schema=schema,
    )
    with pytest.raises(ReportNotFoundError):
        get_report(db_session, report_id=report_id, user_id=other_user.id)
