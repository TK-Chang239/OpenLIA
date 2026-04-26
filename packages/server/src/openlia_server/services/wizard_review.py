"""Setup-wizard AI review orchestration.

Two-stage flow:

1. Deterministic short-circuit. For every configured provider whose `kind` is
   in the adapter catalog, the resolver maps the department's basic
   requirements directly against the adapter's declared capabilities. If
   every basic requirement resolves and no unknown providers are configured,
   we emit the `ReviewResult` immediately without calling the LLM. This is
   exact, fast, and free.

2. LLM fallback. Only when the deterministic stage cannot resolve every
   department (an unknown-kind provider is configured, or a known provider's
   capabilities are missing in subtle ways) do we hand the enriched payload —
   including each provider's `declared_capabilities` and `unknown` flag — to
   the LLM. The prompt instructs it to ground confident mappings in the
   declared capabilities and cap unknown-provider confidence at 0.5.

The background task opens its own DB session via the factory passed in —
never captures a request-scoped session that FastAPI will close before the
task finishes.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from openlia.data.catalog import ProviderCatalog, build_catalog
from sqlalchemy.orm import Session

from openlia_server.ai_review import store as review_store_mod
from openlia_server.ai_review.runner import run_review as _run_review_impl
from openlia_server.ai_review.schema import (
    DepartmentReadiness,
    ReadinessState,
    RequirementMapping,
    ReviewResult,
)


class _ReviewLLMWrapper:
    """Bridges the runner's (prompt, max_tokens) protocol with the real adapter."""

    def __init__(self, adapter: Any) -> None:
        self._adapter = adapter

    async def generate(self, *, prompt: str, max_tokens: int) -> Any:
        from openlia.llm.types import LLMRequest, Message

        req = LLMRequest(messages=[Message(role="user", content=prompt)], max_tokens=max_tokens)
        return await self._adapter.generate(req)


def _build_provider_payload(
    rows: list[Any],
    catalog: ProviderCatalog,
) -> list[dict[str, object]]:
    """Build the provider payload for the AI review prompt.

    Enriches each provider row with `declared_capabilities` (sorted tuple of
    capability strings the adapter advertises) and `unknown: True` when the
    provider's `kind` is not in the live adapter catalog. The LLM uses this
    to ground its mappings instead of guessing from the name alone.
    """
    payload: list[dict[str, object]] = []
    for r in rows:
        entry = catalog.find(r.kind)
        if entry is None:
            declared: tuple[str, ...] = ()
            unknown = True
        else:
            declared = entry.capabilities
            unknown = False
        cfg = getattr(r, "extra_config", None) or {}
        mode = getattr(r, "mode", None) or "builtin"
        url = (
            getattr(r, "mcp_url", None)
            if mode == "mcp"
            else getattr(r, "base_url", None)
        )
        payload.append(
            {
                "id": r.id,
                "category": getattr(r, "category", None) or r.kind,
                "kind": r.kind,
                "provider": r.kind,
                "label": getattr(r, "label", None) or r.kind,
                "mode": mode,
                "url": url,
                "status": cfg.get("wizard_status") or "pending",
                "priority": getattr(r, "priority", None) or cfg.get("default_priority", 100),
                "declared_capabilities": list(declared),
                "unknown": unknown,
            }
        )
    return payload


def _try_deterministic_review(
    departments: list[tuple[str, list[str]]],
    providers: list[dict[str, object]],
) -> ReviewResult | None:
    """Resolve every basic requirement against declared_capabilities.

    Returns a complete `ReviewResult` when every basic requirement matches at
    least one provider's declared_capabilities and no `unknown=True`
    providers exist. Returns None when the LLM must adjudicate.

    Confidence is fixed at 1.0 for deterministic matches — the resolver is
    set-membership, so there's no inference involved.
    """
    if any(p.get("unknown") for p in providers):
        return None

    by_capability: dict[str, dict[str, object]] = {}
    for p in providers:
        for cap in p.get("declared_capabilities", []) or []:
            by_capability.setdefault(cap, p)

    department_results: list[DepartmentReadiness] = []
    for dept_id, basic_reqs in departments:
        basic: list[RequirementMapping] = []
        unmet: list[str] = []
        for req in basic_reqs:
            prov = by_capability.get(req)
            if prov is None:
                unmet.append(req)
            else:
                basic.append(_mapping_from_provider(req, prov, confidence=1.0))
        state = ReadinessState.READY if not unmet else ReadinessState.BLOCKED
        department_results.append(
            DepartmentReadiness(
                id=dept_id,
                state=state,
                note=None,
                basic=basic,
                advanced=[],
                unmet=unmet,
                check_status="checked",
            )
        )

    ready_count = sum(1 for d in department_results if d.state == ReadinessState.READY)
    summary = f"{ready_count} of {len(department_results)} ready."
    return ReviewResult(summary=summary, departments=department_results)


