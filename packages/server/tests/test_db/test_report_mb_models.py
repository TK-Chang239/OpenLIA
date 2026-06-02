from openlia_server.db.models.report_mb import (
    ReportMb,
    ReportMbChart,
    ReportMbCitation,
    ReportMbInstructions,
    ReportMbSection,
    ReportMbTemplate,
    ReportMbToolCallLog,
)


def test_report_mb_columns():
    cols = {c.name for c in ReportMb.__table__.columns}
    assert {
        "id",
        "user_id",
        "subject",
        "trigger_kind",
        "schedule_id",
        "template_id",
        "instructions_id",
        "status",
        "created_at",
    } <= cols
    # MB runs are template/instructions driven, never ticker-anchored.
    assert "ticker" not in cols
    assert "fiscal_date" not in cols


def test_report_mb_schedule_id_is_nullable():
    col = ReportMb.__table__.columns["schedule_id"]
    assert col.nullable is True


def test_report_mb_instructions_id_is_nullable():
    col = ReportMb.__table__.columns["instructions_id"]
    assert col.nullable is True


def test_report_mb_tablenames():
    assert ReportMb.__tablename__ == "report_mb"
    assert ReportMbSection.__tablename__ == "report_mb_sections"
    assert ReportMbChart.__tablename__ == "report_mb_charts"
    assert ReportMbCitation.__tablename__ == "report_mb_citations"
    assert ReportMbToolCallLog.__tablename__ == "report_mb_tool_call_log"
    assert ReportMbTemplate.__tablename__ == "report_mb_templates"
    assert ReportMbInstructions.__tablename__ == "report_mb_instructions"
