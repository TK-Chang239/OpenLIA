from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from _macro_research_fakes import FakeDataProvider
from openlia_server.services.mr_runner import MRRunner


@pytest.fixture
def runner() -> MRRunner:
    data = FakeDataProvider(
        values={
            "macro_indicator:debt_gdp": 105.0,
            "macro_indicator:interest_revenue": 12.0,
            "stock_quote:TIP": {"price": 110.0},
            "stock_quote:UUP": {"price": 29.5},
        }
    )
    cache = MagicMock()
    cache.read_latest.return_value = {
        "assessment": "Late plateau risk",
        "severity": "amber",
        "generated_at": datetime.now(UTC),
    }
    dashboard_svc = MagicMock()
    dashboard_svc.get_or_create.return_value = MagicMock(view_config={}, threshold_overrides={})

    # session_factory must return a context manager — MagicMock supports this
    # out of the box via the auto-configured __enter__/__exit__ methods.
    return MRRunner(
        data_provider=data,
        cache_store=cache,
        dashboard_service=dashboard_svc,
        session_factory=MagicMock,
    )


def test_run_returns_dashboard_result(runner: MRRunner) -> None:
    result = runner.run(
        user_id="u-1",
        dashboard_slug="debt_cycle",
        portfolio=None,
        smart_mode=False,
    )
    assert result.slug == "debt_cycle"
    assert len(result.tiers) == 5
    t4 = next(t for t in result.tiers if t.tier == "T4")
    assert t4.data["assessment"] == "Late plateau risk"


def test_run_unknown_slug_raises(runner: MRRunner) -> None:
    with pytest.raises(KeyError):
        runner.run(
            user_id="u-1",
            dashboard_slug="not_real",
            portfolio=None,
            smart_mode=False,
        )


def test_run_propagates_dashboard_service_errors() -> None:
    """NEW-19-07: programming errors in dashboard_service must escape, not
    be swallowed. Only IntegrityError (racy unique-constraint hit) is
    silently retried.
    """
    data = FakeDataProvider(values={})
    cache = MagicMock()
    cache.read_latest.return_value = None
    dashboard_svc = MagicMock()
    dashboard_svc.get_or_create.side_effect = RuntimeError("boom")
    runner = MRRunner(
        data_provider=data,
        cache_store=cache,
        dashboard_service=dashboard_svc,
        session_factory=MagicMock,
    )
    with pytest.raises(RuntimeError, match="boom"):
        runner.run(
            user_id="u-1",
            dashboard_slug="debt_cycle",
            portfolio=None,
            smart_mode=False,
        )
