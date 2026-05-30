from openlia_server.db.models.report_eu import (
    EuV2EarningsSchedule,
    EuV2Settings,
    EuV2WatchlistEntry,
    ReportEu,
    ReportEuInstructions,
    ReportEuSection,
    ReportEuTemplate,
)


def test_tablenames():
    assert ReportEu.__tablename__ == "report_eu"
    assert ReportEuSection.__tablename__ == "report_eu_sections"
    assert ReportEuTemplate.__tablename__ == "report_eu_templates"
    assert EuV2WatchlistEntry.__tablename__ == "eu_v2_watchlist"
    assert EuV2EarningsSchedule.__tablename__ == "eu_v2_earnings_schedule"
    assert EuV2Settings.__tablename__ == "eu_v2_settings"


def test_settings_connector_defaults_are_columns():
    cols = {c.name for c in EuV2Settings.__table__.columns}
    assert {"financial_enabled", "calendar_enabled", "web_search_enabled"} <= cols


def test_instructions_model_shape():
    assert ReportEuInstructions.__tablename__ == "report_eu_instructions"
    cols = {c.name for c in ReportEuInstructions.__table__.columns}
    assert {
        "id",
        "user_id",
        "name",
        "is_builtin",
        "body_text",
        "source_doc_blob",
        "source_doc_mime",
        "created_at",
        "updated_at",
        "deleted_at",
    } <= cols


def test_settings_has_nullable_instructions_id():
    col = EuV2Settings.__table__.columns["instructions_id"]
    assert col.nullable is True


def test_schedule_dedup_unique_constraint():
    uniques = [
        tuple(c.name for c in con.columns)
        for con in EuV2EarningsSchedule.__table__.constraints
        if con.__class__.__name__ == "UniqueConstraint"
    ]
    assert ("user_id", "ticker", "fiscal_date") in uniques
