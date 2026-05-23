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

CLARIFY-only optionals:
- ``OPENAI_BASE_URL``                       — base URL override
- ``OPENLIA_V2_3_CLARIFY_MAX_TOKENS``       — int; default 1024
- ``OPENLIA_V2_3_CLARIFY_TEMPERATURE``      — float; default 0.2

RESEARCH-only optionals:
- ``OPENLIA_V2_3_RESEARCH_MAX_TOKENS``      — int; default 4096
- ``OPENLIA_V2_3_RESEARCH_TEMPERATURE``     — float; default 0.3
- ``OPENLIA_V2_3_RESEARCH_MAX_TURNS``       — int; default 12

When any CLARIFY var is missing the function returns ``None`` and the
v2.3 routes respond 503 — same shape as the v2.2 engine. RESEARCH falls
back to a NoOp stage when its own vars are missing, so the rest of the
pipeline still composes for tests / no-EODHD smoke runs.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from openlia.llm.adapters import build_adapter
from openlia.llm.runtime.report_v2_3.clients.llm_clarifier import LLMClarifierClient
from openlia.llm.runtime.report_v2_3.clients.llm_researcher import LLMResearcherClient
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

    log.info(
        "v2.3 engine wired (clarify model=%s; research=%s)",
        clarify_model,
        "real" if researcher is not None else "noop",
    )
    return make_v2_3_runner_factory(clarifier, researcher_client=researcher)


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


def _build_eodhd_tool_set(eodhd_api_key: str) -> list[Any]:
    """Adapt ``eodhd.APIClient`` to the v2.3 transport signatures."""
    from eodhd import APIClient

    client = APIClient(api_token=eodhd_api_key)

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
