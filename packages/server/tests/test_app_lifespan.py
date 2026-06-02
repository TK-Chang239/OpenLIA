from __future__ import annotations

import os
from unittest.mock import patch

from fastapi.testclient import TestClient


def test_lifespan_sets_scheduler_on_app_state_when_enabled() -> None:
    """With OPENLIA_SCHEDULER_ENABLED=1, the lifespan must create the
    SchedulerService and park it on app.state.scheduler."""
    with patch.dict(
        os.environ,
        {
            "OPENLIA_SCHEDULER_ENABLED": "1",
            "OPENLIA_DB_URL": "sqlite:///:memory:",
        },
        clear=False,
    ):
        from openlia_server.app import create_app

        app = create_app()
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
            assert getattr(app.state, "scheduler", None) is not None
            assert app.state.scheduler.is_running is True


def test_lifespan_skips_scheduler_when_disabled() -> None:
    with patch.dict(
        os.environ,
        {
            "OPENLIA_SCHEDULER_ENABLED": "0",
            "OPENLIA_DB_URL": "sqlite:///:memory:",
        },
        clear=False,
    ):
        from openlia_server.app import create_app

        app = create_app()
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
            # Either attribute is missing or is_running=False.
            svc = getattr(app.state, "scheduler", None)
            assert svc is None or svc.is_running is False


def test_scheduler_wires_real_builders() -> None:
    """Production lifespan must inject real-impl builders, not stubs.

    Walks the executor graph after `create_app()` boots and confirms each
    executor holds the named real implementation. Also asserts that the
    MR executor receives a non-None batch_runner — guards P0-04."""
    from openlia_server.scheduler.registry import JobType

    with patch.dict(
        os.environ,
        {
            "OPENLIA_SCHEDULER_ENABLED": "1",
            "OPENLIA_DB_URL": "sqlite:///:memory:",
        },
        clear=False,
    ):
        from openlia_server.app import create_app

        app = create_app()
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
            scheduler_svc = app.state.scheduler
            assert scheduler_svc is not None

            mb_exec = scheduler_svc.executors[JobType.MB_BRIEFING]
            eu_exec = scheduler_svc.executors[JobType.EU_SCAN]
            mr_exec = scheduler_svc.executors[JobType.MR_ASSESSMENT]

            # The MB executor runs the report_mb engine inline via
            # mb_v2_run_service.
            from openlia_server.services import mb_v2_run_service

            assert mb_exec._run_service is mb_v2_run_service
            assert type(eu_exec._eu_planner).__name__ == "EuScanPlannerImpl"
            assert type(mr_exec._mr_builder).__name__ == "MRAssessmentBuilderImpl"
            assert type(mr_exec._mr_cache_store).__name__ == "MRCacheStoreImpl"
            assert mr_exec._batch_runner is not None


def test_production_wiring_has_batch_runner() -> None:
    """P0-04 acceptance: MR executor receives a real BatchRunner."""
    from openlia_server.scheduler.registry import JobType

    with patch.dict(
        os.environ,
        {
            "OPENLIA_SCHEDULER_ENABLED": "1",
            "OPENLIA_DB_URL": "sqlite:///:memory:",
        },
        clear=False,
    ):
        from openlia_server.app import create_app

        app = create_app()
        with TestClient(app):
            mr_exec = app.state.scheduler.executors[JobType.MR_ASSESSMENT]
            assert mr_exec._batch_runner is not None


def test_lifespan_exposes_wizard_background_task_set() -> None:
    """NEW-10-14: the lifespan exposes the wizard background-task set so it can
    cancel any in-flight review on shutdown. The set lives on app.state and is
    distinct per-app (router-factory closure, not module scope)."""
    from openlia_server.app import create_app

    with patch.dict(
        os.environ,
        {
            "OPENLIA_SCHEDULER_ENABLED": "0",
            "OPENLIA_DB_URL": "sqlite:///:memory:",
        },
        clear=False,
    ):
        app = create_app()
        with TestClient(app):
            assert isinstance(app.state.setup_background_tasks, set)

        # Two apps should have independent task sets — proves the set lives in
        # the router-factory closure, not at module scope.
        app2 = create_app()
        assert app.state.setup_background_tasks is not app2.state.setup_background_tasks
