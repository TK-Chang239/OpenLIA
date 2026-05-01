"""Wizard-time adapter LLM client.

The connector adapter (`openlia.connectors.adapter.callable_spec_resolver`)
expects an `LlmClient` Protocol with `async generate_json(*, prompt) -> dict`.
This module:

1. Wraps an `LLMProvider` instance into that Protocol via `AdapterLlmJsonClient`.
2. Builds the per-call factory the proposed-specs route hands to the resolver.

The factory resolves a model from `SQLModelRegistry` per call so a freshly
configured provider/model takes effect without restarting the server. If
no model is resolvable, it raises `AdapterLlmNotConfigured` so the route
can return a clean 422 instead of a 500 from a bare `RuntimeError`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from openlia.connectors.adapter import LlmClient, ResolverError
from openlia.llm.adapters import build_adapter
from openlia.llm.base import LLMProvider
from openlia.llm.exceptions import TierNotConfiguredError
from openlia.llm.resolver import resolve
from openlia.llm.types import LLMRequest, Message, ModelTier, ResponseFormat
from sqlalchemy.orm import Session as DBSession

from openlia_server.services.llm_registry import SQLModelRegistry

# Synthetic department id used when resolving a model for the adapter LLM
# itself (it is not a real department). Falls through to tier-default.
_ADAPTER_DEPARTMENT_ID = "_wizard_adapter"

# The adapter task is structured-JSON binding — quick tier is the right
# default. If quick is not configured the factory falls back to everyday.
_PREFERRED_TIERS: tuple[ModelTier, ...] = (ModelTier.QUICK, ModelTier.EVERYDAY, ModelTier.THINKING)

_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL)


class AdapterLlmNotConfigured(Exception):
    """Raised when no LLM model is available to drive the wizard adapter."""


class AdapterLlmJsonClient(LlmClient):
    """Wraps an `LLMProvider` so it satisfies the `LlmClient` Protocol used
    by `resolve_callable_spec`.

    The provider is asked for a JSON object via `response_format=json_object`.
    Adapters that ignore this hint are tolerated: we strip a markdown fence
    if present and parse the body.
    """

    def __init__(self, *, provider: LLMProvider) -> None:
        self._provider = provider

    async def generate_json(self, *, prompt: str) -> dict[str, Any]:
        request = LLMRequest(
            messages=[Message(role="user", content=prompt)],
            system="Return ONLY a JSON object. No prose, no fences.",
            response_format=ResponseFormat(kind="json_object"),
            max_tokens=1024,
            temperature=0.0,
        )
        response = await self._provider.generate(request)
        text = (response.text or "").strip()
        text = _strip_fence(text)
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ResolverError(f"adapter LLM returned non-JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ResolverError("adapter LLM returned a non-object JSON value")
        return parsed


def _strip_fence(text: str) -> str:
    match = _FENCE_RE.match(text.strip())
    if match is None:
        return text
    return match.group(1).strip()


def make_adapter_llm_client_factory(
    db_session_factory: Callable[[], DBSession],
) -> Callable[[], LlmClient]:
    """Build the per-call factory the proposed-specs route hands the resolver.

    Each call opens a fresh DB session, resolves a model via `SQLModelRegistry`,
    and returns a wrapped `LLMProvider`. Raises `AdapterLlmNotConfigured` if
    no enabled model exists in any preferred tier.
    """

    def _factory() -> LlmClient:
        db = db_session_factory()
        try:
            registry = SQLModelRegistry(db)
            resolved = None
            last_error: TierNotConfiguredError | None = None
            for tier in _PREFERRED_TIERS:
                try:
                    resolved = resolve(
                        department_id=_ADAPTER_DEPARTMENT_ID,
                        registry=registry,
                        user_id=None,
                        tier_override=tier,
                    )
                    break
                except TierNotConfiguredError as exc:
                    last_error = exc
                    continue
            if resolved is None:
                raise AdapterLlmNotConfigured(
                    "No LLM model is configured. Add a provider and model in "
                    "Settings → Models before running connector resolve."
                ) from last_error

            provider = build_adapter(
                kind=resolved.provider_kind,
                credentials=resolved.credentials,
                model=resolved.model_ref,
                capabilities=resolved.capabilities,
            )
            return AdapterLlmJsonClient(provider=provider)
        finally:
            db.close()

    return _factory


# Agentic resolver: prefer the thinking tier so the LLM has the headroom
# to navigate large repos via filesystem tools (per the grounding plan).
_AGENTIC_TIERS: tuple[ModelTier, ...] = (
    ModelTier.THINKING,
    ModelTier.EVERYDAY,
    ModelTier.QUICK,
)


def _resolve_provider(db: DBSession, tiers: tuple[ModelTier, ...]) -> LLMProvider:
    registry = SQLModelRegistry(db)
    last_error: TierNotConfiguredError | None = None
    for tier in tiers:
        try:
            resolved = resolve(
                department_id=_ADAPTER_DEPARTMENT_ID,
                registry=registry,
                user_id=None,
                tier_override=tier,
            )
        except TierNotConfiguredError as exc:
            last_error = exc
            continue
        return build_adapter(
            kind=resolved.provider_kind,
            credentials=resolved.credentials,
            model=resolved.model_ref,
            capabilities=resolved.capabilities,
        )
    raise AdapterLlmNotConfigured(
        "No LLM model is configured. Add a provider and model in "
        "Settings → Models before running connector resolve."
    ) from last_error


def make_agentic_resolver_factory(
    db_session_factory: Callable[[], DBSession],
) -> Callable[..., LlmClient]:
    """Build the per-connector factory the dept resolve route hands the service.

    Each invocation opens a fresh DB session (so newly-configured models
    take effect immediately), resolves a thinking-tier `LLMProvider`, and
    wraps it in an `AgenticResolverClient` scoped to the connector's
    grounding clone path. With `connector_root=None` the agentic loop
    degrades to a single-shot JSON call. An optional `tool_call_listener`
    is forwarded to the client so the wizard can stream a live tool-call
    log to the user.
    """
    from openlia.llm.types import ToolCall

    from openlia_server.services.agentic_resolver_client import (
        AgenticResolverClient,
    )

    def _factory(
        connector_root: Path | None,
        *,
        tool_call_listener: Callable[[ToolCall], None] | None = None,
    ) -> LlmClient:
        db = db_session_factory()
        try:
            provider = _resolve_provider(db, _AGENTIC_TIERS)
        finally:
            db.close()
        return AgenticResolverClient(
            provider=provider,
            connector_root=connector_root,
            tool_call_listener=tool_call_listener,
        )

    return _factory


__all__ = [
    "AdapterLlmJsonClient",
    "AdapterLlmNotConfigured",
    "make_adapter_llm_client_factory",
    "make_agentic_resolver_factory",
]
