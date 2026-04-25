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
from openlia_server.services.reports import (
    ReportNotFoundError,
    create_report,
    get_report,
)


def _sample_schema() -> ReportSchema:
    return ReportSchema(
        schema_version="1.0",
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
