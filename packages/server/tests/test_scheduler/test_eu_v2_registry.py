from __future__ import annotations

from openlia_server.scheduler.registry import (
    EU_V2_DISPATCH_KEY,
    EU_V2_SYNC_KEY,
    JobType,
    department_for_job_type,
    job_key,
    parse_job_key,
)


def test_eu_v2_job_types_exist():
    assert JobType.EU_V2_SYNC.value == "eu_v2_sync"
    assert JobType.EU_V2_DISPATCH.value == "eu_v2_dispatch"


def test_department_mapping():
    assert department_for_job_type(JobType.EU_V2_SYNC) == "earnings_update_v2"
    assert department_for_job_type(JobType.EU_V2_DISPATCH) == "earnings_update_v2"


def test_job_key_is_global_fixed():
    assert job_key(JobType.EU_V2_SYNC) == EU_V2_SYNC_KEY
    assert job_key(JobType.EU_V2_DISPATCH) == EU_V2_DISPATCH_KEY


def test_parse_job_key_round_trips():
    assert parse_job_key(EU_V2_SYNC_KEY) == (JobType.EU_V2_SYNC, None)
    assert parse_job_key(EU_V2_DISPATCH_KEY) == (JobType.EU_V2_DISPATCH, None)
