"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any

from apscheduler import AsyncScheduler
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session as DBSession
from sqlalchemy.orm import sessionmaker

import openlia_server.db.models  # noqa: F401 — registers all models on Base.metadata
from openlia_server.db.base import Base
from openlia_server.db.bootstrap import resolve_db_url
from openlia_server.db.session import SessionLocal, configure_engine, get_engine
from openlia_server.routes.admin import build_admin_router
from openlia_server.routes.auth import build_auth_router
from openlia_server.routes.chat_stream import build_chat_stream_router
from openlia_server.routes.departments.earnings_update import (
    build_earnings_update_router,
)
from openlia_server.routes.departments.equity_research import (
    build_equity_research_router,
)
from openlia_server.routes.jobs import build_jobs_router
from openlia_server.routes.notifications import build_notifications_router
from openlia_server.routes.reports import build_reports_router
from openlia_server.routes.settings import (
    build_data_providers_router,
    build_llm_providers_admin_router,
)
from openlia_server.routes.setup import build_setup_router
from openlia_server.scheduler.service import SchedulerService
from openlia_server.scheduler.settings import SchedulerSettings
from openlia_server.scheduler.wiring import build_scheduler_service
from openlia_server.services.eu_scan_planner import EuScanPlannerImpl
from openlia_server.services.report_export import BrowserLauncher
from openlia_server.services.runtime import build_chat_runner, build_report_runner


class _NoopEarningsRecentAdapter:
    """Fallback adapter used when the earnings_data provider isn't wired.

    Implements both the EuScanPlanner `latest_release` shape and the
    EU watchlist `next_earnings` shape so scheduled scans and the
    on-demand watchlist route degrade gracefully (no releases / ticker
    not found) rather than crashing the executor or returning 500.
    """

    def latest_release(self, ticker: str, *, since):  # type: ignore[no-untyped-def]
        return None

    def next_earnings(self, ticker: str):  # type: ignore[no-untyped-def]
        return None


log = logging.getLogger(__name__)


class _SchedulerAdapter:
    """Thin wrapper around APScheduler's AsyncScheduler.

    APScheduler 4.x requires the scheduler to be entered as an async context
    manager before any of its methods can be called. SchedulerService expects
    a scheduler whose `start_in_background()` is *synchronous* (matching the
    FakeAPScheduler contract used in tests). This adapter bridges the gap:

    - It must be entered via `async with` (to initialize APScheduler services)
      before being passed to SchedulerService.
    - `start_in_background()` is synchronous and schedules the APScheduler
      background task onto the running event loop.
    """

    def __init__(self) -> None:
        self._sched = AsyncScheduler()
        self._bg_task: asyncio.Task | None = None

    async def __aenter__(self) -> _SchedulerAdapter:
        await self._sched.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self._sched.__aexit__(*args)

    def start_in_background(self) -> None:
        """Launch the APScheduler event loop in a background task."""
        self._bg_task = asyncio.ensure_future(self._sched.start_in_background())

    async def stop(self) -> None:
        await self._sched.stop()
        if self._bg_task is not None:
            self._bg_task.cancel()
            try:
                await self._bg_task
            except asyncio.CancelledError:
                pass
            except Exception:
                log.debug("error during scheduler teardown (ignored)", exc_info=True)

    async def add_schedule(self, *args: Any, **kwargs: Any) -> Any:
        return await self._sched.add_schedule(*args, **kwargs)

    async def remove_schedule(self, id: str) -> None:
        await self._sched.remove_schedule(id)

    async def get_schedules(self) -> list:
        return await self._sched.get_schedules()


def _is_loopback_request(request: Request) -> bool:
    client = request.client
    if client is None:
        return True
    return client.host in ("127.0.0.1", "::1", "localhost")


def _default_session_factory() -> DBSession:
    get_engine()
    return SessionLocal()


