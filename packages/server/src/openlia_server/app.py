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
from openlia_server.routes.departments.equity_research import (
    build_equity_research_router,
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
from openlia_server.routes.jobs import build_jobs_router
from openlia_server.routes.mr_schedules import build_mr_schedule_router
from openlia_server.routes.notifications import build_notifications_router
from openlia_server.routes.portfolio import build_portfolio_router
from openlia_server.routes.reports import build_reports_router
from openlia_server.routes.settings import (
    build_llm_providers_admin_router,
)
from openlia_server.routes.setup import build_setup_router
from openlia_server.scheduler.service import SchedulerService
from openlia_server.scheduler.settings import SchedulerSettings
from openlia_server.scheduler.wiring import build_scheduler_service
from openlia_server.services.eu_scan_planner import EuScanPlannerImpl
from openlia_server.services.pt_config import PtConfigService
from openlia_server.services.pt_runner import PtRunner
from openlia_server.services.report_export import BrowserLauncher
from openlia_server.services.runtime import (
    build_batch_runner,
    build_chat_runner,
    build_report_runner,
)

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
    "morning_briefing": [
        "report.system",
        "report.morning_briefing.user",
    ],
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


class _NoopPtDispatcher:
    """Fallback PT data dispatcher used when no real adapter is wired."""

    def fetch(self, *, requirement, panel_id, params):  # type: ignore[no-untyped-def]
        return None


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

        # Validate prompt slots once at boot. PromptSlotNotFound propagates
        # and prevents the server from starting if any slot is missing.
        prompt_root = getattr(app.state, "prompt_root", None)
        prompt_loader = PromptLoader(root=prompt_root) if prompt_root else PromptLoader()
        for department_id, slots in _DEPARTMENT_SLOTS.items():
            prompt_loader.validate_department_slots(department_id, expected=slots)

        browser_launcher = BrowserLauncher()
        app.state.browser_launcher = browser_launcher

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
            from openlia_server.services.mb_request_builder import (
                MbRequestBuilderImpl,
            )

            mb_builder = MbRequestBuilderImpl()
            from openlia_server.services.mr_assessment import MRAssessmentBuilderImpl
            from openlia_server.services.mr_cache import MRCacheStoreImpl
            from openlia_server.services.mr_schedules import MRScheduleService
            from openlia_server.services.reports import ReportStoreImpl

            mr_data_provider = getattr(app.state, "mr_data_provider", None)
            mr_builder = MRAssessmentBuilderImpl(data_provider=mr_data_provider)
            mr_cache_store_lifespan = MRCacheStoreImpl()
            report_store_impl = ReportStoreImpl()

            async with adapter:
                scheduler_svc = build_scheduler_service(
                    session_factory=_sm,
                    settings=scheduler_settings,
                    scheduler=adapter,
                    report_runner=build_report_runner(_sm),
                    batch_runner=build_batch_runner(_sm),
                    eu_planner=eu_planner,
                    mb_builder=mb_builder,
                    mr_builder=mr_builder,
                    report_store=report_store_impl,
                    mr_cache_store=mr_cache_store_lifespan,
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

                app.state.scheduler = scheduler_svc
                app.state.mr_schedule_service = mr_schedule_svc_lifespan

                try:
                    yield
                finally:
                    await scheduler_svc.shutdown()
                    await browser_launcher.shutdown()
                    await _cancel_wizard_background_tasks(app)

            return

        app.state.scheduler = scheduler_svc
        try:
            yield
        finally:
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

    # Wire connector + runner-spec mutation hooks so the health cache stays
    # in sync without route handlers needing to know about it.
    from openlia_server.services import (
        connectors_service as _connectors_service,
    )
    from openlia_server.services import (
        dept_health as _dept_health_svc,
    )
    from openlia_server.services import (
        runner_specs_service as _runner_specs_service,
    )

    def _recompute_dept_health(session: DBSession) -> None:
        app.state.dept_health = _dept_health_svc.compute_all(session)

    _connectors_service.set_dept_health_hook(_recompute_dept_health)
    _runner_specs_service.set_dept_health_hook(_recompute_dept_health)

    # Hydrate the wizard-time adapter's per-department needs/categories
    # registry from the live `openlia.departments` module. Without this,
    # `propose_specs` iterates empty maps and every runner-bearing dept
    # stays permanently disabled with every need unresolved.
    _runner_specs_service.hydrate_dept_registries()

    # Mount the wizard-time runner specs router. Production wiring of a
    # real Quick-tier LLM client lives in the wizard adapter integration
    # work (Phase 9 follow-up); the placeholder below raises loudly when
    # the resolver runs without a configured provider so misconfiguration
    # surfaces as a proposal-level error instead of silently dropping
    # drafts.
    from openlia_server.routes.runner_specs import (
        build_dept_proposed_specs_router,
        build_runner_specs_list_router,
        build_runner_specs_router,
    )
    from openlia_server.services.adapter_llm_client import (
        make_adapter_llm_client_factory,
        make_agentic_resolver_factory,
    )

    _adapter_factory = make_adapter_llm_client_factory(factory)
    _agentic_factory = make_agentic_resolver_factory(factory)
    app.include_router(
        build_runner_specs_router(
            db_session_factory=factory,
            llm_client_factory=_adapter_factory,
        )
    )
    app.include_router(
        build_dept_proposed_specs_router(
            db_session_factory=factory,
            agentic_factory=_agentic_factory,
        )
    )

    def _transport_for_connector(conn: Any) -> Any:
        from openlia_server.services.dispatcher_factory import _prepare_connector

        return _prepare_connector(conn).transport

    app.include_router(
        build_runner_specs_list_router(
            db_session_factory=factory,
            llm_client_factory=_adapter_factory,
            transport_factory=_transport_for_connector,
        )
    )
    app.include_router(build_llm_providers_admin_router(db_session_factory=factory, mode=mode))
    app.include_router(build_jobs_router(db_session_factory=factory, mode=mode))
    app.include_router(build_notifications_router(db_session_factory=factory, mode=mode))
    app.include_router(build_reports_router(db_session_factory=factory, mode=mode))
    app.include_router(build_secretary_router(db_session_factory=factory, mode=mode))
    app.include_router(build_equity_research_router(db_session_factory=factory, mode=mode))
    app.include_router(build_earnings_update_router(db_session_factory=factory, mode=mode))
    app.include_router(build_morning_briefing_router(db_session_factory=factory, mode=mode))
    app.include_router(build_panic_thermometer_router(db_session_factory=factory, mode=mode))

    # Portfolio — production price provider wraps app.state.financial_adapter
    # (a configured Plan 3 ProviderAdapter exposing stock_quote). When no
    # adapter is registered we fall back to a no-op provider so the page
    # degrades gracefully (sparkline/price render as `—`) instead of 5xx-ing.
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

    # Macro Research — singletons for dashboard CRUD, cache, runner, schedule.
    from openlia_server.services.mr_cache import MRCacheStoreImpl
    from openlia_server.services.mr_dashboard import MRDashboardService
    from openlia_server.services.mr_runner import MRRunner
    from openlia_server.services.mr_schedules import MRScheduleService

    mr_dashboard_svc = MRDashboardService(session_factory=factory)
    mr_cache_store = MRCacheStoreImpl()
    mr_data_provider = getattr(app.state, "mr_data_provider", None) or _NoopPtDispatcher()

    class _MRDataFetchAdapter:
        """Wrap a PT-style dispatcher to expose the simpler fetch(requirement=...)
        signature the MR assembler expects.

        NEW-19-10: only the signature-mismatch fallback is swallowed; real
        fetch failures escape so a misconfigured provider surfaces in the
        route response instead of silently masking dashboards as zeroed.
        Production wiring should install a registry-backed adapter onto
        `app.state.mr_data_provider` before the first request; the noop
        dispatcher remains as a default for tests and dev with no provider.
        """

        def __init__(self, inner: Any) -> None:
            self._inner = inner

        def fetch(self, *, requirement: str, **kwargs: Any) -> Any:
            try:
                return self._inner.fetch(requirement=requirement, panel_id="mr", params={})
            except TypeError:
                # Inner already matches MR signature — call it directly.
                return self._inner.fetch(requirement=requirement)

    mr_runner = MRRunner(
        data_provider=_MRDataFetchAdapter(mr_data_provider),
        cache_store=mr_cache_store,
        dashboard_service=mr_dashboard_svc,
        session_factory=factory,
    )
    # Factory-time MR schedule service. The lifespan replaces this with
    # a scheduler-bound instance on app.state.mr_schedule_service before
    # the first request. The route layer reads from app.state for every
    # handler so there is no risk of binding the no-scheduler instance.
    mr_schedule_svc = MRScheduleService(session_factory=factory)
    app.state.mr_runner = mr_runner
    app.state.mr_dashboard_service = mr_dashboard_svc
    app.state.mr_cache_store = mr_cache_store
    app.state.mr_schedule_service = mr_schedule_svc

    app.include_router(
        build_macro_research_router(
            db_session_factory=factory,
            mode=mode,
            mr_runner=mr_runner,
            dashboard_service=mr_dashboard_svc,
        )
    )
    app.include_router(
        build_mr_schedule_router(
            db_session_factory=factory,
            mode=mode,
            mr_schedule_service=mr_schedule_svc,
        )
    )

    # Retail Sentiment — runner singleton (per-process). Data provider optional;
    # when absent the runner produces empty-posts snapshots (useful for tests).
    # Classifier resolves the configured LLM model per call and falls back to
    # neutral when none is configured, so the runner is safe to install in
    # environments where no provider is set up yet.
    from openlia_server.services.rs_runner import RsRunner as _RsRunner
    from openlia_server.services.rs_sync_classifier import RefreshingSyncLlmClassifier

    rs_data_provider = getattr(app.state, "rs_data_provider", None)
    rs_classifier = getattr(app.state, "rs_classifier", None) or RefreshingSyncLlmClassifier(
        db_session_factory=factory,
    )
    app.state.rs_classifier = rs_classifier
    app.state.rs_runner = _RsRunner(
        session_factory=factory,
        data_provider=rs_data_provider,
        classifier=rs_classifier,
    )
    app.include_router(build_retail_sentiment_router(db_session_factory=factory, mode=mode))
    # PT runner singleton (per-process) so the per-panel cache persists across
    # requests within a process. Dispatcher defaults to a no-op; a real
    # Plan 3 dispatcher can be installed on `app.state.pt_dispatcher` from an
    # embedding process before the first request.
    pt_dispatcher = getattr(app.state, "pt_dispatcher", None) or _NoopPtDispatcher()
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
    app.include_router(build_disclaimer_router(db_session_factory=factory, mode=mode))
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

    from openlia_server.routes.settings_llm_user import build_llm_user_router

    app.include_router(build_llm_user_router(db_session_factory=factory, mode=mode))

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
    """Serve `frontend/dist` with SPA fallback when configured.

    Resolution order:
      1. OPENLIA_FRONTEND_DIST env var (wins if set; missing dir -> skip).
      2. /app/frontend/dist (Docker image default).
      3. <repo>/frontend/dist (local npm build).

    Skips silently when no candidate resolves to a directory containing
    index.html, so dev servers and tests don't need a built bundle.
    """
    candidates: list[str] = []
    dist_env = os.environ.get("OPENLIA_FRONTEND_DIST")
    if dist_env:
        candidates.append(dist_env)
    else:
        candidates.append("/app/frontend/dist")
        here = os.path.dirname(os.path.abspath(__file__))
        # Walk: openlia_server → src → server → packages → repo root.
        repo_dist = os.path.normpath(os.path.join(here, "..", "..", "..", "..", "frontend", "dist"))
        candidates.append(repo_dist)

    resolved: tuple[str, str] | None = None
    for candidate in candidates:
        dist_dir = os.path.abspath(candidate)
        if not os.path.isdir(dist_dir):
            continue
        index_html = os.path.join(dist_dir, "index.html")
        if not os.path.isfile(index_html):
            continue
        resolved = (dist_dir, index_html)
        break

    if resolved is None:
        return

    dist_dir, index_html = resolved
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
