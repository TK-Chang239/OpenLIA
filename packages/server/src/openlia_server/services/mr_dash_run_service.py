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
from openlia_server.services import connectors_service, portfolio
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

# Map common ETF tickers to the All-Weather asset classes risk_math expects.
# Unmapped tickers fall back to "equities" (the dominant retail default).
_TICKER_ASSET_CLASS: dict[str, str] = {
    "SPY": "equities",
    "VOO": "equities",
    "VTI": "equities",
    "QQQ": "equities",
    "IVV": "equities",
    "TLT": "long_bonds",
    "EDV": "long_bonds",
    "VGLT": "long_bonds",
    "IEF": "intermediate_bonds",
    "BND": "intermediate_bonds",
    "AGG": "intermediate_bonds",
    "IEI": "intermediate_bonds",
    "GLD": "gold",
    "IAU": "gold",
    "SGOL": "gold",
    "DBC": "commodities",
    "GSG": "commodities",
    "PDBC": "commodities",
    "COMT": "commodities",
}


def _portfolio_weights(db: DBSession, user_id: str) -> dict[str, float]:
    """Resolve the user's holdings into normalized asset-class weights.

    Each holding maps to an asset class via ``_TICKER_ASSET_CLASS`` (default
    ``equities``). A position's value is ``shares * cost_basis`` when both are
    present, else ``1.0`` (an equal-weight fallback so weight-less holdings
    still contribute). Returns weights summing to 1.0, or ``{}`` when the user
    has no holdings.
    """
    holdings = portfolio.list_holdings(db, user_id=user_id)
    if not holdings:
        return {}
    by_class: dict[str, float] = {}
    for h in holdings:
        asset = _TICKER_ASSET_CLASS.get(h.ticker.upper(), "equities")
        if h.shares is not None and h.cost_basis is not None:
            value = float(h.shares) * float(h.cost_basis)
        else:
            value = 1.0
        by_class[asset] = by_class.get(asset, 0.0) + value
    total = sum(by_class.values())
    if total <= 0:
        return {}
    return {asset: value / total for asset, value in by_class.items()}


# Map a cached dashboard's RAG tone to a 0-10 Five-Forces intensity score.
# Five Forces seeds F1 (debt/money) from the cached Debt Cycle and F3
# (geopolitical) from the cached World Order, reading each source's headline
# tone. Tones outside this map (e.g. "blue") fall back to the amber score.
_TONE_TO_FORCE_SCORE: dict[str, int] = {"red": 8, "amber": 5, "green": 3}
_FORCE_SCORE_DEFAULT = 5


def _cached_payload(db: DBSession, user_id: str, slug: str) -> dict | None:
    """Return a cached dashboard payload as a dict, or ``None`` when not yet
    generated for this user."""
    row = db.query(MrDashboardCache).filter_by(user_id=user_id, dashboard=slug).one_or_none()
    if row is None:
        return None
    return json.loads(row.payload_json)


def _cached_payload_with_age(
    db: DBSession, user_id: str, slug: str
) -> tuple[dict | None, datetime | None]:
    """Like :func:`_cached_payload`, but also return the row's generated_at
    so consumers can present the read's age instead of implying freshness."""
    row = db.query(MrDashboardCache).filter_by(user_id=user_id, dashboard=slug).one_or_none()
    if row is None:
        return None, None
    generated_at = row.generated_at
    if generated_at is not None and generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=UTC)
    return json.loads(row.payload_json), generated_at


def _seeded_force_line(
    *,
    force_id: str,
    name: str,
    payload: dict | None,
    tone_key: str,
    research_hint: str,
) -> str:
    """One seeded-or-fallback Five-Forces input line.

    When the source dashboard is cached, read its headline tone block
    (``tone_key`` -> e.g. "phaseBox"), map the tone to a 0-10 score, and cite
    its title. When the source is missing, honestly say so and tell the model
    to research the force itself.
    """
    if payload is None:
        return f"- {force_id}: {name} not yet generated; {research_hint}"
    block = payload.get(tone_key, {})
    tone = block.get("tone", "")
    title = block.get("title", "")
    score = _TONE_TO_FORCE_SCORE.get(tone, _FORCE_SCORE_DEFAULT)
    return f"- {force_id}: {score} (0-10), seeded from the cached {name} state ({title})."


def _five_forces_data_context(db: DBSession, user_id: str) -> str:
    """Seed F1 (debt/money) and F3 (geopolitical) from cached dashboards.

    F1 reads the cached Debt Cycle ``phaseBox`` tone/title; F3 reads the cached
    World Order ``verdict`` tone/title. The model researches F2/F4/F5 itself.
    """
    debt = _cached_payload(db, user_id, "debt_cycle")
    world = _cached_payload(db, user_id, "world_order")
    f1 = _seeded_force_line(
        force_id="F1 (debt/money)",
        name="Debt Cycle",
        payload=debt,
        tone_key="phaseBox",
        research_hint="research the debt/money force (F1) from official sources.",
    )
    f3 = _seeded_force_line(
        force_id="F3 (geopolitical)",
        name="World Order",
        payload=world,
        tone_key="verdict",
        research_hint="research the geopolitical force (F3) from official sources.",
    )
    return (
        "Two of the five forces are seeded for you from other dashboards' cached "
        "classifications; research and score the remaining three (F2 political, "
        "F4 technology, F5 nature) yourself on a 0-10 scale.\n"
        f"{f1}\n{f3}"
    )


