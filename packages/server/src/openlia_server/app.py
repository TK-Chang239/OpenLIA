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
from fastapi import FastAPI
from sqlalchemy.orm import Session as DBSession, sessionmaker

import openlia_server.db.models  # noqa: F401 — registers all models on Base.metadata
from openlia_server.db.base import Base
from openlia_server.db.session import SessionLocal, configure_engine, get_engine
from openlia_server.routes.admin import build_admin_router
from openlia_server.routes.auth import build_auth_router
from openlia_server.routes.settings import (
    build_data_providers_router,
    build_llm_providers_admin_router,
)
from openlia_server.scheduler.service import SchedulerService
from openlia_server.scheduler.settings import SchedulerSettings
from openlia_server.scheduler.wiring import build_scheduler_service

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

    async def __aenter__(self) -> "_SchedulerAdapter":
        await self._sched.__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self._sched.__aexit__(*args)

    def start_in_background(self) -> None:
        """Launch the APScheduler event loop in a background task."""
        self._bg_task = asyncio.ensure_future(
            self._sched.start_in_background()
        )

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


def _default_session_factory() -> DBSession:
    get_engine()
    return SessionLocal()


def _make_lifespan(
    db_session_factory: Callable[[], DBSession] | None,
) -> Callable[[FastAPI], AsyncGenerator[None, None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        db_url = os.environ.get("OPENLIA_DATABASE_URL")
        if db_url:
            engine = configure_engine(db_url)
            # For SQLite (dev/test), create tables automatically — production
            # uses Alembic migrations so create_all is a no-op there.
            if engine.url.drivername == "sqlite":
                Base.metadata.create_all(engine)

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
            async with adapter:
                scheduler_svc = build_scheduler_service(
                    session_factory=_sm,
                    settings=scheduler_settings,
                    scheduler=adapter,
                    report_runner=None,
                    batch_runner=None,
                )
                await scheduler_svc.start()

                app.state.scheduler = scheduler_svc

                yield

                await scheduler_svc.shutdown()

            return

        app.state.scheduler = scheduler_svc
        yield

    return lifespan


def create_app(
    *,
    db_session_factory: Callable[[], DBSession] | None = None,
) -> FastAPI:
    factory = db_session_factory or _default_session_factory
    mode = os.environ.get("OPENLIA_MODE", "personal").lower()
    app = FastAPI(
        title="OpenLIA",
        version="0.0.0",
        lifespan=_make_lifespan(db_session_factory),
    )

    if mode == "company":
        app.include_router(build_auth_router(db_session_factory=factory))
        app.include_router(build_admin_router(db_session_factory=factory))

    app.include_router(build_data_providers_router(db_session_factory=factory))
    app.include_router(build_llm_providers_admin_router(db_session_factory=factory, mode=mode))

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "mode": mode}

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
