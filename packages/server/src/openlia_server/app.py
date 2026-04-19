"""FastAPI application factory."""

from __future__ import annotations

import os
from collections.abc import Callable

from fastapi import FastAPI
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.session import SessionLocal, get_engine
from openlia_server.routes.admin import build_admin_router
from openlia_server.routes.auth import build_auth_router
from openlia_server.routes.settings import (
    build_data_providers_router,
    build_llm_providers_admin_router,
)


def _default_session_factory() -> DBSession:
    get_engine()
    return SessionLocal()


def create_app(
    *,
    db_session_factory: Callable[[], DBSession] | None = None,
) -> FastAPI:
    factory = db_session_factory or _default_session_factory
    mode = os.environ.get("OPENLIA_MODE", "personal").lower()
    app = FastAPI(title="OpenLIA", version="0.1.0")

    if mode == "company":
        app.include_router(build_auth_router(db_session_factory=factory))
        app.include_router(build_admin_router(db_session_factory=factory))

    app.include_router(build_data_providers_router(db_session_factory=factory))
    app.include_router(build_llm_providers_admin_router(db_session_factory=factory, mode=mode))

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "mode": mode}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
