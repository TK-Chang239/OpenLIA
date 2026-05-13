from __future__ import annotations

import pytest
from openlia_server.scheduler.registry import (
    MAINTENANCE_JOB_KEY,
    JobStatus,
    JobType,
    NotificationType,
    department_for_job_type,
    job_key,
    parse_job_key,
)


def test_job_types_match_spec() -> None:
    assert {t.value for t in JobType} == {
        "mb_briefing",
        "eu_scan",
        "mr_assessment",
        "rs_snapshot",
        "graph_extraction",
        "system_maintenance",
        "portfolio_price_refresh",
    }


def test_portfolio_price_refresh_job_key_is_global() -> None:
    """The portfolio refresh job is global (not per-user) so its key has no
    user_id segment."""
    from openlia_server.scheduler.registry import PORTFOLIO_PRICE_REFRESH_KEY

    assert PORTFOLIO_PRICE_REFRESH_KEY == "portfolio_price_refresh"
    assert job_key(JobType.PORTFOLIO_PRICE_REFRESH, user_id=None) == ("portfolio_price_refresh")


def test_job_statuses_match_spec() -> None:
    assert {s.value for s in JobStatus} == {"running", "completed", "failed", "cancelled"}


def test_notification_types_match_spec() -> None:
    assert {n.value for n in NotificationType} == {
        "report_ready",
        "assessment_ready",
        "job_failed",
        "panic_level_change",
    }


def test_job_key_user_scoped() -> None:
    assert job_key(JobType.MB_BRIEFING, user_id="u_abc") == "mb_briefing:u_abc"
    assert job_key(JobType.EU_SCAN, user_id="u_abc") == "eu_scan:u_abc"
    assert job_key(JobType.MR_ASSESSMENT, user_id="u_abc") == "mr_assessment:u_abc"


def test_job_key_maintenance_has_fixed_key() -> None:
    assert MAINTENANCE_JOB_KEY == "system_maintenance"
    assert job_key(JobType.SYSTEM_MAINTENANCE, user_id=None) == "system_maintenance"


def test_job_key_user_scoped_requires_user_id() -> None:
    with pytest.raises(ValueError, match="user_id required"):
        job_key(JobType.MB_BRIEFING, user_id=None)


def test_parse_job_key_round_trips() -> None:
    assert parse_job_key("mb_briefing:u_abc") == (JobType.MB_BRIEFING, "u_abc")
    assert parse_job_key("system_maintenance") == (JobType.SYSTEM_MAINTENANCE, None)


def test_parse_job_key_rejects_unknown_prefix() -> None:
    with pytest.raises(ValueError, match="unknown job type"):
        parse_job_key("garbage:u_abc")


def test_department_mapping() -> None:
    assert department_for_job_type(JobType.MB_BRIEFING) == "morning_briefing"
    assert department_for_job_type(JobType.EU_SCAN) == "earnings_update"
    assert department_for_job_type(JobType.MR_ASSESSMENT) == "macro_research"
    assert department_for_job_type(JobType.RS_SNAPSHOT) == "retail_sentiment"
    assert department_for_job_type(JobType.GRAPH_EXTRACTION) == "secretary"


def test_department_mapping_rejects_maintenance() -> None:
    with pytest.raises(ValueError, match="no department"):
        department_for_job_type(JobType.SYSTEM_MAINTENANCE)
