"""Retail Sentiment dashboard run service.

Runs the ``openlia.llm.runtime.report_dash_rs`` engine for one ticker and
upserts its typed payload into ``rs_dashboard_cache``. Sibling of
``mr_dash_run_service``: no report rows, sections, or charts — one engine run
produces one typed dashboard payload, persisted as a single cache row keyed on
``(user_id, ticker)``.

After the engine run, the service reads prior sentiment-score history for
``(user_id, ticker)`` and merges deterministic momentum/trend fields into the
payload via ``momentum_from_history`` from the quant module.

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
from openlia.llm.runtime.report_dash_rs import (
    CancelToken,
    EnabledConnectors,
    LLMSession,
    MbDataTransports,
    NullEmitter,
    Runner,
    RunRequest,
)
from openlia.llm.runtime.report_dash_rs.quant import momentum_from_history
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.dashboard import RsDashboardCache
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
    provider id, plus ``eodhd`` when a key is resolvable.
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


def _null_transports() -> MbDataTransports:
    """Silent null transport bundle for when EODHD is not configured."""
    return MbDataTransports(
        quotes=lambda _tickers: [],
        prices=lambda _ticker, _rng: [],
        news=lambda **_kwargs: [],
        economic_calendar=lambda _window: [],
        macro_indicators=lambda _keys: {},
    )


def _prior_scores(db: DBSession, *, user_id: str, ticker: str) -> list[float]:
    """Read prior sentiment-score history for ``(user_id, ticker)``, oldest-first.

    Returns the ``sentiment_score`` float from each cached row ordered by
    ``generated_at`` ascending. Returns an empty list when no prior rows exist.
    """
    rows = (
        db.query(RsDashboardCache)
        .filter_by(user_id=user_id, ticker=ticker)
        .order_by(RsDashboardCache.generated_at.asc())
        .all()
    )
    scores: list[float] = []
    for row in rows:
        try:
            payload = json.loads(row.payload_json)
            score = payload.get("sentiment_score")
            if score is not None:
                scores.append(float(score))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return scores


def _upsert_cache(
    db: DBSession,
    *,
    user_id: str,
    ticker: str,
    payload: dict,
    model_ref: str,
) -> None:
    """Insert-or-update the ``(user_id, ticker)`` cache row.

    The unique constraint on ``(user_id, ticker)`` guarantees one row
    per ticker per user, so we update in place when a row exists rather
    than accumulating duplicates.
    """
    payload_json = json.dumps(payload)
    provenance = payload.get("provenance", "live")
    generated_at = datetime.now(UTC)

    row = db.query(RsDashboardCache).filter_by(user_id=user_id, ticker=ticker).one_or_none()
    if row is None:
        row = RsDashboardCache(
            user_id=user_id,
            ticker=ticker,
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


async def run_to_cache(
    db: DBSession,
    *,
    user_id: str,
    ticker: str,
    provider_kind: str = "anthropic",
    model: str = "claude-sonnet-4-6",
    transports: MbDataTransports | None = None,
    session: LLMSession | None = None,
    cancel_token: CancelToken | None = None,
) -> str:
    """Run the RS dashboard engine inline and upsert the payload into cache.

    Awaits the engine to completion using the caller's DB session, then
    upserts one ``rs_dashboard_cache`` row keyed on ``(user_id, ticker)``.
    Merges deterministic momentum/trend fields from prior score history.
    Fails loud on a non-completed run or a missing payload — no partial /
    empty cache row is written. Returns the ticker.
    """
    enabled_connectors = _resolve_enabled_connectors(db, provider_kind=provider_kind, model=model)

    request = RunRequest(
        dashboard_slug="retail_sentiment",
        subject=ticker,
        provider_kind=provider_kind,
        model=model,
        enabled_connectors=enabled_connectors,
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
            f"RS dashboard run for {ticker} did not complete: "
            f"status={result.status} message={result.message}"
        )

    payload = dict(result.payload)

    # Merge deterministic momentum from cached score history.
    prior = _prior_scores(db, user_id=user_id, ticker=ticker)
    score = payload.get("sentiment_score")
    if score is not None:
        momentum, trend_label = momentum_from_history([*prior, float(score)])
        payload["momentum"] = momentum
        payload["trend_label"] = trend_label

    # Stamp captured_at if not already set by the engine.
    if not payload.get("captured_at"):
        payload["captured_at"] = datetime.now(UTC).isoformat()

    _upsert_cache(
        db,
        user_id=user_id,
        ticker=ticker,
        payload=payload,
        model_ref=request.model,
    )
    return ticker


__all__ = [
    "run_to_cache",
]