def _mapping_from_provider(
    req: str,
    prov: dict[str, object],
    *,
    confidence: float,
) -> RequirementMapping:
    """Build a RequirementMapping enriched with provider wiring details."""
    return RequirementMapping(
        type=req,
        provider=str(prov.get("kind") or prov.get("provider") or "") or None,
        confidence=confidence,
        provider_id=str(prov.get("id")) if prov.get("id") is not None else None,
        provider_label=str(prov.get("label") or prov.get("kind") or "") or None,
        provider_mode=str(prov.get("mode") or "") or None,
        provider_url=str(prov.get("url") or "") or None,
        provider_status=str(prov.get("status") or "") or None,
    )


async def _run_with_own_session(
    *,
    review_id: str,
    db_session_factory: Callable[[], Session],
    departments: list[tuple[str, list[str]]],
    providers: list[dict[str, object]],
    store: review_store_mod.ReviewStore,
    llm_wrapper: _ReviewLLMWrapper,
) -> None:
    """Open our own session, run the review, close session on exit."""
    session = db_session_factory()
    try:
        await _run_review_impl(
            review_id=review_id,
            db=session,
            llm=llm_wrapper,
            departments=departments,
            providers=providers,
            store=store,
        )
    finally:
        try:
            session.close()
        except Exception:
            pass


def schedule_review(
    *,
    db: Session,
    db_session_factory: Callable[[], Session],
    background_tasks: set[asyncio.Task[Any]],
    store: review_store_mod.ReviewStore,
    departments: list[tuple[str, list[str]]],
) -> str:
    """Run deterministic resolver first; fall back to LLM only when needed.

    Returns the new review_id. The background task opens its own DB session —
    the request-scoped `db` is only used here to read the registry and
    provider rows synchronously before scheduling. The deterministic path
    is now also background-scheduled so per-department progress updates
    reach the UI as each department is verified.
    """
    from openlia.llm.adapters import build_adapter
    from openlia.llm.capabilities import capabilities_for
    from openlia.llm.types import ModelTier

    from openlia_server.services.data_providers import list_providers as list_dp
    from openlia_server.services.llm_registry import SQLModelRegistry

    review_id = store.create()

    catalog = build_catalog()
    dp_rows = list_dp(db)
    providers = _build_provider_payload(dp_rows, catalog)

    has_unknown = any(p.get("unknown") for p in providers)

    if not has_unknown:
        # Deterministic path: still run as a background task so the UI sees
        # departments verified one-by-one with real per-provider health pings.
        task = asyncio.create_task(
            _run_deterministic_progressive(
                review_id=review_id,
                departments=departments,
                providers=providers,
                store=store,
                db_session_factory=db_session_factory,
            )
        )
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)
        return review_id

    registry = SQLModelRegistry(db)
    row = registry.get_tier_default(ModelTier.QUICK) or registry.get_any_in_tier(ModelTier.QUICK)

    if row is None:
        store.update(review_id, state="failed", error="No Quick-tier LLM configured.")
        return review_id

    adapter = build_adapter(
        kind=row.provider_kind,
        credentials=row.credentials,
        model=row.model_ref,
        capabilities=capabilities_for(
            provider_kind=row.provider_kind,
            model=row.model_ref,
            override=row.capability_override,
        ),
    )
    llm_wrapper = _ReviewLLMWrapper(adapter)

    task = asyncio.create_task(
        _run_with_own_session(
            review_id=review_id,
            db_session_factory=db_session_factory,
            departments=departments,
            providers=providers,
            store=store,
            llm_wrapper=llm_wrapper,
        )
    )
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    return review_id


