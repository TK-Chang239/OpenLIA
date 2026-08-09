"""FastAPI application factory.

Environment contract (production-relevant subset):

    OPENLIA_MODE                 personal | company (default: personal)
    OPENLIA_DB_URL               SQLAlchemy URL; defaults to ~/.openlia/openlia.db
    OPENLIA_FRONTEND_DIST        Absolute path to built SPA. Resolution order:
                                   1. this env var
                                   2. /app/frontend/dist (Docker image default)
                                   3. <repo>/frontend/dist (local npm build)
    OPENLIA_TRUST_PROXY_HEADERS  "true" to honor X-Forwarded-For /
                                   X-Forwarded-Proto (for Cloudflare Tunnel,
                                   Caddy, or any TLS-terminating proxy).
    OPENLIA_COOKIE_SECURE        "true" forces Secure flag on session cookies;
                                   defaults to true when OPENLIA_MODE=company,
                                   false otherwise.
    OPENLIA_SCHEDULER_ENABLED    "true" to run APScheduler jobs; default true.
    OPENLIA_SECRET_KEY           32-byte base64 AES-256-GCM key; if unset, the
                                   server reads/writes ~/.openlia/secret.key.

The `/api/...` prefix from the dev Vite proxy is also stripped at runtime by
`_StripApiPrefixMiddleware` so the same built bundle works locally and in
production (Caddy, Cloudflare Tunnel) without per-environment rewrites.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from apscheduler import AsyncScheduler
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openlia.llm.runtime.prompts import PromptLoader
from sqlalchemy.orm import Session as DBSession
from sqlalchemy.orm import sessionmaker
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

import openlia_server.db.models  # noqa: F401 — registers all models on Base.metadata
from openlia_server.db.base import Base
from openlia_server.db.bootstrap import resolve_db_url
from openlia_server.db.session import SessionLocal, configure_engine, get_engine
from openlia_server.routes.admin import build_admin_router
from openlia_server.routes.auth import build_auth_router
from openlia_server.routes.chat_stream import build_chat_stream_router
from openlia_server.routes.connectors import build_connectors_router
from openlia_server.routes.departments.earnings_update import (
    build_earnings_update_router,
)
from openlia_server.routes.departments.earnings_update_v2 import (
    build_earnings_update_v2_router,
)
from openlia_server.routes.departments.equity_research_v3 import (
    build_equity_research_v3_router,
)
from openlia_server.routes.departments.macro_research import (
    build_macro_research_router,
)
from openlia_server.routes.departments.morning_briefing import (
    build_morning_briefing_router,
)
from openlia_server.routes.departments.panic_thermometer import (
    build_panic_thermometer_router,
)
from openlia_server.routes.departments.retail_sentiment import (
    build_retail_sentiment_router,
)
from openlia_server.routes.departments.secretary import build_secretary_router
from openlia_server.routes.dept_health import build_dept_health_router
from openlia_server.routes.disclaimer import build_disclaimer_router
from openlia_server.routes.guardrail_events import build_guardrail_events_router
from openlia_server.routes.jobs import build_jobs_router
from openlia_server.routes.mr_schedules import build_mr_schedule_router
from openlia_server.routes.notifications import build_notifications_router
from openlia_server.routes.notifications_stream import build_notifications_stream_router
from openlia_server.routes.portfolio import build_portfolio_router
from openlia_server.routes.reports import build_reports_router
from openlia_server.routes.reports_revise import build_reports_revise_router
from openlia_server.routes.reports_stream import build_reports_stream_router
from openlia_server.routes.settings import (
    build_llm_providers_admin_router,
)
from openlia_server.routes.settings_llm_slots import (
    build_llm_slot_defaults_router,
)
from openlia_server.routes.setup import build_setup_router
from openlia_server.scheduler.service import SchedulerService
from openlia_server.scheduler.settings import SchedulerSettings
from openlia_server.scheduler.wiring import build_scheduler_service
from openlia_server.services.auto_cancel_sweep import auto_cancel_loop
from openlia_server.services.background_report_registry import BackgroundReportRegistry
from openlia_server.services.eu_scan_planner import EuScanPlannerImpl
from openlia_server.services.pt_config import PtConfigService
from openlia_server.services.pt_runner import PtRunner
from openlia_server.services.pt_wiring import build_pt_dispatcher
from openlia_server.services.report_export import BrowserLauncher
from openlia_server.services.runtime import (
    build_chat_runner,
    build_report_runner,
)
from openlia_server.services.user_presence_registry import UserPresenceRegistry

# Per-department expected prompt slots; validated at startup so a missing or
# renamed slot fails the boot rather than the first user request.
_DEPARTMENT_SLOTS: dict[str, list[str]] = {
    "secretary": ["chat.system", "chat.welcome"],
    "equity_research": [
        "chat.system",
        "report.system",
        "report.stock_initiation.user",
        "report.stock_update.user",
        "report.sector_research.user",
    ],
    "earnings_update": [
        "report.system",
        "report.earnings_update.user",
    ],
    # MB v2 (report_mb) builds its own system prompt in code; only the chat
    # slot (Secretary "ask about a past briefing") is loaded from YAML.
    "morning_briefing": ["chat.system"],
    "macro_research": [
        "batch.t4_assessment.system",
        "batch.t4_assessment.user",
        "batch.t5_assessment.system",
        "batch.t5_assessment.user",
    ],
    "retail_sentiment": [
        "batch.classify_sentiment.system",
        "batch.classify_sentiment.user",
    ],
}


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


def _configure_app_logging() -> None:
    """Install an INFO-level stdout handler on the ``openlia`` and
    ``openlia_server`` loggers.

    Uvicorn's default LOGGING_CONFIG attaches handlers only to its own
    ``uvicorn.*`` namespaces, so application loggers fall through to
    Python's lastResort handler, which emits at WARNING+ and silently
    drops INFO. Without this, per-stage telemetry like the ``llm_usage``
    lines from ``v2_stage_factory`` never reaches the log even though
    the code is calling ``log.info(...)``.

    We target only ``openlia*`` so chatty third-party libraries (httpx,
    asyncio, sqlalchemy.engine) stay at their library defaults. The
    handler is tagged so the function is idempotent under repeated
    ``create_app()`` calls in tests.
    """
    formatter = logging.Formatter("%(levelname)s %(name)s: %(message)s")
    for name in ("openlia", "openlia_server"):
        logger = logging.getLogger(name)
        if any(getattr(h, "_openlia_app", False) for h in logger.handlers):
            continue
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        handler._openlia_app = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)


def sweep_orphaned_generating_reports(db_session_factory: Callable) -> int:
    """Mark any 'generating' report rows as 'failed' with reason 'server_restart_interrupted'.

    Called once at startup to clean up rows left in the 'generating' state by a
    previous server process that exited while a background report job was running.
    Returns the number of rows updated.
    """
    from openlia_server.db.models.content import Report

    with db_session_factory() as session:
        orphans = session.query(Report).filter(Report.status == "generating").all()
        for row in orphans:
            row.status = "failed"
            row.failure_reason = "server_restart_interrupted"
        session.commit()
    return len(orphans)


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

    def __init__(self, *, max_concurrent_jobs: int | None = None) -> None:
        if max_concurrent_jobs is not None:
            self._sched = AsyncScheduler(max_concurrent_jobs=max_concurrent_jobs)
        else:
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
        # APScheduler 4.x has no per-schedule `max_instances` knob — the
        # in-process self-rolled guard in SchedulerService._active_tokens
        # enforces single-instance semantics. Strip the kwarg so production
        # wiring stays compatible with the spec-mandated API while the
        # FakeAPScheduler in tests records it for assertions.
        kwargs.pop("max_instances", None)
        coalesce = kwargs.pop("coalesce", None)
        if coalesce is not None:
            from apscheduler import CoalescePolicy

            kwargs["coalesce"] = CoalescePolicy.latest if coalesce else CoalescePolicy.earliest
        return await self._sched.add_schedule(*args, **kwargs)

    async def remove_schedule(self, id: str) -> None:
        await self._sched.remove_schedule(id)

    async def get_schedules(self) -> list:
        return await self._sched.get_schedules()


class _StripApiPrefixMiddleware:
    """Strip a leading `/api` segment from incoming HTTP paths.

    Mirrors the Vite dev proxy (`rewrite: (p) => p.replace(/^\\/api/, "")`)
    so the built SPA can call `/api/...` in production and dev without
    branching on environment. Non-HTTP scopes pass through unchanged.
    """

    def __init__(self, app: Any) -> None:
        self._app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope.get("type") == "http":
            path = scope.get("path", "")
            raw_path = scope.get("raw_path")
            if path == "/api" or path.startswith("/api/"):
                new_path = path[4:] or "/"
                scope = dict(scope)
                scope["path"] = new_path
                scope["openlia_was_api"] = True
                if raw_path is not None and (raw_path.startswith(b"/api/") or raw_path == b"/api"):
                    scope["raw_path"] = raw_path[4:] or b"/"
        await self._app(scope, receive, send)


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

        # Sweep any 'generating' rows left over from a previous server process
        # that exited mid-run. Must run before any report background tasks start.
        _sweep_sf = db_session_factory or _default_session_factory
        swept = sweep_orphaned_generating_reports(_sweep_sf)
        if swept:
            log.info("startup sweep: marked %d orphaned 'generating' report(s) as failed", swept)

        # Validate prompt slots once at boot. PromptSlotNotFound propagates
        # and prevents the server from starting if any slot is missing.
        prompt_root = getattr(app.state, "prompt_root", None)
        prompt_loader = PromptLoader(root=prompt_root) if prompt_root else PromptLoader()
        for department_id, slots in _DEPARTMENT_SLOTS.items():
            prompt_loader.validate_department_slots(department_id, expected=slots)

        browser_launcher = BrowserLauncher()
        app.state.browser_launcher = browser_launcher

        # The eodhd SDK issues un-timed HTTP; a hung endpoint would block
        # a report run indefinitely (the engine's wall-time guard only
        # checks between turns). Inject a process-wide network timeout so
        # every EODHD call (v3 / Earnings Update / Morning Briefing) is
        # bounded. Must run before any report background task fires.
        from openlia_server.services.eodhd_hardening import harden_eodhd_timeout

        harden_eodhd_timeout()

        # v3 streaming infrastructure: in-memory broker fanned out to
        # SSE subscribers + per-run cancel-token registry. Lives for
        # the lifetime of the process; nothing persisted here.
        from openlia.llm.runtime.report_v3 import EventBroker

        from openlia_server.services.v3_run_service import (
            cleanup_orphaned_running_rows as _v3_cleanup,
        )

        app.state.v3_event_broker = EventBroker()
        app.state.v3_cancel_registry = {}
        app.state.eu_v2_event_broker = EventBroker()
        app.state.eu_v2_cancel_registry = {}

        from openlia.llm.runtime.report_mb import EventBroker as _MbEventBroker

        app.state.mb_v2_event_broker = _MbEventBroker()
        app.state.mb_v2_cancel_registry = {}
        _v3_sweep_sf = db_session_factory or _default_session_factory
        with _v3_sweep_sf() as _v3_sweep_db:
            _v3_swept = _v3_cleanup(db=_v3_sweep_db)
        if _v3_swept:
            log.info("startup sweep: marked %d orphaned v3 run(s) as failed", _v3_swept)

        from openlia_server.services.eu_v2_run_service import (
            cleanup_orphaned_running_rows as _eu_v2_cleanup,
        )

        with _v3_sweep_sf() as _eu_v2_sweep_db:
            _eu_v2_swept = _eu_v2_cleanup(db=_eu_v2_sweep_db)
        if _eu_v2_swept:
            log.info("startup sweep: marked %d orphaned eu_v2 run(s) as failed", _eu_v2_swept)

        from openlia_server.services.mb_v2_run_service import (
            cleanup_orphaned_running_rows as _mb_v2_cleanup,
        )

        with _v3_sweep_sf() as _mb_v2_sweep_db:
            _mb_v2_swept = _mb_v2_cleanup(db=_mb_v2_sweep_db)
        if _mb_v2_swept:
            log.info("startup sweep: marked %d orphaned mb_v2 run(s) as failed", _mb_v2_swept)

        # Resume in-flight batch jobs from before the restart (the EU run sweep
        # above skips their reports). Un-resumable jobs are failed by recovery.
        from openlia_server.services.eu_v2_batch_service import (
            recover_inflight_batches as _eu_v2_batch_recover,
        )

        _eu_v2_batch_resumed = _eu_v2_batch_recover(session_factory=_v3_sweep_sf)
        if _eu_v2_batch_resumed:
            log.info(
                "startup: resumed %d in-flight eu_v2 batch job(s)",
                _eu_v2_batch_resumed,
            )

        from openlia_server.routes.reports import _resolve_frontend_dist
        from openlia_server.services.render_base_url import (
            RenderBaseUrlResolver,
            default_probe,
        )

        app.state.render_base_url_resolver = RenderBaseUrlResolver(
            server_url=os.environ.get("OPENLIA_SERVER_URL", "http://127.0.0.1:8000"),
            is_spa_served_locally=lambda: _resolve_frontend_dist() is not None,
            probe=default_probe,
        )

        # Background report registry + user presence — single instances for the
        # lifetime of this server process. Routes read from app.state so there
        # is no shared mutable module-level state.
        # user_presence is the canonical Task-16 key; user_presence_registry is
        # the legacy alias kept for existing route handlers.
        app.state.bg_report_registry = BackgroundReportRegistry()
        _presence = UserPresenceRegistry()
        app.state.user_presence = _presence
        app.state.user_presence_registry = _presence
        _sweep_sf2 = db_session_factory or _default_session_factory
        _sweep_task = asyncio.create_task(
            auto_cancel_loop(
                presence=app.state.user_presence,
                registry=app.state.bg_report_registry,
                db_session_factory=_sweep_sf2,
                grace_seconds=int(os.environ.get("OPENLIA_AUTO_CANCEL_GRACE_SECONDS", "90")),
                poll_seconds=int(os.environ.get("OPENLIA_AUTO_CANCEL_POLL_SECONDS", "15")),
            )
        )

        # Phase 10: populate dept-health cache. Every dept-route handler
        # and every scheduled-job pre-flight reads from app.state.dept_health.
        from openlia_server.services.dept_health import compute_all as _compute_all_health

        _sf = db_session_factory or _default_session_factory
        _health_session = _sf()
        try:
            app.state.dept_health = _compute_all_health(_health_session)
        except Exception:
            log.exception("startup dept_health computation failed; defaulting to empty map")
            app.state.dept_health = {}
        finally:
            _health_session.close()

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

            adapter = _SchedulerAdapter(max_concurrent_jobs=scheduler_settings.max_concurrent_jobs)
            earnings_adapter = (
                getattr(app.state, "earnings_recent_adapter", None) or _NoopEarningsRecentAdapter()
            )
            eu_planner = EuScanPlannerImpl(adapter=earnings_adapter)
            from openlia_server.services.mr_schedules import MRScheduleService
            from openlia_server.services.reports import ReportStoreImpl

            report_store_impl = ReportStoreImpl()

            # EU v2 is the sole live Earnings Update engine, so its scheduler
            # jobs (EU_V2_SYNC / EU_V2_DISPATCH executors and cadences) are
            # always registered. The EARNINGS_ENGINE_VERSION gate is retired.
            from openlia_server.services.eu_v2_scheduler_impl import (
                EuV2CalendarSyncerImpl,
                EuV2DispatcherImpl,
            )

            eu_v2_syncer = EuV2CalendarSyncerImpl()
            eu_v2_dispatcher = EuV2DispatcherImpl(session_factory=_sm)

            async with adapter:
                scheduler_svc = build_scheduler_service(
                    session_factory=_sm,
                    settings=scheduler_settings,
                    scheduler=adapter,
                    report_runner=build_report_runner(
                        _sm,
                        skill_registry=getattr(app.state, "skills_registry", None),
                    ),
                    eu_planner=eu_planner,
                    report_store=report_store_impl,
                    # Phase 1 portfolio live data: scheduled price refresh
                    # against app.state.financial_adapter at fire time.
                    financial_adapter_provider=lambda: getattr(
                        app.state, "financial_adapter", None
                    ),
                    eu_v2_syncer=eu_v2_syncer,
                    eu_v2_dispatcher=eu_v2_dispatcher,
                )
                # Phase 10: scheduler skip-on-disabled. Reads the live cache
                # off app.state at fire time so invalidation-driven recomputes
                # are picked up without a scheduler restart.
                scheduler_svc.dept_health_provider = lambda: getattr(app.state, "dept_health", None)
                await scheduler_svc.start()

                # Bind the scheduler-aware MRScheduleService onto app.state
                # so route handlers always reach the live scheduler. The
                # factory-time instance built below is only a fallback for
                # tests that bypass lifespan.
                mr_schedule_svc_lifespan = MRScheduleService(
                    session_factory=_sm, scheduler=scheduler_svc
                )
                try:
                    await mr_schedule_svc_lifespan.rehydrate_all()
                except (ValueError, RuntimeError, LookupError):
                    log.exception("MR schedule rehydration failed (continuing startup)")

                # Slice 6 (graph memory runtime): nightly extraction
                # job per user. Reads user_prefs.timezone +
                # user_prefs.graph_extraction_time.
                try:
                    from openlia_server.services import (
                        graph_extraction_rehydrate as _ge_rehydrate,
                    )

                    await _ge_rehydrate.rehydrate_all(
                        session_factory=_sm,
                        scheduler_control=scheduler_svc.scheduler,
                        callback=scheduler_svc._run_job,
                    )
                except (ValueError, RuntimeError, LookupError):
                    log.exception(
                        "graph extraction schedule rehydration failed (continuing startup)"
                    )

                app.state.scheduler = scheduler_svc
                app.state.mr_schedule_service = mr_schedule_svc_lifespan

                try:
                    yield
                finally:
                    _sweep_task.cancel()
                    for task in list(app.state.bg_report_registry._by_report_id.values()):
                        task.asyncio_task.cancel()
                    await scheduler_svc.shutdown()
                    await browser_launcher.shutdown()
                    await _cancel_wizard_background_tasks(app)

            return

        app.state.scheduler = scheduler_svc
        try:
            yield
        finally:
            _sweep_task.cancel()
            for task in list(app.state.bg_report_registry._by_report_id.values()):
                task.asyncio_task.cancel()
            await browser_launcher.shutdown()
            await _cancel_wizard_background_tasks(app)

    return lifespan


async def _cancel_wizard_background_tasks(app: FastAPI) -> None:
    tasks = getattr(app.state, "setup_background_tasks", None)
    if not tasks:
        return
    pending = [t for t in list(tasks) if not t.done()]
    for t in pending:
        t.cancel()
    if pending:
        try:
            await asyncio.gather(*pending, return_exceptions=True)
        except Exception:
            pass


def get_registry(request: Request) -> BackgroundReportRegistry:
    return request.app.state.bg_report_registry


def get_presence(request: Request) -> UserPresenceRegistry:
    return request.app.state.user_presence


def create_app(
    *,
    db_session_factory: Callable[[], DBSession] | None = None,
    is_loopback_request: Callable[[Request], bool] | None = None,
) -> FastAPI:
    _configure_app_logging()
    factory = db_session_factory or _default_session_factory
    mode = os.environ.get("OPENLIA_MODE", "personal").lower()
    app = FastAPI(
        title="OpenLIA",
        version="0.0.0",
        lifespan=_make_lifespan(db_session_factory),
    )

    app.add_middleware(_StripApiPrefixMiddleware)

    if os.environ.get("OPENLIA_TRUST_PROXY_HEADERS", "false").lower() in (
        "1",
        "true",
        "yes",
    ):
        app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

    setup_router = build_setup_router(
        db_session_factory=factory,
        mode=mode,
        is_loopback_request=is_loopback_request or _is_loopback_request,
    )
    app.include_router(setup_router)
    # Expose the wizard background-task set so the lifespan can cancel it on
    # shutdown (no leaks in tests that spin the app up multiple times).
    app.state.setup_background_tasks = getattr(setup_router, "state_background_tasks", set())

    if mode == "company":
        app.include_router(build_auth_router(db_session_factory=factory))
        app.include_router(build_admin_router(db_session_factory=factory))

    app.include_router(build_connectors_router(db_session_factory=factory, mode=mode))
    app.include_router(build_dept_health_router(db_session_factory=factory))

    # Phase 10: dept-health cache. Populated lazily on first read in tests
    # (see dept_health.compute_all) and refreshed at startup in the lifespan
    # below so the GET /api/dept-health endpoint always returns fresh state.
    # Type: dict[str, openlia.departments.health.DepartmentHealth].
    app.state.dept_health = {}

    # Wire connector mutation hook so the health cache stays in sync without
    # route handlers needing to know about it.
    from openlia_server.services import (
        connectors_service as _connectors_service,
    )
    from openlia_server.services import (
        dept_health as _dept_health_svc,
    )

    def _recompute_dept_health(session: DBSession) -> None:
        app.state.dept_health = _dept_health_svc.compute_all(session)

    _connectors_service.set_dept_health_hook(_recompute_dept_health)

    app.include_router(build_llm_providers_admin_router(db_session_factory=factory, mode=mode))
    app.include_router(build_llm_slot_defaults_router(db_session_factory=factory, mode=mode))
    app.include_router(build_jobs_router(db_session_factory=factory, mode=mode))
    app.include_router(build_notifications_router(db_session_factory=factory, mode=mode))
    app.include_router(build_notifications_stream_router(db_session_factory=factory, mode=mode))

    # Shared per-process presence registry; lifespan sets both keys.
    # This guard covers tests that call create_app() without entering
    # the lifespan (i.e. without TestClient or ASGILifespan).
    if getattr(app.state, "user_presence_registry", None) is None:
        _fallback_presence = UserPresenceRegistry()
        app.state.user_presence_registry = _fallback_presence
        app.state.user_presence = _fallback_presence
    app.include_router(build_reports_router(db_session_factory=factory, mode=mode))
    app.include_router(build_reports_stream_router(db_session_factory=factory, mode=mode))
    app.include_router(build_reports_revise_router(db_session_factory=factory, mode=mode))
    from openlia_server.routes.department_model_pref import (
        build_department_model_pref_router,
    )

    app.include_router(build_department_model_pref_router(db_session_factory=factory, mode=mode))

    # Skills system — store + registry constructed here, shared via app.state.
    from openlia.skills import FilesystemSkillStore, LayeredSkillStore, SkillRegistry

    from openlia_server.routes.admin_skills import build_admin_skills_router
    from openlia_server.routes.skills import build_skills_router

    _skills_root = Path(
        os.environ.get("OPENLIA_SKILLS_ROOT", str(Path.home() / ".openlia" / "skills"))
    )
    _skills_root.mkdir(parents=True, exist_ok=True)
    _fs_skill_store = FilesystemSkillStore(root=_skills_root)
    # Plan 1: filesystem store for both scopes. DatabaseSkillStore reserved for
    # company-mode user-scope in Plan 2 once real multi-user wiring is in place.
    skills_layered = LayeredSkillStore(system=_fs_skill_store, user=_fs_skill_store)
    skills_registry = SkillRegistry(store=skills_layered)
    app.state.skills_layered = skills_layered
    app.state.skills_registry = skills_registry
    app.include_router(
        build_skills_router(
            db_session_factory=factory,
            store=skills_layered,
            registry=skills_registry,
            mode=mode,
        )
    )
    app.include_router(
        build_admin_skills_router(
            db_session_factory=factory,
            store=skills_layered,
            registry=skills_registry,
            mode=mode,
        )
    )

    app.include_router(build_secretary_router(db_session_factory=factory, mode=mode))
    app.include_router(build_equity_research_v3_router(db_session_factory=factory, mode=mode))
    app.include_router(build_earnings_update_router(db_session_factory=factory, mode=mode))
    # EU v2 streaming infrastructure — lifespan sets the real broker.
    # This guard covers tests that call create_app() without entering
    # the lifespan (i.e. without TestClient or ASGILifespan).
    if getattr(app.state, "eu_v2_event_broker", None) is None:
        from openlia.llm.runtime.report_v3 import EventBroker as _EventBroker

        app.state.eu_v2_event_broker = _EventBroker()
        app.state.eu_v2_cancel_registry = {}
    app.include_router(build_earnings_update_v2_router(db_session_factory=factory, mode=mode))
    # MB v2 streaming infrastructure — lifespan sets the real broker. This
    # guard covers tests that call create_app() without entering the lifespan.
    if getattr(app.state, "mb_v2_event_broker", None) is None:
        from openlia.llm.runtime.report_mb import EventBroker as _MbEventBroker

        app.state.mb_v2_cancel_registry = {}
        app.state.mb_v2_event_broker = _MbEventBroker()
    app.include_router(build_morning_briefing_router(db_session_factory=factory, mode=mode))
    app.include_router(build_panic_thermometer_router(db_session_factory=factory, mode=mode))

    # Portfolio — bind the connector dispatcher behind a fetch(need_id, params)
    # surface so the price provider can pull live quotes. Skipping this leaves
    # the page in graceful-degradation mode (prices render as `—`).
    from openlia_server.services.connector_financial_adapter import (
        ConnectorFinancialAdapter,
    )

    if getattr(app.state, "financial_adapter", None) is None:
        app.state.financial_adapter = ConnectorFinancialAdapter(factory)

    def _portfolio_price_provider_factory() -> Any:
        from openlia_server.services.portfolio_prices import (
            AdapterPriceProvider,
            _NoopPriceProvider,
        )

        adapter = getattr(app.state, "financial_adapter", None)
        if adapter is None:
            log.warning("portfolio: no financial_adapter on app.state; using no-op price provider")
            return _NoopPriceProvider()
        return AdapterPriceProvider(adapter)

    app.include_router(
        build_portfolio_router(
            db_session_factory=factory,
            mode=mode,
            price_provider_factory=_portfolio_price_provider_factory,
        )
    )

    # Macro Research — singleton for the per-user assessment schedule.
    from openlia_server.services.mr_schedules import MRScheduleService

    # Factory-time MR schedule service. The lifespan replaces this with
    # a scheduler-bound instance on app.state.mr_schedule_service before
    # the first request. The route layer reads from app.state for every
    # handler so there is no risk of binding the no-scheduler instance.
    mr_schedule_svc = MRScheduleService(session_factory=factory)
    app.state.mr_schedule_service = mr_schedule_svc

    # Wire the cross-department snapshot reader into the registered department
    # so MacroResearchDepartment.get_current_snapshot reads the new
    # MrDashboardCache table.
    from openlia.departments import get_department

    from openlia_server.services.mr_snapshot_reader import MrDashboardSnapshotReader

    mr_department = get_department("macro_research")
    if mr_department is not None:
        mr_department.set_snapshot_reader(MrDashboardSnapshotReader(session_factory=factory))

    app.include_router(
        build_macro_research_router(
            db_session_factory=factory,
            mode=mode,
        )
    )
    app.include_router(
        build_mr_schedule_router(
            db_session_factory=factory,
            mode=mode,
            mr_schedule_service=mr_schedule_svc,
        )
    )

    app.include_router(build_retail_sentiment_router(db_session_factory=factory, mode=mode))
    # PT runner singleton (per-process) so the per-panel cache persists across
    # requests within a process. The dispatcher fetches real EODHD data,
    # resolving the key lazily (env, then an installed connector) on each
    # request; an embedding process may pre-install its own dispatcher on
    # `app.state.pt_dispatcher` before the first request.
    pt_dispatcher = getattr(app.state, "pt_dispatcher", None) or build_pt_dispatcher(factory)
    app.state.pt_dispatcher = pt_dispatcher
    app.state.pt_runner = PtRunner(session_factory=factory, dispatcher=pt_dispatcher)
    # Seed shipped presets once at app-factory time.
    try:
        PtConfigService(session_factory=factory).seed_shipped_presets()
    except Exception:
        # Tables may not yet exist in some embed/test setups; lifespan
        # create_all happens later, so skip silently and rely on a later
        # seed call at first dashboard request.
        pass
    app.state.chat_runner_factory = lambda: build_chat_runner(
        db_session_factory=factory,
        skill_registry=getattr(app.state, "skills_registry", None),
    )
    # Report runner is consumed by per-department routes (morning_briefing, earnings_update).
    # `build_report_runner` returns a RefreshingReportRunner that opens a fresh DB session
    # per run, so we can share a single instance across requests.
    app.state.report_runner = build_report_runner(
        db_session_factory=factory,
        skill_registry=getattr(app.state, "skills_registry", None),
    )
    # Earnings data adapter — optional; when unset the EU on-demand route uses a no-op.
    app.state.earnings_adapter = getattr(
        app.state, "earnings_adapter", _NoopEarningsRecentAdapter()
    )
    from openlia_server.routes.capabilities import router as capabilities_router

    app.include_router(capabilities_router)

    app.include_router(build_disclaimer_router(db_session_factory=factory, mode=mode))
    app.include_router(build_guardrail_events_router(db_session_factory=factory, mode=mode))
    app.include_router(build_chat_stream_router(db_session_factory=factory, mode=mode))

    from openlia_server.routes.chat_sessions import build_chat_sessions_router

    app.include_router(build_chat_sessions_router(db_session_factory=factory, mode=mode))

    from openlia_server.routes.graph import build_graph_router

    app.include_router(build_graph_router(db_session_factory=factory, mode=mode))

    from openlia_server.routes.admin_graph import build_admin_graph_router

    app.include_router(build_admin_graph_router(db_session_factory=factory, mode=mode))

    from openlia_server.routes.dev import build_dev_router

    app.include_router(build_dev_router())

    from openlia_server.routes.repo import build_repo_router

    app.include_router(build_repo_router(db_session_factory=factory, mode=mode))

    from openlia_server.routes.report_templates import build_report_templates_router

    app.include_router(build_report_templates_router(db_session_factory=factory, mode=mode))

    from openlia_server.routes.files import build_files_router

    app.include_router(build_files_router(db_session_factory=factory, mode=mode))

    from openlia_server.routes.settings_general import build_settings_general_router

    app.include_router(build_settings_general_router(db_session_factory=factory, mode=mode))

    from openlia_server.routes.settings_email import build_settings_email_router

    app.include_router(build_settings_email_router(db_session_factory=factory, mode=mode))

    from openlia_server.routes.cache import build_cache_router

    app.include_router(build_cache_router(db_session_factory=factory, mode=mode))

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "mode": mode}

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/_debug/client_host", include_in_schema=False)
    def _debug_client_host(request: Request) -> dict[str, str | None]:
        host = request.client.host if request.client else None
        return {"host": host, "scheme": request.url.scheme}

    _mount_frontend(app)

    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve `frontend/dist` with SPA fallback when OPENLIA_FRONTEND_DIST is set.

    Opt-in via env var so dev servers don't accidentally serve a stale build
    alongside the API. The Docker image sets OPENLIA_FRONTEND_DIST=/app/frontend/dist.
    """
    dist_env = os.environ.get("OPENLIA_FRONTEND_DIST")
    if not dist_env:
        return

    dist_dir = os.path.abspath(dist_env)
    index_html = os.path.join(dist_dir, "index.html")
    if not os.path.isdir(dist_dir) or not os.path.isfile(index_html):
        return

    assets_dir = os.path.join(dist_dir, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.api_route(
        "/{full_path:path}",
        include_in_schema=False,
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    )
    def spa_fallback(full_path: str, request: Request) -> FileResponse:
        # Requests that originally had /api/... should 404 as JSON, not
        # serve the SPA shell. Same for any non-GET (SPA shell is only
        # ever rendered for GET — POST/PUT/PATCH/DELETE on unmatched
        # paths means a missing API endpoint, not a navigation).
        if request.scope.get("openlia_was_api") or request.method != "GET":
            raise HTTPException(status_code=404)
        candidate_file = os.path.normpath(os.path.join(dist_dir, full_path))
        if (
            full_path
            and candidate_file.startswith(dist_dir + os.sep)
            and os.path.isfile(candidate_file)
        ):
            return FileResponse(candidate_file)
        return FileResponse(index_html)
