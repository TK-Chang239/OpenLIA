"""Production v2.2 stage factory.

Builds a ``RunnerV2`` with all 8 LLM-using stages wired to per-slot models
chosen by the caller. The factory accepts a `models_by_slot` mapping built
by the route layer from the caller's ``er_v2_model_assignments`` DB rows;
no env-driven default is supplied — runs are refused upstream when any
slot is unassigned.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from openlia.llm.adapters import build_adapter
from openlia.llm.base import LLMProvider
from openlia.llm.runtime.report_v2.pipeline.stage_1_clarify import Clarifier
from openlia.llm.runtime.report_v2.pipeline.stage_3_research_plan import (
    ResearchPlanner,
)
from openlia.llm.runtime.report_v2.pipeline.stage_4_gather import StrandDispatcher
from openlia.llm.runtime.report_v2.pipeline.stage_5_model_plan import ModelPlanner
from openlia.llm.runtime.report_v2.pipeline.stage_6_model_build import ModelBuilder
from openlia.llm.runtime.report_v2.pipeline.stage_7_draft import SectionDrafter
from openlia.llm.runtime.report_v2.pipeline.stage_8_verify import Verifier
from openlia.llm.runtime.report_v2.pipeline.trigger_evaluator import TriggerEvaluator
from openlia.llm.runtime.report_v2.pipeline.verifier_llm import LLMVerifier
from openlia.llm.runtime.report_v2.runner_v2 import RunnerV2
from openlia.llm.runtime.report_v2.slots import V2Slot
from openlia.llm.runtime.report_v2_3.clients.llm_researcher import ToolTurnResponse
from openlia.llm.types import (
    LLMRequest,
    Message,
    ResolvedModel,
    ResponseFormat,
    ToolSchema,
)

log = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL)


# ---------------------------------------------------------------------------
# Sync JSON LLM client — wraps async LLMProvider for the v2 stages.
# ---------------------------------------------------------------------------


class SyncJsonLlmClient:
    """Sync ``.call(system, user) -> dict`` wrapper around an async ``LLMProvider``.

    The v2 pipeline stages (Clarifier, ResearchPlanner, ModelPlanner,
    ModelBuilder, SectionDrafter, TriggerEvaluator) all expect this exact
    shape — see ``stage_3_research_plan.py`` for the canonical call site.
    """

    def __init__(
        self,
        provider: LLMProvider,
        *,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> None:
        self._provider = provider
        self._max_tokens = max_tokens
        self._temperature = temperature

    _JSON_DIRECTIVE = (
        "\n\nReturn ONLY a single JSON object. No prose, no markdown fences,"
        " no explanation. Start with { and end with }."
    )

    def call(self, *, system: str | None, user: Any) -> dict[str, Any]:
        if isinstance(user, str):
            user_text = user
        else:
            user_text = json.dumps(user, default=_json_default)

        system_with_directive = (system or "") + self._JSON_DIRECTIVE

        request = LLMRequest(
            messages=[Message(role="user", content=user_text)],
            system=system_with_directive,
            response_format=ResponseFormat(kind="json_object"),
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )

        response = _run_sync(self._provider.generate(request))
        text = (response.text or "").strip()
        text = _strip_fence(text)

        if not text:
            log.warning("v2 LLM returned empty body — substituting {}")
            return {}

        parsed = _try_parse_json(text)
        if parsed is None:
            log.warning(
                "v2 LLM produced non-JSON body, returning {}; head=%r",
                text[:200],
            )
            return {}

        if not isinstance(parsed, dict):
            log.warning(
                "v2 LLM produced non-object JSON (%s), wrapping under 'value'",
                type(parsed).__name__,
            )
            return {"value": parsed}
        return parsed


# ---------------------------------------------------------------------------
# Sync tool-use LLM client — wraps async LLMProvider for the v2.3 researcher.
# ---------------------------------------------------------------------------


class SyncToolLlmClient:
    """Sync ``.send(...)`` wrapper that runs one tool-use turn.

    Matches the v2.3 ``ToolLLMClient`` protocol. Each call hands the
    provider the current conversation + tool schemas and returns the
    text + tool calls from a single turn — the v2.3 ``LLMResearcherClient``
    owns the loop and decides when to stop. Tool execution happens in
    the researcher, NOT here.
    """

    def __init__(
        self,
        provider: LLMProvider,
        *,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        native_tools: tuple[str, ...] = (),
    ) -> None:
        self._provider = provider
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._native_tools = native_tools

    def send(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[ToolSchema],
    ) -> ToolTurnResponse:
        request = LLMRequest(
            messages=list(messages),
            system=system,
            tools=list(tools) if tools else None,
            native_tools=self._native_tools,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )
        response = _run_sync(self._provider.generate(request))
        return ToolTurnResponse(
            text=response.text or "",
            tool_calls=tuple(response.tool_calls),
            citations=tuple(response.citations),
        )


def _json_default(value: Any) -> Any:
    """Fallback JSON encoder for Pydantic models, dataclasses, etc."""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "__dict__"):
        return vars(value)
    return str(value)


def _strip_fence(text: str) -> str:
    match = _FENCE_RE.match(text.strip())
    if match is None:
        return text
    return match.group(1).strip()


def _try_parse_json(text: str) -> Any:
    """Attempt several recovery strategies for prose-wrapped LLM JSON.

    Anthropic and other providers may ignore ``response_format=json_object``;
    they often prefix with a sentence ("Here is the JSON object:") and may
    wrap in fences (already stripped earlier). We try, in order:

    1. Direct ``json.loads``.
    2. Substring from the first ``{`` to the last ``}``.
    3. Substring from the first ``[`` to the last ``]`` (array fallback).
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        candidate = text[first_brace : last_brace + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    first_sq = text.find("[")
    last_sq = text.rfind("]")
    if first_sq != -1 and last_sq > first_sq:
        candidate = text[first_sq : last_sq + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    return None


def _run_sync(coro: Any) -> Any:
    """Drive an async coroutine to completion from a sync context.

    The v2 stages are sync; FastAPI routes execute them inside a thread
    via ``StreamingResponse``, so a nested ``asyncio.run`` is safe.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        # We are inside an already-running loop — schedule on a new one in
        # a worker thread so we do not deadlock.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Strand subagent — minimal LLM-driven research strand executor.
# ---------------------------------------------------------------------------


class SimpleStrandSubagent:
    """Minimal v2 strand subagent that yields findings + citations via the LLM.

    The full v2.2 design contemplates tool-equipped subagents that call
    connectors per strand. That work is out of scope for the first wiring
    cut — for now each strand becomes a single LLM call asking the model
    to summarise what it knows on the topic and surface any citations it
    can recall. Stage 4's retry-once semantics are preserved by the
    dispatcher itself; this subagent just provides the raw run() entry.
    """

    _SYSTEM = (
        "You are a research strand subagent. Produce a JSON object with"
        " keys: 'findings' (markdown string summarising what is known"
        " about the strand's purpose, citing dates where possible) and"
        " 'citations' (list of {id, kind, title, url, source}). If you"
        " have no citations, return an empty list. Do not fabricate URLs."
    )

    def __init__(self, llm: SyncJsonLlmClient) -> None:
        self._llm = llm

    def run(
        self,
        *,
        strand: Any,
        composer_inputs: dict[str, Any],
        plan: Any,
    ) -> dict[str, Any]:
        user = {
            "strand_id": getattr(strand, "id", None),
            "purpose": getattr(strand, "purpose", ""),
            "allowed_tools": list(getattr(strand, "allowed_tools", []) or []),
            "composer_inputs": composer_inputs,
        }
        raw = self._llm.call(system=self._SYSTEM, user=user)

        findings = str(raw.get("findings", "")).strip()
        citations_raw = raw.get("citations", []) or []
        citations: list[dict[str, Any]] = []
        now_iso = datetime.now(UTC).isoformat()
        for c in citations_raw:
            if not isinstance(c, dict):
                continue
            cid = str(c.get("id") or f"{getattr(strand, 'id', 'cite')}-{len(citations)}")
            title = c.get("title") or c.get("source") or "Untitled source"
            url = c.get("url")
            citations.append(
                {
                    "id": cid,
                    "source_type": "internal_model",
                    "tool": None,
                    "url": url,
                    "title": str(title),
                    "retrieved_at": now_iso,
                    "snippet": c.get("snippet"),
                    "served_from_cache": False,
                }
            )

        return {
            "findings": findings,
            "citations": citations,
            "cache_hits": 0,
            "cache_misses": 0,
        }


# ---------------------------------------------------------------------------
# Provider construction from a ResolvedModel.
# ---------------------------------------------------------------------------


def _build_provider_from_resolved(resolved: ResolvedModel) -> LLMProvider:
    """Construct an LLMProvider for a single DB-resolved model row."""
    return build_adapter(
        kind=resolved.provider_kind,
        credentials=resolved.credentials,
        model=resolved.model_ref,
        capabilities=resolved.capabilities,
    )


# ---------------------------------------------------------------------------
# Public factory.
# ---------------------------------------------------------------------------


def build_runner_v2(*, models_by_slot: dict[str, ResolvedModel]) -> RunnerV2:
    """Construct a fresh ``RunnerV2`` whose stages each speak to the model
    chosen for their slot.

    `models_by_slot` keys MUST be the ``V2Slot`` string values; every slot
    in ``REQUIRED_V2_SLOTS`` must be present (the caller validates this).
    """
    providers: dict[str, LLMProvider] = {
        slot: _build_provider_from_resolved(rm) for slot, rm in models_by_slot.items()
    }
    llm_by_slot: dict[str, SyncJsonLlmClient] = {
        slot: SyncJsonLlmClient(p) for slot, p in providers.items()
    }

    drafter_llm = llm_by_slot[V2Slot.SECTION_DRAFTER.value]
    verifier_llm = llm_by_slot[V2Slot.LLM_VERIFIER.value]

    section_drafter = SectionDrafter(drafter_llm, TriggerEvaluator(drafter_llm))
    verifier = Verifier(
        llm_verifier=LLMVerifier(verifier_llm),
        drafter=section_drafter,
        section_directives={},
    )

    return RunnerV2(
        clarifier=Clarifier(llm_by_slot[V2Slot.CLARIFIER.value]),
        research_planner=ResearchPlanner(llm_by_slot[V2Slot.RESEARCH_PLANNER.value]),
        strand_dispatcher=StrandDispatcher(
            SimpleStrandSubagent(llm_by_slot[V2Slot.STRAND_SUBAGENT.value]),
            max_workers=4,
        ),
        model_planner=ModelPlanner(llm_by_slot[V2Slot.MODEL_PLANNER.value]),
        model_builder=ModelBuilder(llm_by_slot[V2Slot.MODEL_BUILDER.value], max_workers=2),
        section_drafter=section_drafter,
        verifier=verifier,
        planner_v2_2_llm=providers[V2Slot.PLANNER_V2_2.value],
    )


def make_v2_runner_stage_factory() -> Callable[[Any], RunnerV2]:
    """Build the callable assigned to ``app.state.v2_runner_stage_factory``.

    The returned factory expects ``ctx.models_by_slot`` to be populated by
    the caller. Each invocation creates a fresh ``RunnerV2`` so per-run
    state (current stage, accumulated outcomes) does not leak between
    concurrent reports.
    """

    def _factory(ctx: Any) -> RunnerV2:
        models = getattr(ctx, "models_by_slot", None)
        if not models:
            raise RuntimeError(
                "v2 stage factory: ctx.models_by_slot is empty; route must "
                "supply a per-slot model mapping"
            )
        return build_runner_v2(models_by_slot=models)

    return _factory