async def _run_deterministic_progressive(
    *,
    review_id: str,
    departments: list[tuple[str, list[str]]],
    providers: list[dict[str, object]],
    store: review_store_mod.ReviewStore,
    db_session_factory: Callable[[], Session],
) -> None:
    """Run the deterministic resolver one department at a time.

    For each department:
      1. Build the requirement→provider mapping.
      2. Re-run the wizard health-check on each unique provider involved
         (cached per provider so we ping once per review).
      3. Mark the department as ready/blocked, write to the store, and pause
         briefly so the UI's poll picks up the progressive update.
    """
    from openlia_server.services.wizard_providers import _run_health_check

    by_capability: dict[str, dict[str, object]] = {}
    for p in providers:
        for cap in p.get("declared_capabilities", []) or []:
            by_capability.setdefault(cap, p)

    # Build initial pending-list of all departments so the UI can show them
    # immediately — none of them are yet verified.
    initial_departments = [
        DepartmentReadiness(
            id=dept_id,
            state=ReadinessState.READY,
            note=None,
            basic=[],
            advanced=[],
            unmet=[],
            check_status="pending",
        )
        for dept_id, _ in departments
    ]
    store.update(
        review_id,
        state="running",
        progress=0,
        result={
            "summary": "Checking departments…",
            "departments": [d.model_dump() for d in initial_departments],
        },
    )

    # Cache per-provider health-check results so we ping each provider once.
    provider_health: dict[str, tuple[bool, str | None]] = {}

    session = db_session_factory()
    try:
        from openlia_server.services.data_providers import get_provider as _get_provider

        completed: list[DepartmentReadiness] = []
        for index, (dept_id, basic_reqs) in enumerate(departments):
            basic: list[RequirementMapping] = []
            unmet: list[str] = []
            providers_for_dept: set[str] = set()
            for req in basic_reqs:
                prov = by_capability.get(req)
                if prov is None:
                    unmet.append(req)
                    continue
                pid = str(prov.get("id") or "")
                providers_for_dept.add(pid)
                basic.append(_mapping_from_provider(req, prov, confidence=1.0))

            # Verify each unique provider this department depends on by
            # re-running the live health check (cached per provider).
            blocked_by_health: list[str] = []
            for pid in providers_for_dept:
                if not pid:
                    continue
                if pid not in provider_health:
                    try:
                        row = _get_provider(session, pid)
                    except Exception:
                        provider_health[pid] = (False, "provider not found")
                    else:
                        provider_health[pid] = await _run_health_check(row)
                ok, err = provider_health[pid]
                if not ok:
                    blocked_by_health.append(err or "health check failed")

            if unmet:
                state = ReadinessState.BLOCKED
            elif blocked_by_health:
                state = ReadinessState.BLOCKED
                # Annotate the mapping(s) with the failure message so the UI
                # surfaces it under the adapter setup view.
                for m in basic:
                    if m.provider_status not in ("ok",):
                        m.provider_status = m.provider_status or "error"
            else:
                state = ReadinessState.READY

            note = "; ".join(blocked_by_health) if blocked_by_health else None
            completed.append(
                DepartmentReadiness(
                    id=dept_id,
                    state=state,
                    note=note,
                    basic=basic,
                    advanced=[],
                    unmet=unmet,
                    check_status="checked",
                )
            )

            # Build the running list: completed departments first, then the
            # remaining ones still pending.
            remaining = [
                DepartmentReadiness(
                    id=did,
                    state=ReadinessState.READY,
                    note=None,
                    basic=[],
                    advanced=[],
                    unmet=[],
                    check_status="pending",
                )
                for did, _ in departments[index + 1 :]
            ]
            running_departments = completed + remaining
            ready_count = sum(
                1 for d in completed if d.state == ReadinessState.READY
            )
            store.update(
                review_id,
                state="running",
                progress=int(((index + 1) / max(1, len(departments))) * 100),
                result={
                    "summary": (
                        f"Checked {index + 1} of {len(departments)} "
                        f"({ready_count} ready)"
                    ),
                    "departments": [d.model_dump() for d in running_departments],
                },
            )
            # Brief pause so the UI poll (1.5s) catches the intermediate state.
            await asyncio.sleep(0.4)

        ready_count = sum(1 for d in completed if d.state == ReadinessState.READY)
        store.update(
            review_id,
            state="complete",
            progress=100,
            result={
                "summary": f"{ready_count} of {len(completed)} ready",
                "departments": [d.model_dump() for d in completed],
            },
        )
    finally:
        try:
            session.close()
        except Exception:
            pass
