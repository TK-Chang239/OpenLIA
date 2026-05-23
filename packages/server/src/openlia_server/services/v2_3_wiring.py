"""Startup-time wiring for the v2.3 runner factory.

Reads env vars and, when present, instantiates an OpenAI-backed
`LLMClarifierClient` + the v2.3 runner factory, returning it for the
caller (typically `app.py`) to assign onto `app.state.v2_3_runner_factory`.

Env contract (all required to enable the engine):
- ``OPENAI_API_KEY``                — auth for the OpenAI adapter
- ``OPENLIA_V2_3_CLARIFY_MODEL``    — OpenAI model id, e.g. ``gpt-5.4-mini``

Optional:
- ``OPENAI_BASE_URL``               — override for the OpenAI base URL
- ``OPENLIA_V2_3_CLARIFY_MAX_TOKENS``       — int; default 1024
- ``OPENLIA_V2_3_CLARIFY_TEMPERATURE``      — float; default 0.2

When any required var is missing the function returns ``None`` and the
v2.3 routes respond 503 — same shape as the v2.2 engine.
"""

from __future__ import annotations

import logging
import os

from openlia.llm.adapters import build_adapter
from openlia.llm.runtime.report_v2_3.clients.llm_clarifier import LLMClarifierClient
from openlia.llm.types import Capabilities, ProviderCredentials

from .v2_3_runner_factory import V23RunnerFactory, make_v2_3_runner_factory
from .v2_stage_factory import SyncJsonLlmClient

log = logging.getLogger(__name__)


def build_v2_3_runner_factory_from_env() -> V23RunnerFactory | None:
    """Return a v2.3 factory configured from env, or None if not configured."""
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENLIA_V2_3_CLARIFY_MODEL")
    if not api_key or not model:
        log.info(
            "v2.3 engine env vars not set (OPENAI_API_KEY=%s, "
            "OPENLIA_V2_3_CLARIFY_MODEL=%s); v2.3 routes will respond 503",
            "***" if api_key else "missing",
            "set" if model else "missing",
        )
        return None

    base_url = os.getenv("OPENAI_BASE_URL")
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
        # The CLARIFY prompt is short and the response is small JSON; we do
        # not need long context here.
        capabilities=Capabilities(
            structured_output=True,
            max_context_tokens=128_000,
            max_output_tokens=max_tokens,
        ),
    )
    json_client = SyncJsonLlmClient(
        provider, max_tokens=max_tokens, temperature=temperature
    )
    clarifier = LLMClarifierClient(json_client.call)
    log.info("v2.3 engine wired (clarify model=%s)", model)
    return make_v2_3_runner_factory(clarifier)
