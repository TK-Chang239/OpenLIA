"""Macro Research dashboard run service.

Runs the ``openlia.llm.runtime.report_dash_mr`` engine for one dashboard
and upserts its typed payload into ``mr_dashboard_cache``. A much slimmer
sibling of ``mb_v2_run_service``: there are no report rows, sections, or
charts — one engine run produces one typed dashboard payload, persisted
as a single cache row keyed on ``(user_id, dashboard)``.

The connector gating defaults to "use everything available": web search
is on (when the model supports native web search) since macro dashboards
lean on it as their backbone, plus every validated connector provider and
EODHD when a key is resolvable.

Connector dispatch reuses ``mb_v2_run_service.build_mb_dispatcher`` — it is
department-agnostic blocklist wiring, so there is nothing to fork. Data
transports reuse ``build_mb_transports`` / ``resolve_eodhd_api_key`` from
``mb_v2_wiring``.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from openlia.connectors.types import ConnectorStatus
from openlia.llm.capabilities import capabilities_for
from openlia.llm.runtime.report_dash_mr import (
    CancelToken,
    EnabledConnectors,
    LLMSession,
    MbDataTransports,
    NullEmitter,
    Runner,
    RunRequest,
)
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.dashboard import MrDashboardCache
from openlia_server.services import connectors_service
from openlia_server.services.mb_v2_run_service import build_mb_dispatcher
from openlia_server.services.mb_v2_wiring import (
    build_mb_transports,
    resolve_eodhd_api_key,
)

log = logging.getLogger(__name__)


def _resolve_enabled_connectors(
    db: DBSession,
    *,
    provider_kind: str,
    model: str,
) -> EnabledConnectors:
    """Build the gated connector set for a dashboard run.

    Defaults to "use everything available": ``web_search`` ON (gated by
    the model's native web-search capability), every VALIDATED connector
    provider id, plus ``eodhd`` when a key is resolvable. Macro dashboards
    lean on web search as the backbone, so it is on by default rather than
    opt-in like the Morning Briefing schedule path.
    """
    caps = capabilities_for(provider_kind=provider_kind, model=model)
    providers = {
        row.provider_id
        for row in connectors_service.list_connectors(db)
        if row.status == ConnectorStatus.VALIDATED.value
    }
    if resolve_eodhd_api_key(db) is not None:
        providers.add("eodhd")
    return EnabledConnectors(
        provider_ids=frozenset(providers),
        web_search=caps.web_search_native,
    )


def build_run_request(
    db: DBSession,
    *,
    dashboard_slug: str,
    provider_kind: str,
    model: str,
) -> RunRequest:
    """Build a ``report_dash_mr.RunRequest`` for one dashboard.

    The dashboard engine is driven by ``dashboard_slug`` (which output
    schema to emit), not a section template, so ``template`` stays None.
    """
    return RunRequest(
        dashboard_slug=dashboard_slug,
        subject=f"{dashboard_slug} dashboard",
        template=None,
        provider_kind=provider_kind,
        model=model,
        enabled_connectors=_resolve_enabled_connectors(
            db, provider_kind=provider_kind, model=model
        ),
    )


def _null_transports() -> MbDataTransports:
    """A silent null transport bundle for when EODHD is not configured.

    Every data callable returns an empty result rather than raising — the
    dashboard engine leans on web search, so a missing EODHD key should
    not surface a hard error on a tool the model may never call. Used when
    ``build_mb_transports`` returns None (no key) and no override was
    supplied.
    """
    return MbDataTransports(
        quotes=lambda _tickers: [],
        prices=lambda _ticker, _rng: [],
        news=lambda **_kwargs: [],
        economic_calendar=lambda _window: [],
        macro_indicators=lambda _keys: {},
    )


async def run_to_cache(
    db: DBSession,
    *,
    user_id: str,
    dashboard_slug: str,
    provider_kind: str = "anthropic",
    model: str = "claude-sonnet-4-6",
    transports: MbDataTransports | None = None,
    session: LLMSession | None = None,
    cancel_token: CancelToken | None = None,
) -> str:
    """Run the dashboard engine inline and upsert the payload into cache.

    Awaits the engine to completion using the caller's DB session, then
    upserts one ``mr_dashboard_cache`` row keyed on ``(user_id, dashboard)``.
    Fails loud on a non-completed run or a missing payload — no partial /
    empty cache row is written. Returns the dashboard slug.
    """
    request = build_run_request(
        db,
        dashboard_slug=dashboard_slug,
        provider_kind=provider_kind,
        model=model,
    )

    resolved_transports = transports or (
        build_mb_transports(api_key=resolve_eodhd_api_key(db)) or _null_transports()
    )
    dispatcher = build_mb_dispatcher(
        db, enabled_provider_ids=request.enabled_connectors.provider_ids
    )

    runner = Runner(
        request=request,
        transports=resolved_transports,
        dispatcher=dispatcher,
    )
    if session is None:
        session = LLMSession.create(
            provider_kind=request.provider_kind,
            model=request.model,
        )
    result = await runner.run(
        session=session,
        emitter=NullEmitter(),
        cancel_token=cancel_token or CancelToken(),
    )

    if result.status != "completed" or result.payload is None:
        raise RuntimeError(
            f"dashboard run for {dashboard_slug} did not complete: "
            f"status={result.status} message={result.message}"
        )

    _upsert_cache(
        db,
        user_id=user_id,
        dashboard_slug=dashboard_slug,
        payload=result.payload,
        model_ref=request.model,
    )
    return dashboard_slug


def _upsert_cache(
    db: DBSession,
    *,
    user_id: str,
    dashboard_slug: str,
    payload: dict,
    model_ref: str,
) -> None:
    """Insert-or-update the ``(user_id, dashboard)`` cache row.

    The unique constraint on ``(user_id, dashboard)`` guarantees one row
    per dashboard per user, so we update in place when a row exists rather
    than accumulating duplicates.
    """
    payload_json = json.dumps(payload)
    provenance = payload.get("provenance", "live")
    generated_at = datetime.now(UTC)

    row = (
        db.query(MrDashboardCache)
        .filter_by(user_id=user_id, dashboard=dashboard_slug)
        .one_or_none()
    )
    if row is None:
        row = MrDashboardCache(
            user_id=user_id,
            dashboard=dashboard_slug,
            payload_json=payload_json,
            provenance=provenance,
            model_ref=model_ref,
            generated_at=generated_at,
        )
        db.add(row)
    else:
        row.payload_json = payload_json
        row.provenance = provenance
        row.model_ref = model_ref
        row.generated_at = generated_at
    db.flush()


__all__ = [
    "build_run_request",
    "run_to_cache",
]
