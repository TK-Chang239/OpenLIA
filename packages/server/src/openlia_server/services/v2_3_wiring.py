"""Startup-time wiring for the v2.3 runner factory.

Reads env vars and, when present, instantiates the LLM-backed stage
clients plus the v2.3 runner factory, returning it for the caller
(typically `app.py`) to assign onto `app.state.v2_3_runner_factory`.

Env contract — CLARIFY (required to enable the engine at all):
- ``OPENAI_API_KEY``                — auth for the OpenAI adapter
- ``OPENLIA_V2_3_CLARIFY_MODEL``    — OpenAI model id, e.g. ``gpt-5.4-mini``

Env contract — RESEARCH (optional; enables real research):
- ``OPENLIA_V2_3_RESEARCH_MODEL``   — OpenAI model id used for the
  RESEARCH tool-use loop (typically the same family as CLARIFY but
  with tool_calling enabled)
- ``EODHD_API_KEY``                 — auth for the EODHD data tools

Env contract — other stages (each optional; each NoOps when unset):
- ``OPENLIA_V2_3_PLAN_MODEL``        — PLAN model id
- ``OPENLIA_V2_3_COMPUTE_MODEL``     — COMPUTE input-proposal model id
- ``OPENLIA_V2_3_SYNTHESIZE_MODEL``  — SYNTHESIZE model id
- ``OPENLIA_V2_3_WRITE_MODEL``       — WRITE model id
- ``OPENLIA_V2_3_VERIFY_MODEL``      — VERIFY model id

CLARIFY-only optionals:
- ``OPENAI_BASE_URL``                       — base URL override
- ``OPENLIA_V2_3_CLARIFY_MAX_TOKENS``       — int; default 1024
- ``OPENLIA_V2_3_CLARIFY_TEMPERATURE``      — float; default 0.2

RESEARCH-only optionals:
- ``OPENLIA_V2_3_RESEARCH_MAX_TOKENS``      — int; default 4096
- ``OPENLIA_V2_3_RESEARCH_TEMPERATURE``     — float; default 0.3
- ``OPENLIA_V2_3_RESEARCH_MAX_TURNS``       — int; default 12

Each non-CLARIFY stage also takes ``OPENLIA_V2_3_<STAGE>_MAX_TOKENS``
and ``OPENLIA_V2_3_<STAGE>_TEMPERATURE`` overrides. The defaults are
tuned per stage in ``_STAGE_DEFAULTS`` below.

When any CLARIFY var is missing the function returns ``None`` and the
v2.3 routes respond 503 — same shape as the v2.2 engine. The other
stages fall back to NoOp when their own vars are missing, so the rest
of the pipeline still composes for tests / no-EODHD smoke runs.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

from openlia.llm.adapters import build_adapter
from openlia.llm.runtime.report_v2_3.clients.llm_clarifier import LLMClarifierClient
from openlia.llm.runtime.report_v2_3.clients.llm_researcher import LLMResearcherClient
from openlia.llm.runtime.report_v2_3.clients.llm_stage_clients import (
    LLMComputeClient,
    LLMPlannerClient,
    LLMSynthesizerClient,
    LLMVerifierClient,
    LLMWriterClient,
)
from openlia.llm.runtime.report_v2_3.clients.researcher import ResearcherClient
from openlia.llm.runtime.report_v2_3.research import build_research_tools
from openlia.llm.types import Capabilities, ProviderCredentials

from .v2_3_runner_factory import V23RunnerFactory, make_v2_3_runner_factory
from .v2_stage_factory import SyncJsonLlmClient, SyncToolLlmClient

log = logging.getLogger(__name__)


def build_v2_3_runner_factory_from_env() -> V23RunnerFactory | None:
    """Return a v2.3 factory configured from env, or None if not configured."""
    api_key = os.getenv("OPENAI_API_KEY")
    clarify_model = os.getenv("OPENLIA_V2_3_CLARIFY_MODEL")
    if not api_key or not clarify_model:
        log.info(
            "v2.3 engine env vars not set (OPENAI_API_KEY=%s, "
            "OPENLIA_V2_3_CLARIFY_MODEL=%s); v2.3 routes will respond 503",
            "***" if api_key else "missing",
            "set" if clarify_model else "missing",
        )
        return None

    base_url = os.getenv("OPENAI_BASE_URL")
    clarifier = _build_clarifier(api_key=api_key, model=clarify_model, base_url=base_url)
    researcher = _build_researcher(api_key=api_key, base_url=base_url)
    planner = _build_json_stage_client(
        api_key=api_key, base_url=base_url, stage="PLAN", ctor=LLMPlannerClient
    )
    compute = _build_json_stage_client(
        api_key=api_key, base_url=base_url, stage="COMPUTE", ctor=LLMComputeClient
    )
    synthesizer = _build_json_stage_client(
        api_key=api_key, base_url=base_url, stage="SYNTHESIZE", ctor=LLMSynthesizerClient
    )
    writer = _build_json_stage_client(
        api_key=api_key, base_url=base_url, stage="WRITE", ctor=LLMWriterClient
    )
    verifier = _build_json_stage_client(
        api_key=api_key, base_url=base_url, stage="VERIFY", ctor=LLMVerifierClient
    )

    log.info(
        "v2.3 engine wired (clarify=%s, research=%s, plan=%s, compute=%s, "
        "synthesize=%s, write=%s, verify=%s)",
        clarify_model,
        "real" if researcher is not None else "noop",
        "real" if planner is not None else "noop",
        "real" if compute is not None else "noop",
        "real" if synthesizer is not None else "noop",
        "real" if writer is not None else "noop",
        "real" if verifier is not None else "noop",
    )
    return make_v2_3_runner_factory(
        clarifier,
        planner_client=planner,
        researcher_client=researcher,
        compute_client=compute,
        synthesizer_client=synthesizer,
        writer_client=writer,
        verifier_client=verifier,
    )


# ---------------------------------------------------------------------------
# Per-stage defaults (model token budget + temperature)
# ---------------------------------------------------------------------------


_STAGE_DEFAULTS: dict[str, tuple[int, float]] = {
    # max_tokens, temperature
    "PLAN": (2048, 0.3),
    "COMPUTE": (1024, 0.2),
    "SYNTHESIZE": (4096, 0.3),
    "WRITE": (4096, 0.4),
    "VERIFY": (2048, 0.2),
}


def _build_json_stage_client(
    *,
    api_key: str,
    base_url: str | None,
    stage: str,
    ctor: Callable[[Callable[..., dict]], Any],
) -> Any | None:
    """Generic builder for the JSON-only stages (PLAN/COMPUTE/SYNTHESIZE/
    WRITE/VERIFY). Each follows the LLMClarifier pattern: one OpenAI
    provider, one SyncJsonLlmClient, one stage client constructor."""
    model = os.getenv(f"OPENLIA_V2_3_{stage}_MODEL")
    if not model:
        log.info("OPENLIA_V2_3_%s_MODEL unset; %s stage will NoOp.", stage, stage)
        return None
    default_max, default_temp = _STAGE_DEFAULTS[stage]
    max_tokens = int(os.getenv(f"OPENLIA_V2_3_{stage}_MAX_TOKENS", str(default_max)))
    temperature = float(os.getenv(f"OPENLIA_V2_3_{stage}_TEMPERATURE", str(default_temp)))

    credentials = ProviderCredentials(
        api_key=api_key,
        base_url=base_url,
        env_var_name="OPENAI_API_KEY",
    )
    provider = build_adapter(
        kind="openai",
        credentials=credentials,
        model=model,
        capabilities=Capabilities(
            structured_output=True,
            max_context_tokens=128_000,
            max_output_tokens=max_tokens,
        ),
    )
    json_client = SyncJsonLlmClient(provider, max_tokens=max_tokens, temperature=temperature)
    return ctor(json_client.call)


def _build_clarifier(*, api_key: str, model: str, base_url: str | None) -> LLMClarifierClient:
    max_tokens = int(os.getenv("OPENLIA_V2_3_CLARIFY_MAX_TOKENS", "1024"))
    temperature = float(os.getenv("OPENLIA_V2_3_CLARIFY_TEMPERATURE", "0.2"))

    credentials = ProviderCredentials(
        api_key=api_key,
        base_url=base_url,
        env_var_name="OPENAI_API_KEY",
    )
    provider = build_adapter(
        kind="openai",
        credentials=credentials,
        model=model,
        capabilities=Capabilities(
            structured_output=True,
            max_context_tokens=128_000,
            max_output_tokens=max_tokens,
        ),
    )
    json_client = SyncJsonLlmClient(provider, max_tokens=max_tokens, temperature=temperature)
    return LLMClarifierClient(json_client.call)


def _build_researcher(*, api_key: str, base_url: str | None) -> ResearcherClient | None:
    research_model = os.getenv("OPENLIA_V2_3_RESEARCH_MODEL")
    eodhd_key = os.getenv("EODHD_API_KEY")
    if not research_model:
        log.info("OPENLIA_V2_3_RESEARCH_MODEL unset; RESEARCH stage will NoOp.")
        return None
    if not eodhd_key:
        log.info("EODHD_API_KEY unset; RESEARCH stage will NoOp (no data tools).")
        return None

    max_tokens = int(os.getenv("OPENLIA_V2_3_RESEARCH_MAX_TOKENS", "4096"))
    temperature = float(os.getenv("OPENLIA_V2_3_RESEARCH_TEMPERATURE", "0.3"))
    max_turns = int(os.getenv("OPENLIA_V2_3_RESEARCH_MAX_TURNS", "12"))

    credentials = ProviderCredentials(
        api_key=api_key,
        base_url=base_url,
        env_var_name="OPENAI_API_KEY",
    )
    provider = build_adapter(
        kind="openai",
        credentials=credentials,
        model=research_model,
        capabilities=Capabilities(
            tool_calling=True,
            structured_output=True,
            max_context_tokens=128_000,
            max_output_tokens=max_tokens,
        ),
    )
    tool_client = SyncToolLlmClient(provider, max_tokens=max_tokens, temperature=temperature)
    tools = _build_eodhd_tool_set(eodhd_key)
    return LLMResearcherClient(tool_client, tools, max_turns=max_turns)


# ---------------------------------------------------------------------------
# Per-user factory builder — takes a {slot: ResolvedModel} mapping built
# from the caller's er_v2_3_model_assignments rows. Mirrors v2.2's
# ``build_runner_v2(models_by_slot=...)`` shape so the route layer can
# pick the right model per stage per user.
# ---------------------------------------------------------------------------


_STAGE_DEFAULTS_PER_USER: dict[str, tuple[int, float]] = {
    # Mirrors _STAGE_DEFAULTS but includes CLARIFY (env path keeps its own
    # block for backwards compat).
    "clarify": (1024, 0.2),
    "plan": (2048, 0.3),
    "research": (4096, 0.3),
    "compute": (1024, 0.2),
    "synthesize": (4096, 0.3),
    "write": (4096, 0.4),
    "verify": (2048, 0.2),
}


def build_v2_3_runner_factory_from_models(
    *,
    models_by_slot: dict[str, Any],  # actually ResolvedModel
    eodhd_api_key: str | None = None,
    research_max_turns: int = 12,
) -> V23RunnerFactory:
    """Build a V23RunnerFactory from per-user resolved models.

    The route layer calls this per request after resolving the user's
    ``er_v2_3_model_assignments`` rows through ``SQLModelRegistry``.
    Slots absent from ``models_by_slot`` stay NoOp (the runner gates
    on CLARIFY only; the other six gracefully no-op when unbound).

    RESEARCH additionally requires ``eodhd_api_key`` to wire its tool
    set. Missing key -> NoOp RESEARCH stage even if a model is assigned.
    """
    if "clarify" not in models_by_slot:
        raise ValueError(
            "v2.3 runner factory requires at least the 'clarify' slot to be "
            "assigned; v2.3 cannot start without a working clarifier."
        )

    clarifier = _build_json_client_from_resolved(
        models_by_slot["clarify"], stage="clarify", ctor=LLMClarifierClient
    )
    planner = (
        _build_json_client_from_resolved(
            models_by_slot["plan"], stage="plan", ctor=LLMPlannerClient
        )
        if "plan" in models_by_slot
        else None
    )
    compute = (
        _build_json_client_from_resolved(
            models_by_slot["compute"], stage="compute", ctor=LLMComputeClient
        )
        if "compute" in models_by_slot
        else None
    )
    synthesizer = (
        _build_json_client_from_resolved(
            models_by_slot["synthesize"], stage="synthesize", ctor=LLMSynthesizerClient
        )
        if "synthesize" in models_by_slot
        else None
    )
    writer = (
        _build_json_client_from_resolved(
            models_by_slot["write"], stage="write", ctor=LLMWriterClient
        )
        if "write" in models_by_slot
        else None
    )
    verifier = (
        _build_json_client_from_resolved(
            models_by_slot["verify"], stage="verify", ctor=LLMVerifierClient
        )
        if "verify" in models_by_slot
        else None
    )

    researcher: ResearcherClient | None = None
    if "research" in models_by_slot and eodhd_api_key:
        max_tokens, temperature = _STAGE_DEFAULTS_PER_USER["research"]
        provider = build_adapter(
            kind="openai",
            credentials=models_by_slot["research"].credentials,
            model=models_by_slot["research"].model_ref,
            capabilities=Capabilities(
                tool_calling=True,
                structured_output=True,
                max_context_tokens=128_000,
                max_output_tokens=max_tokens,
            ),
        )
        tool_client = SyncToolLlmClient(provider, max_tokens=max_tokens, temperature=temperature)
        tools = _build_eodhd_tool_set(eodhd_api_key)
        researcher = LLMResearcherClient(tool_client, tools, max_turns=research_max_turns)
    elif "research" in models_by_slot:
        log.info("research model assigned but EODHD_API_KEY missing; RESEARCH will NoOp.")

    return make_v2_3_runner_factory(
        clarifier,
        planner_client=planner,
        researcher_client=researcher,
        compute_client=compute,
        synthesizer_client=synthesizer,
        writer_client=writer,
        verifier_client=verifier,
    )


def _build_json_client_from_resolved(
    resolved: Any,  # ResolvedModel
    *,
    stage: str,
    ctor: Callable[[Callable[..., dict]], Any],
) -> Any:
    max_tokens, temperature = _STAGE_DEFAULTS_PER_USER[stage]
    provider = build_adapter(
        kind=resolved.provider_kind,
        credentials=resolved.credentials,
        model=resolved.model_ref,
        capabilities=Capabilities(
            structured_output=True,
            max_context_tokens=128_000,
            max_output_tokens=max_tokens,
        ),
    )
    json_client = SyncJsonLlmClient(provider, max_tokens=max_tokens, temperature=temperature)
    return ctor(json_client.call)


def _build_eodhd_tool_set(eodhd_api_key: str) -> list[Any]:
    """Adapt ``eodhd.APIClient`` to the v2.3 transport signatures."""
    from eodhd import APIClient

    client = APIClient(api_key=eodhd_api_key)

    def fundamentals(ticker: str) -> dict:
        raw = client.get_fundamentals_data(ticker)
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):
            return raw[0]
        return {"value": raw}

    def prices(ticker: str, from_date: str, to_date: str) -> list:
        rows = client.get_eod_historical_stock_market_data(
            symbol=ticker, period="d", from_date=from_date, to_date=to_date
        )
        return list(rows) if rows else []

    def news(ticker: str, limit: int) -> list:
        rows = client.financial_news(s=ticker, limit=limit)
        return list(rows) if rows else []

    return build_research_tools(fundamentals=fundamentals, prices=prices, news=news)
