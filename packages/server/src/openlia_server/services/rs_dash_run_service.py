"""Retail Sentiment dashboard run service.

Runs the ``openlia.llm.runtime.report_dash_rs`` engine for one ticker and
inserts a new row into ``rs_dashboard_cache`` on each run. Sibling of
``mr_dash_run_service``: no report rows, sections, or charts — one engine run
produces one typed dashboard payload. Rows accumulate; the route reads the
latest by ``generated_at DESC``; old rows are pruned by maintenance.

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
from openlia_server.services.dash_citations import citation_rows
from openlia_server.services.llm_providers import (
    get_capability_override,
    resolve_provider_api_key,
)
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

    The web-search gate resolves the SAME capability override the session
    later applies via ``LLMSession.create`` — a user who enables
    ``web_search_native`` in Settings -> Models must have the gate and the
    session agree, or the run gets a session with web search but a gate that
    computed no native tools.
    """
    override = get_capability_override(db, provider_kind=provider_kind, model=model)
    caps = capabilities_for(provider_kind=provider_kind, model=model, override=override)
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


def _dedupe_evidence(evidence: list) -> list:
    """Drop evidence items that repeat an earlier item's story.

    Key is normalized title + published date — the observed duplicate pair
    shared both but differed in the ``source`` string (syndicated copy), so
    URL equality is not a sufficient key. First occurrence wins.
    """
    seen: set[tuple[str, str]] = set()
    out: list = []
    for item in evidence:
        if not isinstance(item, dict):
            out.append(item)
            continue
        title = " ".join(str(item.get("title") or "").lower().split())
        published = str(item.get("published_at") or "")[:10]
        key = (title, published)
        if title and key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


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


def _insert_cache(
    db: DBSession,
    *,
    user_id: str,
    ticker: str,
    payload: dict,
    model_ref: str,
) -> None:
    """Insert a new ``rs_dashboard_cache`` row for each run.

    Each run appends a fresh row; the route reads the latest by
    ``generated_at DESC LIMIT 1``. Old rows are pruned by the maintenance
    executor after ``RS_DASHBOARD_CACHE_RETENTION_DAYS`` days.
    """
    payload_json = json.dumps(payload)
    provenance = payload.get("provenance", "live")
    generated_at = datetime.now(UTC)

    row = RsDashboardCache(
        user_id=user_id,
        ticker=ticker,
        payload_json=payload_json,
        provenance=provenance,
        model_ref=model_ref,
        generated_at=generated_at,
    )
    db.add(row)
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
    """Run the RS dashboard engine inline and insert a new cache row.

    Awaits the engine to completion using the caller's DB session, then
    inserts a fresh ``rs_dashboard_cache`` row for ``(user_id, ticker)``.
    Each run appends; the route reads the latest by ``generated_at DESC``.
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
            capability_override=get_capability_override(
                db, provider_kind=request.provider_kind, model=request.model
            ),
            api_key=resolve_provider_api_key(
                db, provider_kind=request.provider_kind, model=request.model
            ),
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

    # The evidence list is LLM-authored; the same story sometimes arrives
    # twice under different source strings (syndication). Dedupe on
    # normalized title + date before persisting.
    evidence = payload.get("evidence")
    if isinstance(evidence, list):
        payload["evidence"] = _dedupe_evidence(evidence)

    # Stamp captured_at if not already set by the engine.
    if not payload.get("captured_at"):
        payload["captured_at"] = datetime.now(UTC).isoformat()

    # Attach the run's citation ledger so the UI can render the narrative's
    # [^source_id] markers as links instead of stripping them.
    payload["citations"] = citation_rows(result.citations)

    _insert_cache(
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