def _summary_state_line(
    *,
    label: str,
    payload: dict | None,
    block_key: str,
    extra: str = "",
    generated_at: datetime | None = None,
) -> str:
    """One cached-framework headline-state line for the Summary context block.

    Reads the source dashboard's headline block (``block_key`` -> e.g.
    "phaseBox" or "verdict") for its title; honestly notes a framework that has
    not been generated yet so the model says so rather than inventing a read.
    Each line carries its as-of date so the model can (and is told to) flag
    reads that have gone stale instead of presenting them as current.
    ``extra`` appends a framework-specific signal (e.g. the Five Forces
    active-count) when present.
    """
    if payload is None:
        return f"- {label}: not yet generated."
    block = payload.get(block_key, {})
    title = block.get("title", "")
    suffix = f" {extra}" if extra else ""
    age = ""
    if generated_at is not None:
        age_days = (datetime.now(UTC) - generated_at).days
        age = f" (as of {generated_at.date().isoformat()}, {age_days}d old)"
    return f"- {label}: {title}.{suffix}{age}"


def _summary_data_context(db: DBSession, user_id: str) -> str:
    """Summarize the five cached framework states for the Summary synthesis.

    Reads each framework's cached headline state (Debt Cycle phaseBox, Four
    Seasons / World Order / All-Weather / Five Forces verdict), plus the World
    Order scorecard label and the Five Forces active-count, and formats them
    into one authoritative context block. Frameworks with no cache row are
    flagged as not yet generated.
    """
    debt, debt_at = _cached_payload_with_age(db, user_id, "debt_cycle")
    seasons, seasons_at = _cached_payload_with_age(db, user_id, "four_seasons")
    world, world_at = _cached_payload_with_age(db, user_id, "world_order")
    weather, weather_at = _cached_payload_with_age(db, user_id, "all_weather")
    forces, forces_at = _cached_payload_with_age(db, user_id, "five_forces")

    world_extra = ""
    if world is not None:
        world_extra = f"Scorecard: {world.get('scorecard', {}).get('label', '')}."
    forces_extra = ""
    if forces is not None:
        count = forces.get("loops", {}).get("active", {}).get("countText", "")
        if count:
            forces_extra = f"Active forces: {count}."

    lines = [
        _summary_state_line(
            label="T1 - Debt Cycle (phase)",
            payload=debt,
            block_key="phaseBox",
            generated_at=debt_at,
        ),
        _summary_state_line(
            label="T2 - Four Seasons (season)",
            payload=seasons,
            block_key="verdict",
            generated_at=seasons_at,
        ),
        _summary_state_line(
            label="T4 - World Order (stage)",
            payload=world,
            block_key="verdict",
            extra=world_extra,
            generated_at=world_at,
        ),
        _summary_state_line(
            label="T3 - All-Weather (coverage)",
            payload=weather,
            block_key="verdict",
            generated_at=weather_at,
        ),
        _summary_state_line(
            label="T5 - Five Forces (active-count)",
            payload=forces,
            block_key="verdict",
            extra=forces_extra,
            generated_at=forces_at,
        ),
    ]
    return (
        "The five framework dashboards' latest cached reads are below, each "
        "with its as-of date. Treat each as the authoritative read for that "
        "framework as of that date; synthesize, do not contradict. When a "
        "read is more than a few days old, say so explicitly wherever the "
        "synthesis leans on it. Emit one frameworkStatus card per framework "
        "reflecting its state.\n" + "\n".join(lines)
    )


def _build_data_context(db: DBSession, *, user_id: str, dashboard_slug: str) -> str | None:
    """Server-injected authoritative inputs for this run.

    For ``all_weather`` returns a formatted summary of the user's portfolio
    asset-class weights (or a proxy instruction when no holdings exist). For
    ``five_forces`` seeds F1/F3 from the cached Debt Cycle / World Order
    dashboards. For ``summary`` injects the five framework dashboards' cached
    headline states. Other dashboards have no server-side inputs yet, so this
    returns ``None``.
    """
    if dashboard_slug == "all_weather":
        weights = _portfolio_weights(db, user_id)
        if not weights:
            return (
                "No portfolio holdings on file; audit the Dalio reference allocation "
                "as a proxy and say so."
            )
        parts = ", ".join(f"{asset} {weight:.2f}" for asset, weight in sorted(weights.items()))
        return f"Portfolio weights: {parts}"
    if dashboard_slug == "five_forces":
        return _five_forces_data_context(db, user_id)
    if dashboard_slug == "summary":
        return _summary_data_context(db, user_id)
    return None


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


def build_run_request(
    db: DBSession,
    *,
    user_id: str,
    dashboard_slug: str,
    provider_kind: str,
    model: str,
) -> RunRequest:
    """Build a ``report_dash_mr.RunRequest`` for one dashboard.

    The dashboard engine is driven by ``dashboard_slug`` (which output
    schema to emit), not a section template, so ``template`` stays None.
    Server-side authoritative inputs (e.g. the user's portfolio weights for
    the All-Weather audit) are injected via ``data_context``.
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
        data_context=_build_data_context(db, user_id=user_id, dashboard_slug=dashboard_slug),
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
        user_id=user_id,
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
            f"dashboard run for {dashboard_slug} did not complete: "
            f"status={result.status} message={result.message}"
        )

    # Attach the run's citation ledger so the UI can render the prose's
    # [^source_id] markers as links instead of showing/stripping raw tokens.
    payload = dict(result.payload)
    payload["citations"] = citation_rows(result.citations)

    _upsert_cache(
        db,
        user_id=user_id,
        dashboard_slug=dashboard_slug,
        payload=payload,
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
