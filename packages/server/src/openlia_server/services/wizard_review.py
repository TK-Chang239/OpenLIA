"""Setup-wizard AI review orchestration.

Owns session lifetime for the background task. Handlers schedule the task,
this module opens its own DB session via the factory passed in — never
captures a request-scoped session that FastAPI will close before the task
finishes.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from openlia_server.ai_review import store as review_store_mod
from openlia_server.ai_review.runner import run_review as _run_review_impl


class _ReviewLLMWrapper:
    """Bridges the runner's (prompt, max_tokens) protocol with the real adapter."""

    def __init__(self, adapter: Any) -> None:
        self._adapter = adapter

    async def generate(self, *, prompt: str, max_tokens: int) -> Any:
        from openlia.llm.types import LLMRequest, Message

        req = LLMRequest(messages=[Message(role="user", content=prompt)], max_tokens=max_tokens)
        return await self._adapter.generate(req)


def _build_provider_payload(rows: list[Any]) -> list[dict[str, object]]:
    """Build the provider payload for the AI review prompt.

    Includes both `category` (financial/news/...) and `kind` (eodhd/fmp/...)
    so the LLM can route requirements correctly. `provider` mirrors `kind`
    for backwards compatibility with the older payload shape.
    """
    payload: list[dict[str, object]] = []
    for r in rows:
        payload.append(
            {
                "id": r.id,
                "category": getattr(r, "category", None) or r.kind,
                "kind": r.kind,
                "provider": r.kind,
                "priority": getattr(r, "priority", None)
                or (r.extra_config or {}).get("default_priority", 100),
            }
        )
    return payload


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
    """Build the LLM adapter, snapshot providers, and start the review task.

    Returns the new review_id. The task opens its own DB session — the
    request-scoped `db` is only used here to read the registry and provider
    rows synchronously before scheduling.
    """
    from openlia.llm.adapters import build_adapter
    from openlia.llm.capabilities import capabilities_for
    from openlia.llm.types import ModelTier

    from openlia_server.services.data_providers import list_providers as list_dp
    from openlia_server.services.llm_registry import SQLModelRegistry

    review_id = store.create()

    registry = SQLModelRegistry(db)
    row = registry.get_tier_default(ModelTier.QUICK) or registry.get_any_in_tier(ModelTier.QUICK)

    dp_rows = list_dp(db)
    providers = _build_provider_payload(dp_rows)

    if row is None:
        store.update(review_id, state="failed", error="No Quick-tier LLM configured.")
        return review_id

    adapter = build_adapter(
        kind=row.provider_kind,
        credentials=row.credentials,
        model=row.model_ref,
        capabilities=capabilities_for(row.provider_kind, row.model_ref, row.capability_override),
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