def _make_lifespan(
    db_session_factory: Callable[[], DBSession] | None,
) -> Callable[[FastAPI], AsyncGenerator[None, None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        # Resolve the DB URL via the same helper the CLI bootstrap uses so
        # `openlia serve` and direct ASGI/factory deployments agree on the
        # effective database (single source of truth: OPENLIA_DB_URL).
        configured_explicit_url = bool(os.environ.get("OPENLIA_DB_URL"))
        db_url = resolve_db_url() if configured_explicit_url else None
        if db_url:
            engine = configure_engine(db_url)
            # For SQLite (dev/test), create tables automatically — production
            # uses Alembic migrations so create_all is a no-op there.
            if engine.url.drivername == "sqlite":
                Base.metadata.create_all(engine)

        browser_launcher = BrowserLauncher()
        app.state.browser_launcher = browser_launcher

        scheduler_settings = SchedulerSettings.from_env()
        scheduler_svc: SchedulerService | None = None

        if scheduler_settings.enabled:
            # Build a sessionmaker for the scheduler that supports context
            # manager usage (session_factory() as a context manager).
            if db_url:
                _engine = get_engine()
                _sm = sessionmaker(
                    bind=_engine,
                    autoflush=False,
                    autocommit=False,
                    expire_on_commit=False,
                )
            else:
                _sf = db_session_factory or _default_session_factory

                @contextlib.contextmanager
                def _sm():  # type: ignore[misc]
                    s = _sf()
                    try:
                        yield s
                    finally:
                        s.close()

            adapter = _SchedulerAdapter()
            earnings_adapter = (
                getattr(app.state, "earnings_recent_adapter", None) or _NoopEarningsRecentAdapter()
            )
            eu_planner = EuScanPlannerImpl(adapter=earnings_adapter)
            async with adapter:
                scheduler_svc = build_scheduler_service(
                    session_factory=_sm,
                    settings=scheduler_settings,
                    scheduler=adapter,
                    report_runner=build_report_runner(_sm),
                    batch_runner=None,
                    eu_planner=eu_planner,
                )
                await scheduler_svc.start()

                app.state.scheduler = scheduler_svc

                try:
                    yield
                finally:
                    await scheduler_svc.shutdown()
                    await browser_launcher.shutdown()

            return

        app.state.scheduler = scheduler_svc
        try:
            yield
        finally:
            await browser_launcher.shutdown()

    return lifespan


def create_app(
    *,
    db_session_factory: Callable[[], DBSession] | None = None,
    is_loopback_request: Callable[[Request], bool] | None = None,
) -> FastAPI:
    factory = db_session_factory or _default_session_factory
    mode = os.environ.get("OPENLIA_MODE", "personal").lower()
    app = FastAPI(
        title="OpenLIA",
        version="0.0.0",
        lifespan=_make_lifespan(db_session_factory),
    )

    app.include_router(
        build_setup_router(
            db_session_factory=factory,
            mode=mode,
            is_loopback_request=is_loopback_request or _is_loopback_request,
        )
    )

    if mode == "company":
        app.include_router(build_auth_router(db_session_factory=factory))
        app.include_router(build_admin_router(db_session_factory=factory))

    app.include_router(build_data_providers_router(db_session_factory=factory))
    app.include_router(build_llm_providers_admin_router(db_session_factory=factory, mode=mode))
    app.include_router(build_jobs_router(db_session_factory=factory, mode=mode))
    app.include_router(build_notifications_router(db_session_factory=factory, mode=mode))
    app.include_router(build_reports_router(db_session_factory=factory, mode=mode))
    app.include_router(build_equity_research_router(db_session_factory=factory, mode=mode))
    app.include_router(build_earnings_update_router(db_session_factory=factory, mode=mode))
    app.state.chat_runner_factory = lambda: build_chat_runner(db_session_factory=factory)
    # Report runner is consumed by per-department routes (equity_research, earnings_update).
    # `build_report_runner` returns a RefreshingReportRunner that opens a fresh DB session
    # per run, so we can share a single instance across requests.
    app.state.report_runner = build_report_runner(db_session_factory=factory)
    app.state.equity_research_inner_factory = lambda: build_report_runner(
        db_session_factory=factory
    )
    # Earnings data adapter — optional; when unset the EU on-demand route uses a no-op.
    app.state.earnings_adapter = getattr(
        app.state, "earnings_adapter", _NoopEarningsRecentAdapter()
    )
    app.include_router(build_chat_stream_router(db_session_factory=factory, mode=mode))

    from openlia_server.routes.chat_sessions import build_chat_sessions_router

    app.include_router(build_chat_sessions_router(db_session_factory=factory, mode=mode))

    from openlia_server.routes.repo import build_repo_router

    app.include_router(build_repo_router(db_session_factory=factory, mode=mode))

    from openlia_server.routes.files import build_files_router

    app.include_router(build_files_router(db_session_factory=factory, mode=mode))

    from openlia_server.routes.settings_general import build_settings_general_router

    app.include_router(build_settings_general_router(db_session_factory=factory, mode=mode))

    from openlia_server.routes.settings_email import build_settings_email_router

    app.include_router(build_settings_email_router(db_session_factory=factory, mode=mode))

    from openlia_server.routes.settings_models import build_settings_models_router

    app.include_router(build_settings_models_router(db_session_factory=factory, mode=mode))

    from openlia_server.routes.eu_schedules import build_eu_schedules_router

    app.include_router(build_eu_schedules_router(db_session_factory=factory, mode=mode))

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "mode": mode}

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    _mount_frontend(app)

    return app


_API_PREFIXES = (
    "auth",
    "admin",
    "settings",
    "setup",
    "jobs",
    "notifications",
    "reports",
    "departments",
    "chat",
    "repo",
    "healthz",
    "health",
    "docs",
    "redoc",
    "openapi.json",
)


def _mount_frontend(app: FastAPI) -> None:
    """Serve `frontend/dist` with SPA fallback when configured.

    Skips silently if `OPENLIA_FRONTEND_DIST` is unset or the directory does
    not yet exist, so dev servers and tests don't need a built bundle.
    """
    dist_env = os.environ.get("OPENLIA_FRONTEND_DIST")
    if not dist_env:
        return
    dist_dir = os.path.abspath(dist_env)
    if not os.path.isdir(dist_dir):
        return
    index_html = os.path.join(dist_dir, "index.html")
    if not os.path.isfile(index_html):
        return

    assets_dir = os.path.join(dist_dir, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        head = full_path.split("/", 1)[0]
        if head in _API_PREFIXES:
            raise HTTPException(status_code=404)
        candidate = os.path.normpath(os.path.join(dist_dir, full_path))
        if full_path and candidate.startswith(dist_dir + os.sep) and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(index_html)
