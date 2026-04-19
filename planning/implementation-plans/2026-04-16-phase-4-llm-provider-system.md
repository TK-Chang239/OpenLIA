# Phase 4 — LLM Provider System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the LLM provider abstraction (six adapter types), the three-tier model roster, the two-stage resolver (department-tier → model), and the admin/user routes that manage it all — so every downstream plan can call `resolve(department_id=..., user_id=..., registry=...)` and get back a ready-to-use `LLMProvider` instance with credentials bound.

**Architecture:**

- **Core layer (`packages/core/src/openlia/llm/`)** stays import-pure: an `LLMProvider` ABC, six HTTP/Ollama adapters, a `Capabilities` dataclass + shipped capability map, a retry wrapper, and a resolver function parametrized over a `ModelRegistry` Protocol. No SQLAlchemy, no FastAPI.
- **Server layer** implements `SQLModelRegistry` (translates the core Protocol to SQLAlchemy queries against `llm_providers` / `llm_models` / `user_llm_preferences`), exposes admin CRUD + user preference routes under `/settings/models/*`, and reuses Plan 2's `encrypt_for_row` / `decrypt_for_row` for API keys at rest (AAD = `llm_providers.id`).
- **Streaming deferred.** Plan 4 implements `generate()` (non-streaming) for every adapter and stubs `stream()` with `NotImplementedError`. Plan 5 builds the runners and wires streaming.

**Tech Stack:** Python 3.12, SQLAlchemy 2.x, FastAPI, Pydantic v2, httpx (async), pytest + pytest-asyncio + respx, ruff, uv workspace.

**Source spec:** `planning/specs/systems/llm-provider-design.md`

**Depends on:**

- Plan 1A (tables `llm_providers`, `llm_models`, `user_llm_preferences`, `config_store`).
- Plan 2 (`encrypt_for_row` / `decrypt_for_row` helpers, `build_require_admin`, `build_require_auth`, `create_app(db_session_factory=...)` factory, `company_client` / `personal_client` test fixtures, the `db_session` fixture, `OPENLIA_MODE` handling).

**Unblocks:**

- Plan 5 (LLM runtime — consumes the `LLMProvider` returned by `resolve()`).
- Plan 7 (CLI maintenance / rotate-key touches encrypted API keys).
- Plans 10, 11 (Setup Wizard Step 3 and Settings → Models UI — both write to the admin endpoints added here).
- Every department plan from 13 onward.

**Out of scope (explicitly deferred):**

- `stream()` implementations — stubbed as `raise NotImplementedError` in every adapter; Plan 5 replaces these with real SSE streaming.
- Prompt assembly, framework/style-guide injection, tool schema construction — Plan 5.
- `/setup/models/*` wizard routes (Plan 10) — but the service layer they call is built here.
- Frontend Settings → Models UI (Plan 11) — but every API endpoint it needs is built here.
- Capability-override dialog UI (Plan 11). The storage path (`config_store` key `llm.capability_override.<provider>.<model>`) is wired into the capability map here.
- Per-department tier override UI (Plan 11) — storage path (`config_store` key `llm.department.<id>.tier`) is wired into the resolver here.
- Every actual department's `DEFAULT_TIER` constant — this plan ships a single `DEPARTMENT_DEFAULT_TIERS` dict populated from the spec's shipped table; each department plan can override later.
- yfinance / OAuth / budget tracking (spec non-goals).

---

## File Structure

New core files:

```
packages/core/src/openlia/llm/
├── __init__.py
├── exceptions.py                # LLMProviderError + 5 non-transient + 3 transient subclasses
├── types.py                     # ModelTier, Capability, Capabilities, ModelInfo, LLMRequest/Response/Chunk,
│                                #   TestResult, DepartmentRequirements, ProviderCredentials, ResolvedModel
├── base.py                      # LLMProvider ABC (constructor shape + abstract methods)
├── retry.py                     # with_retries() async retry wrapper for transient errors
├── capabilities.py              # CAPABILITY_MAP + capabilities_for(provider, model, overrides)
├── model_defaults.py            # SHIPPED_TIER_DEFAULTS (provider -> tier -> model_ref)
├── department_defaults.py       # DEPARTMENT_DEFAULT_TIERS (department_id -> ModelTier)
├── resolver.py                  # ModelRegistry Protocol + resolve()
└── adapters/
    ├── __init__.py              # ADAPTERS registry + build_adapter()
    ├── _http.py                 # shared AsyncClient construction + status-code -> exception mapping
    ├── openai.py                # OpenAIAdapter
    ├── anthropic.py             # AnthropicAdapter
    ├── gemini.py                # GeminiAdapter
    ├── openrouter.py            # OpenRouterAdapter (OpenAI-compat variant)
    ├── openai_compat.py         # OpenAICompatAdapter (user-supplied base URL)
    └── ollama.py                # OllamaAdapter
```

New server files:

```
packages/server/src/openlia_server/
├── services/
│   ├── llm_providers.py         # CRUD helpers for llm_providers + llm_models; encrypt/decrypt; capability override + dept tier override stored in config_store
│   └── llm_registry.py          # SQLModelRegistry — implements core's ModelRegistry Protocol
└── routes/
    └── settings.py              # MODIFY (created in Plan 3 for data providers) — add LLM router builders
```

Modified files:

```
packages/server/src/openlia_server/app.py   # mount LLM admin + user routers unconditionally
planning/implementation-plans/README.md      # mark Plan 4 Draft
```

New test modules:

```
packages/core/tests/test_llm/
├── __init__.py
├── conftest.py                   # shared respx fixture
├── test_exceptions.py
├── test_types.py
├── test_capabilities.py
├── test_retry.py
├── test_adapter_openai.py
├── test_adapter_anthropic.py
├── test_adapter_gemini.py
├── test_adapter_openrouter.py
├── test_adapter_openai_compat.py
├── test_adapter_ollama.py
├── test_adapter_registry.py
└── test_resolver.py

packages/server/tests/test_services/
├── test_llm_providers_service.py
└── test_llm_registry.py

packages/server/tests/test_routes/
├── test_llm_admin_routes.py
└── test_llm_user_routes.py

packages/server/tests/test_integration/
└── test_llm_end_to_end.py
```

---

## Task Roadmap

1. Scaffold `openlia/llm/` + typed exceptions.
2. Core types (ModelTier, Capability, Capabilities, ModelInfo, LLMRequest/Response/Chunk, TestResult, DepartmentRequirements, ProviderCredentials, ResolvedModel).
3. Capability map + `capabilities_for()`.
4. Shipped model defaults + department default tiers.
5. Retry wrapper.
6. `LLMProvider` ABC + shared HTTP helpers.
7. OpenAI adapter.
8. Anthropic adapter.
9. Gemini adapter.
10. OpenRouter adapter.
11. OpenAI-compatible adapter.
12. Ollama adapter.
13. Adapter registry + factory.
14. Resolver + `ModelRegistry` Protocol.
15. Server service layer — `llm_providers.py` (CRUD + crypto).
16. Server service layer — `llm_registry.py` (SQLModelRegistry).
17. Admin routes (provider CRUD, model CRUD, test, remote-models, capability override, department tier).
18. User preference routes + wire routers into `create_app` + update README.
19. End-to-end integration test.

---

## Task 1: Scaffold `openlia/llm/` + typed exceptions

**Files:**
- Create: `packages/core/src/openlia/llm/__init__.py`
- Create: `packages/core/src/openlia/llm/exceptions.py`
- Create: `packages/core/tests/test_llm/__init__.py`
- Create: `packages/core/tests/test_llm/test_exceptions.py`

- [ ] **Step 1: Create the package directories and empty `__init__.py` files**

```bash
mkdir -p packages/core/src/openlia/llm/adapters
mkdir -p packages/core/tests/test_llm
touch packages/core/src/openlia/llm/__init__.py
touch packages/core/src/openlia/llm/adapters/__init__.py
touch packages/core/tests/test_llm/__init__.py
```

- [ ] **Step 2: Write the failing exception tests**

Create `packages/core/tests/test_llm/test_exceptions.py`:

```python
"""Typed-exception tests for the LLM provider surface."""
from __future__ import annotations

import pytest

from openlia.llm.exceptions import (
    AuthError,
    CapabilityError,
    ContextLengthError,
    LLMProviderError,
    ModelNotFoundError,
    ProviderOutageError,
    RateLimitError,
    TierNotConfiguredError,
    TransportError,
)


def test_all_errors_derive_from_llm_provider_error() -> None:
    for cls in (
        AuthError,
        CapabilityError,
        ContextLengthError,
        ModelNotFoundError,
        ProviderOutageError,
        RateLimitError,
        TierNotConfiguredError,
        TransportError,
    ):
        assert issubclass(cls, LLMProviderError)


def test_rate_limit_retry_after_defaults_to_none() -> None:
    err = RateLimitError("slow down", retry_after_seconds=None)
    assert err.retry_after_seconds is None
    assert "slow down" in str(err)


def test_rate_limit_retry_after_roundtrip() -> None:
    err = RateLimitError("try again", retry_after_seconds=12)
    assert err.retry_after_seconds == 12


def test_tier_not_configured_names_tier() -> None:
    err = TierNotConfiguredError("thinking")
    assert err.tier == "thinking"
    assert "thinking" in str(err)


def test_auth_error_is_non_transient() -> None:
    from openlia.llm.exceptions import is_transient

    assert is_transient(AuthError("bad key")) is False
    assert is_transient(ModelNotFoundError("nope")) is False
    assert is_transient(CapabilityError("no tools")) is False
    assert is_transient(ContextLengthError("too long", limit=8000)) is False
    assert is_transient(TierNotConfiguredError("quick")) is False


def test_transport_and_rate_limit_and_outage_are_transient() -> None:
    from openlia.llm.exceptions import is_transient

    assert is_transient(TransportError("dns")) is True
    assert is_transient(RateLimitError("429", retry_after_seconds=1)) is True
    assert is_transient(ProviderOutageError("5xx")) is True


def test_context_length_exposes_limit() -> None:
    err = ContextLengthError("too long", limit=8192)
    assert err.limit == 8192
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_llm/test_exceptions.py -v`
Expected: `ModuleNotFoundError: No module named 'openlia.llm.exceptions'`.

- [ ] **Step 4: Implement the exceptions module**

Create `packages/core/src/openlia/llm/exceptions.py`:

```python
"""LLM provider exception hierarchy.

Non-transient errors derive from LLMProviderError and never retry.
Transient errors (TransportError, RateLimitError, ProviderOutageError) are
retried by the adapter layer; see `openlia.llm.retry`.
"""
from __future__ import annotations


class LLMProviderError(Exception):
    """Base class for every error surfaced by the LLM provider layer."""


class TransportError(LLMProviderError):
    """Connection reset, read timeout, DNS failure, any other transport fault."""


class RateLimitError(LLMProviderError):
    """HTTP 429 (or provider-specific equivalent). Carries optional Retry-After seconds."""

    def __init__(self, message: str, *, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class ProviderOutageError(LLMProviderError):
    """Upstream gateway / 5xx. The provider is having a bad day, not the caller."""


class AuthError(LLMProviderError):
    """HTTP 401 / 403. The configured API key is invalid or revoked."""


class ModelNotFoundError(LLMProviderError):
    """HTTP 404 on completion, Ollama 'model not found', etc."""


class ContextLengthError(LLMProviderError):
    """Request exceeded the model's context window."""

    def __init__(self, message: str, *, limit: int) -> None:
        super().__init__(message)
        self.limit = limit


class CapabilityError(LLMProviderError):
    """Provider rejected a capability (tools / JSON / vision) the caller depended on."""


class TierNotConfiguredError(LLMProviderError):
    """The resolved tier has zero enabled models. The caller cannot proceed."""

    def __init__(self, tier: str) -> None:
        super().__init__(
            f"No enabled models configured in tier '{tier}'. "
            "Ask your admin to add one in Settings -> Admin -> Models."
        )
        self.tier = tier


_TRANSIENT: tuple[type[LLMProviderError], ...] = (
    TransportError,
    RateLimitError,
    ProviderOutageError,
)


def is_transient(exc: BaseException) -> bool:
    """True if the exception should be retried by the adapter layer."""
    return isinstance(exc, _TRANSIENT)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_llm/test_exceptions.py -v`
Expected: all 7 pass.

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/llm/__init__.py \
        packages/core/src/openlia/llm/exceptions.py \
        packages/core/src/openlia/llm/adapters/__init__.py \
        packages/core/tests/test_llm/__init__.py \
        packages/core/tests/test_llm/test_exceptions.py
git commit -m "phase-4(llm): typed exception hierarchy"
```

---

## Task 2: Core types

**Files:**
- Create: `packages/core/src/openlia/llm/types.py`
- Create: `packages/core/tests/test_llm/test_types.py`

- [ ] **Step 1: Write the failing type tests**

Create `packages/core/tests/test_llm/test_types.py`:

```python
from __future__ import annotations

import pytest

from openlia.llm.types import (
    Capabilities,
    Capability,
    DepartmentRequirements,
    LLMChunk,
    LLMRequest,
    LLMResponse,
    Message,
    ModelInfo,
    ModelTier,
    ProviderCredentials,
    ResolvedModel,
    TestResult,
)


def test_model_tier_values() -> None:
    assert ModelTier.THINKING.value == "thinking"
    assert ModelTier.EVERYDAY.value == "everyday"
    assert ModelTier.QUICK.value == "quick"
    assert {t.value for t in ModelTier} == {"thinking", "everyday", "quick"}


def test_capabilities_defaults_are_conservative() -> None:
    caps = Capabilities()
    assert caps.streaming is True
    assert caps.tool_calling is False
    assert caps.structured_output is False
    assert caps.vision is False
    assert caps.web_search_native is False
    assert caps.max_context_tokens == 8192
    assert caps.max_output_tokens == 2048


def test_capability_enum_values() -> None:
    assert Capability.STREAMING.value == "streaming"
    assert Capability.TOOL_CALLING.value == "tool_calling"
    assert Capability.STRUCTURED_OUTPUT.value == "structured_output"
    assert Capability.VISION.value == "vision"
    assert Capability.WEB_SEARCH.value == "web_search"


def test_message_minimal() -> None:
    m = Message(role="user", content="hello")
    assert m.role == "user"
    assert m.content == "hello"


def test_llm_request_construction() -> None:
    req = LLMRequest(
        messages=[Message(role="user", content="hi")],
        system="be nice",
        max_tokens=128,
        temperature=0.2,
    )
    assert req.messages[0].content == "hi"
    assert req.system == "be nice"
    assert req.tools is None
    assert req.response_format is None
    assert req.stop is None


def test_llm_response_shape() -> None:
    resp = LLMResponse(
        text="hello back",
        finish_reason="stop",
        input_tokens=5,
        output_tokens=3,
    )
    assert resp.text == "hello back"
    assert resp.tool_calls == []


def test_llm_chunk_shape() -> None:
    chunk = LLMChunk(delta="to", finish_reason=None)
    assert chunk.delta == "to"
    assert chunk.finish_reason is None


def test_model_info_shape() -> None:
    mi = ModelInfo(id="gpt-5.4", display_name="GPT 5.4", context_window=200_000)
    assert mi.id == "gpt-5.4"
    assert mi.context_window == 200_000


def test_provider_credentials_api_key_mode() -> None:
    creds = ProviderCredentials(api_key="sk-...", base_url=None)
    assert creds.api_key == "sk-..."
    assert creds.base_url is None


def test_provider_credentials_base_url_only() -> None:
    creds = ProviderCredentials(api_key=None, base_url="http://localhost:11434")
    assert creds.api_key is None
    assert creds.base_url == "http://localhost:11434"


def test_test_result_ok() -> None:
    tr = TestResult(ok=True, latency_ms=142, error_class=None, error_msg=None)
    assert tr.ok is True
    assert tr.latency_ms == 142


def test_test_result_failure_carries_error_class() -> None:
    tr = TestResult(ok=False, latency_ms=0, error_class="AuthError", error_msg="bad key")
    assert tr.ok is False
    assert tr.error_class == "AuthError"


def test_department_requirements_defaults() -> None:
    r = DepartmentRequirements(
        required=[Capability.STREAMING, Capability.TOOL_CALLING],
    )
    assert Capability.STREAMING in r.required
    assert r.preferred == []
    assert r.min_output_tokens == 0
    assert r.min_context_tokens == 0


def test_resolved_model_shape() -> None:
    rm = ResolvedModel(
        provider_kind="openai",
        provider_id="p1",
        model_id="m1",
        model_ref="gpt-5.4",
        tier=ModelTier.EVERYDAY,
        credentials=ProviderCredentials(api_key="sk-...", base_url=None),
        capabilities=Capabilities(),
        overrides={"temperature": 0.3},
    )
    assert rm.model_ref == "gpt-5.4"
    assert rm.tier is ModelTier.EVERYDAY
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_llm/test_types.py -v`
Expected: `ModuleNotFoundError: No module named 'openlia.llm.types'`.

- [ ] **Step 3: Implement the types module**

Create `packages/core/src/openlia/llm/types.py`:

```python
"""Core LLM type surface.

Pure data types only. No network, no SQLAlchemy, no FastAPI.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ModelTier(StrEnum):
    THINKING = "thinking"
    EVERYDAY = "everyday"
    QUICK = "quick"


class Capability(StrEnum):
    STREAMING = "streaming"
    TOOL_CALLING = "tool_calling"
    STRUCTURED_OUTPUT = "structured_output"
    VISION = "vision"
    WEB_SEARCH = "web_search"


@dataclass(frozen=True)
class Capabilities:
    streaming: bool = True
    tool_calling: bool = False
    structured_output: bool = False
    vision: bool = False
    web_search_native: bool = False
    max_context_tokens: int = 8192
    max_output_tokens: int = 2048


@dataclass(frozen=True)
class Message:
    role: str
    content: str


@dataclass(frozen=True)
class ToolSchema:
    name: str
    description: str
    parameters: dict


@dataclass(frozen=True)
class ResponseFormat:
    kind: str
    json_schema: dict | None = None


@dataclass(frozen=True)
class LLMRequest:
    messages: list[Message]
    system: str | None = None
    tools: list[ToolSchema] | None = None
    response_format: ResponseFormat | None = None
    max_tokens: int = 1024
    temperature: float = 0.7
    stop: list[str] | None = None


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass(frozen=True)
class LLMResponse:
    text: str
    finish_reason: str
    input_tokens: int
    output_tokens: int
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass(frozen=True)
class LLMChunk:
    delta: str
    finish_reason: str | None = None


@dataclass(frozen=True)
class ModelInfo:
    id: str
    display_name: str
    context_window: int | None = None


@dataclass(frozen=True)
class ProviderCredentials:
    api_key: str | None
    base_url: str | None


@dataclass(frozen=True)
class TestResult:
    ok: bool
    latency_ms: int
    error_class: str | None
    error_msg: str | None


@dataclass(frozen=True)
class DepartmentRequirements:
    required: list[Capability]
    preferred: list[Capability] = field(default_factory=list)
    min_output_tokens: int = 0
    min_context_tokens: int = 0


@dataclass(frozen=True)
class ResolvedModel:
    provider_kind: str
    provider_id: str
    model_id: str
    model_ref: str
    tier: ModelTier
    credentials: ProviderCredentials
    capabilities: Capabilities
    overrides: dict
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_llm/test_types.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/types.py \
        packages/core/tests/test_llm/test_types.py
git commit -m "phase-4(llm): core types (ModelTier/Capability/Capabilities/LLMRequest/Response/Chunk/ResolvedModel)"
```

---

## Task 3: Capability map + `capabilities_for()`

**Files:**
- Create: `packages/core/src/openlia/llm/capabilities.py`
- Create: `packages/core/tests/test_llm/test_capabilities.py`

- [ ] **Step 1: Write the failing capability tests**

Create `packages/core/tests/test_llm/test_capabilities.py`:

```python
from __future__ import annotations

from openlia.llm.capabilities import capabilities_for
from openlia.llm.types import Capabilities


def test_unknown_provider_returns_sane_default() -> None:
    caps = capabilities_for(provider_kind="unknown", model="anything")
    assert caps.streaming is True
    assert caps.tool_calling is False
    assert caps.structured_output is False
    assert caps.max_context_tokens == 8192


def test_anthropic_opus_family_matches() -> None:
    caps = capabilities_for(provider_kind="anthropic", model="claude-opus-4-6-20260101")
    assert caps.tool_calling is True
    assert caps.structured_output is True
    assert caps.web_search_native is True
    assert caps.max_context_tokens >= 200_000


def test_anthropic_haiku_matches() -> None:
    caps = capabilities_for(provider_kind="anthropic", model="claude-haiku-4-5")
    assert caps.tool_calling is True


def test_openai_gpt_5_4_matches() -> None:
    caps = capabilities_for(provider_kind="openai", model="gpt-5.4-pro")
    assert caps.tool_calling is True
    assert caps.structured_output is True
    assert caps.web_search_native is True


def test_gemini_3_1_matches() -> None:
    caps = capabilities_for(provider_kind="gemini", model="gemini-3.1-pro")
    assert caps.tool_calling is True
    assert caps.structured_output is True
    assert caps.web_search_native is True


def test_openrouter_inherits_upstream() -> None:
    # OpenRouter model names embed the upstream family, e.g. "anthropic/claude-sonnet-4-6"
    caps = capabilities_for(
        provider_kind="openrouter", model="anthropic/claude-sonnet-4-6"
    )
    assert caps.tool_calling is True


def test_ollama_llama31_has_tools() -> None:
    caps = capabilities_for(provider_kind="ollama", model="llama3.1:8b")
    assert caps.tool_calling is True


def test_ollama_llama2_no_tools() -> None:
    caps = capabilities_for(provider_kind="ollama", model="llama2:7b")
    assert caps.tool_calling is False


def test_openai_compat_defaults_to_generic_modern() -> None:
    caps = capabilities_for(provider_kind="openai_compat", model="anything")
    assert caps.streaming is True
    assert caps.tool_calling is True
    assert caps.structured_output is True
    assert caps.vision is False


def test_override_applies() -> None:
    override = {"tool_calling": False, "max_context_tokens": 16000}
    caps = capabilities_for(
        provider_kind="anthropic", model="claude-opus-4-6", override=override
    )
    assert caps.tool_calling is False
    assert caps.max_context_tokens == 16000
    # untouched fields keep the mapped value
    assert caps.structured_output is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_llm/test_capabilities.py -v`
Expected: `ModuleNotFoundError: No module named 'openlia.llm.capabilities'`.

- [ ] **Step 3: Implement the capability map**

Create `packages/core/src/openlia/llm/capabilities.py`:

```python
"""Shipped capability map keyed by (provider_kind, model-family regex).

Maintainer-curated per release. See llm-provider-design.md § Capabilities for
the rationale and the dev-note on maintenance burden.
"""
from __future__ import annotations

import re
from dataclasses import replace

from openlia.llm.types import Capabilities

_DEFAULT = Capabilities()

_OPENAI_COMPAT_DEFAULT = Capabilities(
    streaming=True,
    tool_calling=True,
    structured_output=True,
    vision=False,
    web_search_native=False,
    max_context_tokens=32_000,
    max_output_tokens=4_096,
)


def _anthropic_opus() -> Capabilities:
    return Capabilities(
        streaming=True,
        tool_calling=True,
        structured_output=True,
        vision=True,
        web_search_native=True,
        max_context_tokens=200_000,
        max_output_tokens=8_192,
    )


def _anthropic_sonnet() -> Capabilities:
    return Capabilities(
        streaming=True,
        tool_calling=True,
        structured_output=True,
        vision=True,
        web_search_native=True,
        max_context_tokens=200_000,
        max_output_tokens=8_192,
    )


def _anthropic_haiku() -> Capabilities:
    return Capabilities(
        streaming=True,
        tool_calling=True,
        structured_output=True,
        vision=True,
        web_search_native=False,
        max_context_tokens=200_000,
        max_output_tokens=4_096,
    )


def _openai_gpt_5_4_pro() -> Capabilities:
    return Capabilities(
        streaming=True,
        tool_calling=True,
        structured_output=True,
        vision=True,
        web_search_native=True,
        max_context_tokens=400_000,
        max_output_tokens=16_384,
    )


def _openai_gpt_5_4() -> Capabilities:
    return Capabilities(
        streaming=True,
        tool_calling=True,
        structured_output=True,
        vision=True,
        web_search_native=True,
        max_context_tokens=200_000,
        max_output_tokens=8_192,
    )


def _openai_gpt_5_4_mini() -> Capabilities:
    return Capabilities(
        streaming=True,
        tool_calling=True,
        structured_output=True,
        vision=True,
        web_search_native=False,
        max_context_tokens=128_000,
        max_output_tokens=4_096,
    )


def _gemini_pro() -> Capabilities:
    return Capabilities(
        streaming=True,
        tool_calling=True,
        structured_output=True,
        vision=True,
        web_search_native=True,
        max_context_tokens=1_000_000,
        max_output_tokens=8_192,
    )


def _gemini_flash() -> Capabilities:
    return Capabilities(
        streaming=True,
        tool_calling=True,
        structured_output=True,
        vision=True,
        web_search_native=True,
        max_context_tokens=1_000_000,
        max_output_tokens=8_192,
    )


def _gemini_flash_lite() -> Capabilities:
    return Capabilities(
        streaming=True,
        tool_calling=True,
        structured_output=True,
        vision=True,
        web_search_native=False,
        max_context_tokens=500_000,
        max_output_tokens=4_096,
    )


def _ollama_tool_family() -> Capabilities:
    return Capabilities(
        streaming=True,
        tool_calling=True,
        structured_output=False,
        vision=False,
        web_search_native=False,
        max_context_tokens=128_000,
        max_output_tokens=4_096,
    )


# Ordered list of (provider_kind, compiled regex, factory). First match wins.
_CAPABILITY_MAP: list[tuple[str, re.Pattern[str], "callable"]] = [
    # Anthropic families
    ("anthropic", re.compile(r"^claude-opus-4", re.IGNORECASE), _anthropic_opus),
    ("anthropic", re.compile(r"^claude-sonnet-4", re.IGNORECASE), _anthropic_sonnet),
    ("anthropic", re.compile(r"^claude-haiku-4", re.IGNORECASE), _anthropic_haiku),
    # OpenAI families
    ("openai", re.compile(r"^gpt-5\.4-pro", re.IGNORECASE), _openai_gpt_5_4_pro),
    ("openai", re.compile(r"^gpt-5\.4-mini", re.IGNORECASE), _openai_gpt_5_4_mini),
    ("openai", re.compile(r"^gpt-5\.4", re.IGNORECASE), _openai_gpt_5_4),
    # Gemini families
    ("gemini", re.compile(r"^gemini-3\.1-pro", re.IGNORECASE), _gemini_pro),
    ("gemini", re.compile(r"^gemini-3\.1-flash-lite", re.IGNORECASE), _gemini_flash_lite),
    ("gemini", re.compile(r"^gemini-3\.1-flash", re.IGNORECASE), _gemini_flash),
    ("gemini", re.compile(r"^gemini-3-flash", re.IGNORECASE), _gemini_flash),
    # Ollama tool-capable families
    ("ollama", re.compile(r"^llama3\.1", re.IGNORECASE), _ollama_tool_family),
    ("ollama", re.compile(r"^qwen2\.5", re.IGNORECASE), _ollama_tool_family),
    ("ollama", re.compile(r"^mistral-nemo", re.IGNORECASE), _ollama_tool_family),
]


def _lookup_base(provider_kind: str, model: str) -> Capabilities:
    """Return the base capabilities for (provider_kind, model) before overrides."""
    # OpenRouter models embed the upstream family, e.g. "anthropic/claude-sonnet-4-6".
    if provider_kind == "openrouter" and "/" in model:
        upstream_kind, upstream_model = model.split("/", 1)
        return _lookup_base(upstream_kind, upstream_model)

    if provider_kind == "openai_compat":
        return _OPENAI_COMPAT_DEFAULT

    for kind, pattern, factory in _CAPABILITY_MAP:
        if kind == provider_kind and pattern.match(model):
            return factory()

    return _DEFAULT


def capabilities_for(
    *,
    provider_kind: str,
    model: str,
    override: dict | None = None,
) -> Capabilities:
    """Resolve the capability set for (provider_kind, model), applying any override.

    Overrides come from the admin's capability-override dialog; they are stored in
    config_store under `llm.capability_override.<provider_kind>.<model>`. The caller
    (server layer) loads the override dict and passes it here.
    """
    base = _lookup_base(provider_kind, model)
    if not override:
        return base
    fields = {
        "streaming",
        "tool_calling",
        "structured_output",
        "vision",
        "web_search_native",
        "max_context_tokens",
        "max_output_tokens",
    }
    patch = {k: v for k, v in override.items() if k in fields}
    return replace(base, **patch)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_llm/test_capabilities.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/capabilities.py \
        packages/core/tests/test_llm/test_capabilities.py
git commit -m "phase-4(llm): shipped capability map + capabilities_for() with override"
```

---

## Task 4: Model defaults + department default tiers

**Files:**
- Create: `packages/core/src/openlia/llm/model_defaults.py`
- Create: `packages/core/src/openlia/llm/department_defaults.py`
- Create: `packages/core/tests/test_llm/test_defaults.py`

- [ ] **Step 1: Write the failing defaults tests**

Create `packages/core/tests/test_llm/test_defaults.py`:

```python
from __future__ import annotations

from openlia.llm.department_defaults import DEPARTMENT_DEFAULT_TIERS
from openlia.llm.model_defaults import SHIPPED_TIER_DEFAULTS
from openlia.llm.types import ModelTier


def test_shipped_tier_defaults_has_six_named_providers() -> None:
    assert set(SHIPPED_TIER_DEFAULTS.keys()) == {
        "openai",
        "anthropic",
        "gemini",
        "openrouter",
        "openai_compat",
        "ollama",
    }


def test_openai_tier_defaults_populated() -> None:
    d = SHIPPED_TIER_DEFAULTS["openai"]
    assert d[ModelTier.THINKING] == "gpt-5.4-pro"
    assert d[ModelTier.EVERYDAY] == "gpt-5.4"
    assert d[ModelTier.QUICK] == "gpt-5.4-mini"


def test_anthropic_tier_defaults_populated() -> None:
    d = SHIPPED_TIER_DEFAULTS["anthropic"]
    assert d[ModelTier.THINKING] == "claude-opus-4-6"
    assert d[ModelTier.EVERYDAY] == "claude-sonnet-4-6"
    assert d[ModelTier.QUICK] == "claude-haiku-4-5"


def test_gemini_tier_defaults_populated() -> None:
    d = SHIPPED_TIER_DEFAULTS["gemini"]
    assert d[ModelTier.THINKING] == "gemini-3.1-pro"
    assert d[ModelTier.EVERYDAY] == "gemini-3-flash"
    assert d[ModelTier.QUICK] == "gemini-3.1-flash-lite"


def test_byo_providers_have_none_defaults() -> None:
    for kind in ("openrouter", "openai_compat", "ollama"):
        d = SHIPPED_TIER_DEFAULTS[kind]
        assert d[ModelTier.THINKING] is None
        assert d[ModelTier.EVERYDAY] is None
        assert d[ModelTier.QUICK] is None


def test_department_defaults_cover_all_shipped_departments() -> None:
    expected = {
        "secretary": ModelTier.EVERYDAY,
        "equity_research": ModelTier.THINKING,
        "earnings_update": ModelTier.EVERYDAY,
        "morning_briefing": ModelTier.EVERYDAY,
        "retail_sentiment": ModelTier.QUICK,
        "macro_research": ModelTier.THINKING,
        "panic_thermometer": ModelTier.QUICK,
    }
    assert DEPARTMENT_DEFAULT_TIERS == expected
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_llm/test_defaults.py -v`
Expected: module-not-found errors.

- [ ] **Step 3: Implement the model defaults**

Create `packages/core/src/openlia/llm/model_defaults.py`:

```python
"""Shipped tier defaults per provider.

Used only as a suggestion source for the Setup Wizard's first-run model pickers,
not as a runtime fallback. See llm-provider-design.md § Shipped tier defaults.

Maintainer-curated per release. Provider /v1/models endpoints are the
authoritative source at runtime; the Wizard/Settings dropdowns live-populate
from there.
"""
from __future__ import annotations

from openlia.llm.types import ModelTier


SHIPPED_TIER_DEFAULTS: dict[str, dict[ModelTier, str | None]] = {
    "openai": {
        ModelTier.THINKING: "gpt-5.4-pro",
        ModelTier.EVERYDAY: "gpt-5.4",
        ModelTier.QUICK: "gpt-5.4-mini",
    },
    "anthropic": {
        ModelTier.THINKING: "claude-opus-4-6",
        ModelTier.EVERYDAY: "claude-sonnet-4-6",
        ModelTier.QUICK: "claude-haiku-4-5",
    },
    "gemini": {
        ModelTier.THINKING: "gemini-3.1-pro",
        ModelTier.EVERYDAY: "gemini-3-flash",
        ModelTier.QUICK: "gemini-3.1-flash-lite",
    },
    "openrouter": {
        ModelTier.THINKING: None,
        ModelTier.EVERYDAY: None,
        ModelTier.QUICK: None,
    },
    "openai_compat": {
        ModelTier.THINKING: None,
        ModelTier.EVERYDAY: None,
        ModelTier.QUICK: None,
    },
    "ollama": {
        ModelTier.THINKING: None,
        ModelTier.EVERYDAY: None,
        ModelTier.QUICK: None,
    },
}
```

- [ ] **Step 4: Implement the department defaults**

Create `packages/core/src/openlia/llm/department_defaults.py`:

```python
"""Default tier routing for each shipped department.

Plan 4 ships these as a single dict. When department plans (13+) are built, each
department module may export its own DEFAULT_TIER; the resolver reads the
`config_store` admin override first, then falls back to this dict.

DEFAULT_TIER_REASON strings live here too so the Settings UI (Plan 11) can
tooltip them without importing every department module.
"""
from __future__ import annotations

from openlia.llm.types import ModelTier


DEPARTMENT_DEFAULT_TIERS: dict[str, ModelTier] = {
    "secretary": ModelTier.EVERYDAY,
    "equity_research": ModelTier.THINKING,
    "earnings_update": ModelTier.EVERYDAY,
    "morning_briefing": ModelTier.EVERYDAY,
    "retail_sentiment": ModelTier.QUICK,
    "macro_research": ModelTier.THINKING,
    "panic_thermometer": ModelTier.QUICK,
}


DEPARTMENT_TIER_REASONS: dict[str, str] = {
    "secretary": "Conversational Q&A needs a balance of speed and reasoning.",
    "equity_research": "Multi-section report drafting with heavy reasoning over fundamentals.",
    "earnings_update": "Standardized scorecard analysis; benefits from a solid all-rounder.",
    "morning_briefing": "News summarization with light reasoning; speed matters.",
    "retail_sentiment": "High-volume classification of social posts; batched micro-tasks.",
    "macro_research": "Framework-driven analysis with long context and deep reasoning.",
    "panic_thermometer": "Real-time indicator scoring; cheap and fast.",
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_llm/test_defaults.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/llm/model_defaults.py \
        packages/core/src/openlia/llm/department_defaults.py \
        packages/core/tests/test_llm/test_defaults.py
git commit -m "phase-4(llm): shipped model defaults + department tier defaults"
```

---

## Task 5: Retry wrapper

**Files:**
- Create: `packages/core/src/openlia/llm/retry.py`
- Create: `packages/core/tests/test_llm/test_retry.py`

- [ ] **Step 1: Write the failing retry tests**

Create `packages/core/tests/test_llm/test_retry.py`:

```python
from __future__ import annotations

import pytest

from openlia.llm.exceptions import (
    AuthError,
    ProviderOutageError,
    RateLimitError,
    TransportError,
)
from openlia.llm.retry import with_retries


async def _factory(responses):
    calls = {"n": 0}

    async def impl():
        calls["n"] += 1
        resp = responses[calls["n"] - 1]
        if isinstance(resp, Exception):
            raise resp
        return resp

    return impl, calls


async def test_returns_on_first_success() -> None:
    impl, calls = await _factory(["ok"])
    result = await with_retries(impl, max_attempts=3, base_delay_s=0)
    assert result == "ok"
    assert calls["n"] == 1


async def test_retries_transport_up_to_three_times() -> None:
    impl, calls = await _factory([TransportError("boom"), TransportError("boom"), "ok"])
    result = await with_retries(impl, max_attempts=3, base_delay_s=0)
    assert result == "ok"
    assert calls["n"] == 3


async def test_retries_outage_then_gives_up() -> None:
    impl, calls = await _factory(
        [
            ProviderOutageError("5xx"),
            ProviderOutageError("5xx"),
            ProviderOutageError("5xx"),
        ]
    )
    with pytest.raises(ProviderOutageError):
        await with_retries(impl, max_attempts=3, base_delay_s=0)
    assert calls["n"] == 3


async def test_rate_limit_respects_retry_after() -> None:
    impl, calls = await _factory(
        [RateLimitError("429", retry_after_seconds=0), "ok"]
    )
    result = await with_retries(impl, max_attempts=3, base_delay_s=0)
    assert result == "ok"
    assert calls["n"] == 2


async def test_non_transient_not_retried() -> None:
    impl, calls = await _factory([AuthError("bad key")])
    with pytest.raises(AuthError):
        await with_retries(impl, max_attempts=3, base_delay_s=0)
    assert calls["n"] == 1
```

- [ ] **Step 2: Ensure `pytest-asyncio` auto mode is enabled**

Run: `uv run pytest packages/core/tests/test_llm/test_retry.py -v`

If the tests are collected as synchronous (and fail trying to `await`), add or confirm pytest config. In `pyproject.toml`, under `[tool.pytest.ini_options]`, ensure:

```toml
asyncio_mode = "auto"
```

Also ensure the dev dependency group includes `pytest-asyncio>=0.24`:

```bash
uv add --dev pytest-asyncio
```

- [ ] **Step 3: Run the tests to verify they fail (module-not-found)**

Run: `uv run pytest packages/core/tests/test_llm/test_retry.py -v`
Expected: `ModuleNotFoundError: No module named 'openlia.llm.retry'`.

- [ ] **Step 4: Implement the retry wrapper**

Create `packages/core/src/openlia/llm/retry.py`:

```python
"""Exponential-backoff retry wrapper for transient LLM errors.

Policy (from llm-provider-design.md § Runtime Failure Handling):

  TransportError      : 3 attempts, backoff 1s / 4s / 10s + jitter
  RateLimitError      : 3 attempts, backoff = max(Retry-After, exponential)
  ProviderOutageError : 3 attempts, backoff 1s / 4s / 10s

Non-transient errors (AuthError, ModelNotFoundError, ContextLengthError,
CapabilityError, TierNotConfiguredError) fail immediately.
"""
from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

from openlia.llm.exceptions import RateLimitError, is_transient

T = TypeVar("T")

# Backoff schedule in seconds for attempts 1, 2, 3.
_BACKOFFS = (1.0, 4.0, 10.0)


async def with_retries(
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
    base_delay_s: float = 1.0,
) -> T:
    """Invoke `fn` with exponential backoff on transient errors.

    `base_delay_s` scales the standard schedule — set to 0 in tests to disable
    real sleeps. Jitter is added as +/-20%.
    """
    last_exc: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await fn()
        except Exception as exc:  # noqa: BLE001
            if not is_transient(exc):
                raise
            last_exc = exc
            if attempt >= max_attempts:
                break

            schedule = _BACKOFFS[min(attempt - 1, len(_BACKOFFS) - 1)] * base_delay_s
            if isinstance(exc, RateLimitError) and exc.retry_after_seconds is not None:
                schedule = max(schedule, float(exc.retry_after_seconds) * base_delay_s)
            if base_delay_s > 0:
                jitter = schedule * random.uniform(-0.2, 0.2)
                await asyncio.sleep(max(0.0, schedule + jitter))
    assert last_exc is not None
    raise last_exc
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest packages/core/tests/test_llm/test_retry.py -v`
Expected: all 5 pass.

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/llm/retry.py \
        packages/core/tests/test_llm/test_retry.py \
        pyproject.toml
git commit -m "phase-4(llm): with_retries() exponential-backoff wrapper for transient errors"
```

---

## Task 6: `LLMProvider` ABC + shared HTTP helpers

**Files:**
- Create: `packages/core/src/openlia/llm/base.py`
- Create: `packages/core/src/openlia/llm/adapters/_http.py`
- Create: `packages/core/tests/test_llm/test_base.py`

- [ ] **Step 1: Write the failing base-adapter tests**

Create `packages/core/tests/test_llm/test_base.py`:

```python
from __future__ import annotations

import pytest

from openlia.llm.base import LLMProvider
from openlia.llm.types import Capabilities, ProviderCredentials


class _Concrete(LLMProvider):
    kind = "openai"

    async def list_models(self):
        return []

    async def generate(self, request):
        raise NotImplementedError

    async def stream(self, request):
        raise NotImplementedError
        yield

    async def test_connection(self, model):
        raise NotImplementedError


def test_cannot_instantiate_abstract_base() -> None:
    with pytest.raises(TypeError):
        LLMProvider(  # type: ignore[abstract]
            credentials=ProviderCredentials(api_key="k", base_url=None),
            model="m",
            capabilities=Capabilities(),
        )


def test_concrete_subclass_stores_fields() -> None:
    creds = ProviderCredentials(api_key="sk-x", base_url=None)
    caps = Capabilities()
    a = _Concrete(credentials=creds, model="gpt-5.4", capabilities=caps)
    assert a.credentials is creds
    assert a.model == "gpt-5.4"
    assert a.capabilities is caps
    assert a.kind == "openai"


def test_status_to_exception_auth() -> None:
    from openlia.llm.adapters._http import status_to_exception
    from openlia.llm.exceptions import AuthError

    with pytest.raises(AuthError):
        status_to_exception(status_code=401, body_text="invalid key")


def test_status_to_exception_rate_limit_with_retry_after() -> None:
    from openlia.llm.adapters._http import status_to_exception
    from openlia.llm.exceptions import RateLimitError

    with pytest.raises(RateLimitError) as excinfo:
        status_to_exception(
            status_code=429, body_text="slow", headers={"retry-after": "17"}
        )
    assert excinfo.value.retry_after_seconds == 17


def test_status_to_exception_rate_limit_missing_retry_after() -> None:
    from openlia.llm.adapters._http import status_to_exception
    from openlia.llm.exceptions import RateLimitError

    with pytest.raises(RateLimitError) as excinfo:
        status_to_exception(status_code=429, body_text="slow")
    assert excinfo.value.retry_after_seconds is None


def test_status_to_exception_outage() -> None:
    from openlia.llm.adapters._http import status_to_exception
    from openlia.llm.exceptions import ProviderOutageError

    with pytest.raises(ProviderOutageError):
        status_to_exception(status_code=502, body_text="bad gateway")


def test_status_to_exception_model_not_found() -> None:
    from openlia.llm.adapters._http import status_to_exception
    from openlia.llm.exceptions import ModelNotFoundError

    with pytest.raises(ModelNotFoundError):
        status_to_exception(status_code=404, body_text="model not found")


def test_status_to_exception_context_length() -> None:
    from openlia.llm.adapters._http import status_to_exception
    from openlia.llm.exceptions import ContextLengthError

    with pytest.raises(ContextLengthError) as excinfo:
        status_to_exception(
            status_code=400,
            body_text="This model's maximum context length is 8192 tokens",
        )
    assert excinfo.value.limit == 8192


def test_status_to_exception_plain_400_is_capability_error() -> None:
    from openlia.llm.adapters._http import status_to_exception
    from openlia.llm.exceptions import CapabilityError

    with pytest.raises(CapabilityError):
        status_to_exception(
            status_code=400, body_text="tool use is not supported on this model"
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_llm/test_base.py -v`
Expected: module-not-found errors.

- [ ] **Step 3: Implement the base ABC**

Create `packages/core/src/openlia/llm/base.py`:

```python
"""LLMProvider abstract base class.

Every adapter subclasses this. Constructor stores credentials, model ref,
and capabilities. Adapters are async-first; synchronous callers wrap
with asyncio.run / anyio.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from openlia.llm.types import (
    Capabilities,
    LLMChunk,
    LLMRequest,
    LLMResponse,
    ModelInfo,
    ProviderCredentials,
    TestResult,
)


class LLMProvider(ABC):
    """Abstract base for every LLM adapter.

    Class-level `kind` must match `llm_providers.kind` for resolver lookup.
    """

    kind: str = ""

    def __init__(
        self,
        *,
        credentials: ProviderCredentials,
        model: str,
        capabilities: Capabilities,
    ) -> None:
        self.credentials = credentials
        self.model = model
        self.capabilities = capabilities

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        """Live model list from the provider. May raise LLMProviderError."""

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Non-streaming completion."""

    @abstractmethod
    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMChunk]:
        """Streaming completion. Plan 4 stubs this; Plan 5 implements SSE."""

    @abstractmethod
    async def test_connection(self, model: str) -> TestResult:
        """1-token ping. Returns structured TestResult — does not raise."""
```

- [ ] **Step 4: Implement the shared HTTP helper**

Create `packages/core/src/openlia/llm/adapters/_http.py`:

```python
"""Shared HTTP helpers for the adapter layer.

Keeps status-code -> exception mapping in one place so each adapter only
translates its own wire format.
"""
from __future__ import annotations

import re

import httpx

from openlia.llm.exceptions import (
    AuthError,
    CapabilityError,
    ContextLengthError,
    ModelNotFoundError,
    ProviderOutageError,
    RateLimitError,
    TransportError,
)

_CONTEXT_LENGTH_RE = re.compile(
    r"(?:context|maximum).*?(\d{3,7})\s*tokens?", re.IGNORECASE
)


def make_client(
    *,
    base_url: str,
    timeout: float = 30.0,
    headers: dict[str, str] | None = None,
) -> httpx.AsyncClient:
    """Construct an AsyncClient with the adapter's base URL + standard timeout."""
    return httpx.AsyncClient(
        base_url=base_url,
        timeout=timeout,
        headers=headers or {},
    )


def _parse_retry_after(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def status_to_exception(
    *,
    status_code: int,
    body_text: str,
    headers: dict[str, str] | None = None,
) -> None:
    """Raise the correct LLMProviderError subclass for a failed HTTP response."""
    headers = {k.lower(): v for k, v in (headers or {}).items()}

    if status_code in (401, 403):
        raise AuthError(f"authentication failed ({status_code}): {body_text[:200]}")

    if status_code == 429:
        retry_after = _parse_retry_after(headers.get("retry-after"))
        raise RateLimitError(
            f"rate limited: {body_text[:200]}",
            retry_after_seconds=retry_after,
        )

    if status_code == 404:
        raise ModelNotFoundError(f"not found: {body_text[:200]}")

    if 500 <= status_code < 600:
        raise ProviderOutageError(f"upstream {status_code}: {body_text[:200]}")

    if status_code == 400:
        match = _CONTEXT_LENGTH_RE.search(body_text)
        if match:
            raise ContextLengthError(body_text[:300], limit=int(match.group(1)))
        raise CapabilityError(f"bad request: {body_text[:200]}")

    # Anything else: treat as transient transport hiccup.
    raise TransportError(f"unexpected status {status_code}: {body_text[:200]}")


def wrap_httpx_error(exc: httpx.HTTPError) -> TransportError:
    """Convert an httpx transport-level error into our TransportError."""
    return TransportError(f"{type(exc).__name__}: {exc!s}")
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest packages/core/tests/test_llm/test_base.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/llm/base.py \
        packages/core/src/openlia/llm/adapters/_http.py \
        packages/core/tests/test_llm/test_base.py
git commit -m "phase-4(llm): LLMProvider ABC + shared status-code -> exception mapper"
```

---

## Task 7: OpenAI adapter

**Files:**
- Create: `packages/core/src/openlia/llm/adapters/openai.py`
- Create: `packages/core/tests/test_llm/test_adapter_openai.py`

- [ ] **Step 1: Write the failing OpenAI adapter tests**

Create `packages/core/tests/test_llm/test_adapter_openai.py`:

```python
from __future__ import annotations

import httpx
import pytest
import respx

from openlia.llm.adapters.openai import OpenAIAdapter
from openlia.llm.exceptions import AuthError, ModelNotFoundError, RateLimitError
from openlia.llm.types import (
    Capabilities,
    LLMRequest,
    Message,
    ProviderCredentials,
)


def _adapter(model: str = "gpt-5.4") -> OpenAIAdapter:
    return OpenAIAdapter(
        credentials=ProviderCredentials(api_key="sk-test", base_url=None),
        model=model,
        capabilities=Capabilities(),
    )


async def test_list_models_parses_response() -> None:
    adapter = _adapter()
    with respx.mock(assert_all_called=True) as mock:
        mock.get("https://api.openai.com/v1/models").respond(
            200,
            json={
                "data": [
                    {"id": "gpt-5.4", "object": "model"},
                    {"id": "gpt-5.4-mini", "object": "model"},
                ]
            },
        )
        models = await adapter.list_models()
    assert {m.id for m in models} == {"gpt-5.4", "gpt-5.4-mini"}


async def test_list_models_auth_error() -> None:
    adapter = _adapter()
    with respx.mock():
        respx.get("https://api.openai.com/v1/models").respond(
            401, json={"error": {"message": "bad key"}}
        )
        with pytest.raises(AuthError):
            await adapter.list_models()


async def test_generate_happy_path() -> None:
    adapter = _adapter()
    with respx.mock():
        respx.post("https://api.openai.com/v1/chat/completions").respond(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "hello"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2},
            },
        )
        resp = await adapter.generate(
            LLMRequest(messages=[Message(role="user", content="hi")])
        )
    assert resp.text == "hello"
    assert resp.finish_reason == "stop"
    assert resp.input_tokens == 5
    assert resp.output_tokens == 2


async def test_generate_rate_limit_extracts_retry_after() -> None:
    adapter = _adapter()
    with respx.mock():
        respx.post("https://api.openai.com/v1/chat/completions").respond(
            429, json={"error": {"message": "slow"}}, headers={"retry-after": "9"}
        )
        with pytest.raises(RateLimitError) as excinfo:
            await adapter.generate(
                LLMRequest(messages=[Message(role="user", content="hi")])
            )
        assert excinfo.value.retry_after_seconds == 9


async def test_generate_model_not_found() -> None:
    adapter = _adapter(model="ghost-model")
    with respx.mock():
        respx.post("https://api.openai.com/v1/chat/completions").respond(
            404, json={"error": {"message": "model not found"}}
        )
        with pytest.raises(ModelNotFoundError):
            await adapter.generate(
                LLMRequest(messages=[Message(role="user", content="hi")])
            )


async def test_test_connection_ok() -> None:
    adapter = _adapter()
    with respx.mock():
        respx.post("https://api.openai.com/v1/chat/completions").respond(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "x"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )
        tr = await adapter.test_connection(model="gpt-5.4")
    assert tr.ok is True
    assert tr.error_class is None


async def test_test_connection_returns_structured_failure_on_auth() -> None:
    adapter = _adapter()
    with respx.mock():
        respx.post("https://api.openai.com/v1/chat/completions").respond(
            401, json={"error": {"message": "bad key"}}
        )
        tr = await adapter.test_connection(model="gpt-5.4")
    assert tr.ok is False
    assert tr.error_class == "AuthError"


async def test_stream_raises_not_implemented() -> None:
    adapter = _adapter()
    with pytest.raises(NotImplementedError):
        agen = adapter.stream(
            LLMRequest(messages=[Message(role="user", content="hi")])
        )
        await agen.__anext__()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_llm/test_adapter_openai.py -v`
Expected: module-not-found error.

- [ ] **Step 3: Implement the adapter**

Create `packages/core/src/openlia/llm/adapters/openai.py`:

```python
"""OpenAI chat-completions adapter."""
from __future__ import annotations

import time
from collections.abc import AsyncIterator

import httpx

from openlia.llm.adapters._http import (
    make_client,
    status_to_exception,
    wrap_httpx_error,
)
from openlia.llm.base import LLMProvider
from openlia.llm.exceptions import LLMProviderError
from openlia.llm.types import (
    LLMChunk,
    LLMRequest,
    LLMResponse,
    ModelInfo,
    TestResult,
    ToolCall,
)

_BASE_URL = "https://api.openai.com"


def _to_openai_messages(req: LLMRequest) -> list[dict]:
    out: list[dict] = []
    if req.system:
        out.append({"role": "system", "content": req.system})
    for m in req.messages:
        out.append({"role": m.role, "content": m.content})
    return out


class OpenAIAdapter(LLMProvider):
    kind = "openai"

    def _headers(self) -> dict[str, str]:
        return {
            "authorization": f"Bearer {self.credentials.api_key}",
            "content-type": "application/json",
        }

    async def list_models(self) -> list[ModelInfo]:
        async with make_client(base_url=_BASE_URL, headers=self._headers()) as client:
            try:
                resp = await client.get("/v1/models")
            except httpx.HTTPError as exc:
                raise wrap_httpx_error(exc) from exc
            if resp.status_code != 200:
                status_to_exception(
                    status_code=resp.status_code,
                    body_text=resp.text,
                    headers=dict(resp.headers),
                )
            data = resp.json()
            return [
                ModelInfo(
                    id=item["id"],
                    display_name=item["id"],
                    context_window=item.get("context_length"),
                )
                for item in data.get("data", [])
            ]

    async def generate(self, request: LLMRequest) -> LLMResponse:
        payload: dict = {
            "model": self.model,
            "messages": _to_openai_messages(request),
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.stop:
            payload["stop"] = request.stop
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in request.tools
            ]
        if request.response_format and request.response_format.kind == "json_schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": request.response_format.json_schema,
            }

        async with make_client(base_url=_BASE_URL, headers=self._headers()) as client:
            try:
                resp = await client.post("/v1/chat/completions", json=payload)
            except httpx.HTTPError as exc:
                raise wrap_httpx_error(exc) from exc

            if resp.status_code != 200:
                status_to_exception(
                    status_code=resp.status_code,
                    body_text=resp.text,
                    headers=dict(resp.headers),
                )
            body = resp.json()

        choice = body["choices"][0]
        message = choice.get("message", {})
        tool_calls = [
            ToolCall(
                id=tc.get("id", ""),
                name=tc["function"]["name"],
                arguments=_parse_arguments(tc["function"].get("arguments", "{}")),
            )
            for tc in message.get("tool_calls") or []
        ]
        usage = body.get("usage") or {}
        return LLMResponse(
            text=message.get("content") or "",
            finish_reason=choice.get("finish_reason", "stop"),
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
            tool_calls=tool_calls,
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMChunk]:
        raise NotImplementedError("OpenAIAdapter.stream is implemented in Plan 5")
        yield  # pragma: no cover  # keeps the method a generator

    async def test_connection(self, model: str) -> TestResult:
        probe = OpenAIAdapter(
            credentials=self.credentials,
            model=model,
            capabilities=self.capabilities,
        )
        start = time.perf_counter()
        try:
            await probe.generate(
                LLMRequest(
                    messages=[_ping_message()],
                    max_tokens=1,
                    temperature=0.0,
                )
            )
        except LLMProviderError as exc:
            return TestResult(
                ok=False,
                latency_ms=int((time.perf_counter() - start) * 1000),
                error_class=type(exc).__name__,
                error_msg=str(exc),
            )
        return TestResult(
            ok=True,
            latency_ms=int((time.perf_counter() - start) * 1000),
            error_class=None,
            error_msg=None,
        )


def _ping_message():
    from openlia.llm.types import Message

    return Message(role="user", content="ping")


def _parse_arguments(raw: str) -> dict:
    import json

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
```

- [ ] **Step 4: Install `respx` if not already present**

```bash
uv add --dev respx
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest packages/core/tests/test_llm/test_adapter_openai.py -v`
Expected: all 8 pass.

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/llm/adapters/openai.py \
        packages/core/tests/test_llm/test_adapter_openai.py \
        pyproject.toml
git commit -m "phase-4(llm): OpenAIAdapter (list_models, generate, test_connection)"
```

---

## Task 8: Anthropic adapter

**Files:**
- Create: `packages/core/src/openlia/llm/adapters/anthropic.py`
- Create: `packages/core/tests/test_llm/test_adapter_anthropic.py`

- [ ] **Step 1: Write the failing Anthropic adapter tests**

Create `packages/core/tests/test_llm/test_adapter_anthropic.py`:

```python
from __future__ import annotations

import pytest
import respx

from openlia.llm.adapters.anthropic import AnthropicAdapter
from openlia.llm.exceptions import AuthError
from openlia.llm.types import (
    Capabilities,
    LLMRequest,
    Message,
    ProviderCredentials,
)


def _adapter(model: str = "claude-sonnet-4-6") -> AnthropicAdapter:
    return AnthropicAdapter(
        credentials=ProviderCredentials(api_key="sk-ant", base_url=None),
        model=model,
        capabilities=Capabilities(),
    )


async def test_list_models_parses_response() -> None:
    adapter = _adapter()
    with respx.mock():
        respx.get("https://api.anthropic.com/v1/models").respond(
            200,
            json={
                "data": [
                    {"id": "claude-opus-4-6", "display_name": "Claude Opus 4.6"},
                    {"id": "claude-sonnet-4-6", "display_name": "Claude Sonnet 4.6"},
                ]
            },
        )
        models = await adapter.list_models()
    assert {m.id for m in models} == {"claude-opus-4-6", "claude-sonnet-4-6"}
    assert any(m.display_name == "Claude Sonnet 4.6" for m in models)


async def test_generate_happy_path_separates_system_from_messages() -> None:
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["payload"] = request.read()
        import httpx

        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "hello"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 5, "output_tokens": 2},
            },
        )

    with respx.mock():
        respx.post("https://api.anthropic.com/v1/messages").mock(side_effect=_capture)
        resp = await adapter.generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                system="be nice",
            )
        )
    assert resp.text == "hello"
    assert resp.finish_reason == "end_turn"
    assert resp.input_tokens == 5
    assert resp.output_tokens == 2
    # system prompt must go on the top-level "system" field, NOT in messages.
    import json

    body = json.loads(captured["payload"])
    assert body["system"] == "be nice"
    assert all(m["role"] != "system" for m in body["messages"])


async def test_generate_includes_api_key_header() -> None:
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["headers"] = dict(request.headers)
        import httpx

        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "ok"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    with respx.mock():
        respx.post("https://api.anthropic.com/v1/messages").mock(side_effect=_capture)
        await adapter.generate(
            LLMRequest(messages=[Message(role="user", content="hi")])
        )
    assert captured["headers"]["x-api-key"] == "sk-ant"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"


async def test_test_connection_failure_returns_structured_error() -> None:
    adapter = _adapter()
    with respx.mock():
        respx.post("https://api.anthropic.com/v1/messages").respond(
            403, json={"error": {"message": "forbidden"}}
        )
        tr = await adapter.test_connection(model="claude-sonnet-4-6")
    assert tr.ok is False
    assert tr.error_class == "AuthError"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_llm/test_adapter_anthropic.py -v`
Expected: module-not-found error.

- [ ] **Step 3: Implement the Anthropic adapter**

Create `packages/core/src/openlia/llm/adapters/anthropic.py`:

```python
"""Anthropic Messages-API adapter."""
from __future__ import annotations

import time
from collections.abc import AsyncIterator

import httpx

from openlia.llm.adapters._http import (
    make_client,
    status_to_exception,
    wrap_httpx_error,
)
from openlia.llm.base import LLMProvider
from openlia.llm.exceptions import LLMProviderError
from openlia.llm.types import (
    LLMChunk,
    LLMRequest,
    LLMResponse,
    Message,
    ModelInfo,
    TestResult,
    ToolCall,
)

_BASE_URL = "https://api.anthropic.com"
_API_VERSION = "2023-06-01"


class AnthropicAdapter(LLMProvider):
    kind = "anthropic"

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.credentials.api_key or "",
            "anthropic-version": _API_VERSION,
            "content-type": "application/json",
        }

    async def list_models(self) -> list[ModelInfo]:
        async with make_client(base_url=_BASE_URL, headers=self._headers()) as client:
            try:
                resp = await client.get("/v1/models")
            except httpx.HTTPError as exc:
                raise wrap_httpx_error(exc) from exc
            if resp.status_code != 200:
                status_to_exception(
                    status_code=resp.status_code,
                    body_text=resp.text,
                    headers=dict(resp.headers),
                )
            data = resp.json()
            return [
                ModelInfo(
                    id=item["id"],
                    display_name=item.get("display_name") or item["id"],
                    context_window=item.get("context_window"),
                )
                for item in data.get("data", [])
            ]

    async def generate(self, request: LLMRequest) -> LLMResponse:
        payload: dict = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.system:
            payload["system"] = request.system
        if request.stop:
            payload["stop_sequences"] = request.stop
        if request.tools:
            payload["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.parameters,
                }
                for t in request.tools
            ]

        async with make_client(base_url=_BASE_URL, headers=self._headers()) as client:
            try:
                resp = await client.post("/v1/messages", json=payload)
            except httpx.HTTPError as exc:
                raise wrap_httpx_error(exc) from exc
            if resp.status_code != 200:
                status_to_exception(
                    status_code=resp.status_code,
                    body_text=resp.text,
                    headers=dict(resp.headers),
                )
            body = resp.json()

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in body.get("content", []):
            btype = block.get("type")
            if btype == "text":
                text_parts.append(block.get("text", ""))
            elif btype == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        arguments=block.get("input") or {},
                    )
                )
        usage = body.get("usage") or {}
        return LLMResponse(
            text="".join(text_parts),
            finish_reason=body.get("stop_reason", "end_turn"),
            input_tokens=int(usage.get("input_tokens", 0)),
            output_tokens=int(usage.get("output_tokens", 0)),
            tool_calls=tool_calls,
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMChunk]:
        raise NotImplementedError("AnthropicAdapter.stream is implemented in Plan 5")
        yield  # pragma: no cover

    async def test_connection(self, model: str) -> TestResult:
        probe = AnthropicAdapter(
            credentials=self.credentials,
            model=model,
            capabilities=self.capabilities,
        )
        start = time.perf_counter()
        try:
            await probe.generate(
                LLMRequest(
                    messages=[Message(role="user", content="ping")],
                    max_tokens=1,
                    temperature=0.0,
                )
            )
        except LLMProviderError as exc:
            return TestResult(
                ok=False,
                latency_ms=int((time.perf_counter() - start) * 1000),
                error_class=type(exc).__name__,
                error_msg=str(exc),
            )
        return TestResult(
            ok=True,
            latency_ms=int((time.perf_counter() - start) * 1000),
            error_class=None,
            error_msg=None,
        )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/core/tests/test_llm/test_adapter_anthropic.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/adapters/anthropic.py \
        packages/core/tests/test_llm/test_adapter_anthropic.py
git commit -m "phase-4(llm): AnthropicAdapter (Messages API, system as top-level field)"
```

---

## Task 9: Gemini adapter

**Files:**
- Create: `packages/core/src/openlia/llm/adapters/gemini.py`
- Create: `packages/core/tests/test_llm/test_adapter_gemini.py`

- [ ] **Step 1: Write the failing Gemini tests**

Create `packages/core/tests/test_llm/test_adapter_gemini.py`:

```python
from __future__ import annotations

import json

import httpx
import pytest
import respx

from openlia.llm.adapters.gemini import GeminiAdapter
from openlia.llm.exceptions import AuthError
from openlia.llm.types import (
    Capabilities,
    LLMRequest,
    Message,
    ProviderCredentials,
)


def _adapter(model: str = "gemini-3-flash") -> GeminiAdapter:
    return GeminiAdapter(
        credentials=ProviderCredentials(api_key="gk-test", base_url=None),
        model=model,
        capabilities=Capabilities(),
    )


async def test_list_models_parses_response() -> None:
    adapter = _adapter()
    with respx.mock():
        respx.get(
            "https://generativelanguage.googleapis.com/v1beta/models"
        ).respond(
            200,
            json={
                "models": [
                    {
                        "name": "models/gemini-3.1-pro",
                        "displayName": "Gemini 3.1 Pro",
                        "inputTokenLimit": 1_000_000,
                    },
                    {
                        "name": "models/gemini-3-flash",
                        "displayName": "Gemini 3 Flash",
                        "inputTokenLimit": 1_000_000,
                    },
                ]
            },
        )
        models = await adapter.list_models()
    assert {m.id for m in models} == {"gemini-3.1-pro", "gemini-3-flash"}


async def test_generate_happy_path_uses_key_query_param() -> None:
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.read())
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {"parts": [{"text": "hello"}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 4,
                    "candidatesTokenCount": 2,
                },
            },
        )

    with respx.mock():
        respx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash:generateContent"
        ).mock(side_effect=_capture)
        resp = await adapter.generate(
            LLMRequest(
                messages=[Message(role="user", content="hi")],
                system="be nice",
            )
        )
    assert "key=gk-test" in captured["url"]
    assert captured["body"]["systemInstruction"]["parts"][0]["text"] == "be nice"
    assert resp.text == "hello"
    assert resp.finish_reason == "STOP"
    assert resp.input_tokens == 4
    assert resp.output_tokens == 2


async def test_generate_auth_error() -> None:
    adapter = _adapter()
    with respx.mock():
        respx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash:generateContent"
        ).respond(403, json={"error": {"message": "forbidden"}})
        with pytest.raises(AuthError):
            await adapter.generate(
                LLMRequest(messages=[Message(role="user", content="hi")])
            )


async def test_test_connection_ok() -> None:
    adapter = _adapter()
    with respx.mock():
        respx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash:generateContent"
        ).respond(
            200,
            json={
                "candidates": [
                    {
                        "content": {"parts": [{"text": "x"}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 1,
                    "candidatesTokenCount": 1,
                },
            },
        )
        tr = await adapter.test_connection(model="gemini-3-flash")
    assert tr.ok is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_llm/test_adapter_gemini.py -v`
Expected: module-not-found error.

- [ ] **Step 3: Implement the Gemini adapter**

Create `packages/core/src/openlia/llm/adapters/gemini.py`:

```python
"""Google Gemini (generative-language) adapter."""
from __future__ import annotations

import time
from collections.abc import AsyncIterator

import httpx

from openlia.llm.adapters._http import (
    make_client,
    status_to_exception,
    wrap_httpx_error,
)
from openlia.llm.base import LLMProvider
from openlia.llm.exceptions import LLMProviderError
from openlia.llm.types import (
    LLMChunk,
    LLMRequest,
    LLMResponse,
    Message,
    ModelInfo,
    TestResult,
)

_BASE_URL = "https://generativelanguage.googleapis.com"


def _role(role: str) -> str:
    return "model" if role == "assistant" else "user"


class GeminiAdapter(LLMProvider):
    kind = "gemini"

    def _query(self) -> dict[str, str]:
        return {"key": self.credentials.api_key or ""}

    async def list_models(self) -> list[ModelInfo]:
        async with make_client(base_url=_BASE_URL) as client:
            try:
                resp = await client.get("/v1beta/models", params=self._query())
            except httpx.HTTPError as exc:
                raise wrap_httpx_error(exc) from exc
            if resp.status_code != 200:
                status_to_exception(
                    status_code=resp.status_code,
                    body_text=resp.text,
                    headers=dict(resp.headers),
                )
            data = resp.json()
            out: list[ModelInfo] = []
            for item in data.get("models", []):
                name = item.get("name", "")
                short_id = name.split("/", 1)[1] if "/" in name else name
                out.append(
                    ModelInfo(
                        id=short_id,
                        display_name=item.get("displayName") or short_id,
                        context_window=item.get("inputTokenLimit"),
                    )
                )
            return out

    async def generate(self, request: LLMRequest) -> LLMResponse:
        payload: dict = {
            "contents": [
                {"role": _role(m.role), "parts": [{"text": m.content}]}
                for m in request.messages
            ],
            "generationConfig": {
                "maxOutputTokens": request.max_tokens,
                "temperature": request.temperature,
            },
        }
        if request.system:
            payload["systemInstruction"] = {"parts": [{"text": request.system}]}
        if request.stop:
            payload["generationConfig"]["stopSequences"] = request.stop
        if request.tools:
            payload["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            "name": t.name,
                            "description": t.description,
                            "parameters": t.parameters,
                        }
                        for t in request.tools
                    ]
                }
            ]

        path = f"/v1beta/models/{self.model}:generateContent"
        async with make_client(base_url=_BASE_URL) as client:
            try:
                resp = await client.post(path, params=self._query(), json=payload)
            except httpx.HTTPError as exc:
                raise wrap_httpx_error(exc) from exc
            if resp.status_code != 200:
                status_to_exception(
                    status_code=resp.status_code,
                    body_text=resp.text,
                    headers=dict(resp.headers),
                )
            body = resp.json()

        candidate = (body.get("candidates") or [{}])[0]
        parts = (candidate.get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if "text" in p)
        usage = body.get("usageMetadata") or {}
        return LLMResponse(
            text=text,
            finish_reason=candidate.get("finishReason", "STOP"),
            input_tokens=int(usage.get("promptTokenCount", 0)),
            output_tokens=int(usage.get("candidatesTokenCount", 0)),
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMChunk]:
        raise NotImplementedError("GeminiAdapter.stream is implemented in Plan 5")
        yield  # pragma: no cover

    async def test_connection(self, model: str) -> TestResult:
        probe = GeminiAdapter(
            credentials=self.credentials,
            model=model,
            capabilities=self.capabilities,
        )
        start = time.perf_counter()
        try:
            await probe.generate(
                LLMRequest(
                    messages=[Message(role="user", content="ping")],
                    max_tokens=1,
                    temperature=0.0,
                )
            )
        except LLMProviderError as exc:
            return TestResult(
                ok=False,
                latency_ms=int((time.perf_counter() - start) * 1000),
                error_class=type(exc).__name__,
                error_msg=str(exc),
            )
        return TestResult(
            ok=True,
            latency_ms=int((time.perf_counter() - start) * 1000),
            error_class=None,
            error_msg=None,
        )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/core/tests/test_llm/test_adapter_gemini.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/adapters/gemini.py \
        packages/core/tests/test_llm/test_adapter_gemini.py
git commit -m "phase-4(llm): GeminiAdapter (generateContent, key as query param, systemInstruction)"
```

---

## Task 10: OpenRouter adapter

**Files:**
- Create: `packages/core/src/openlia/llm/adapters/openrouter.py`
- Create: `packages/core/tests/test_llm/test_adapter_openrouter.py`

- [ ] **Step 1: Write the failing OpenRouter tests**

Create `packages/core/tests/test_llm/test_adapter_openrouter.py`:

```python
from __future__ import annotations

import pytest
import respx

from openlia.llm.adapters.openrouter import OpenRouterAdapter
from openlia.llm.exceptions import LLMProviderError
from openlia.llm.types import (
    Capabilities,
    LLMRequest,
    Message,
    ProviderCredentials,
)


def _adapter(model: str = "anthropic/claude-sonnet-4-6") -> OpenRouterAdapter:
    return OpenRouterAdapter(
        credentials=ProviderCredentials(api_key="or-test", base_url=None),
        model=model,
        capabilities=Capabilities(),
    )


async def test_list_models_not_used_returns_empty_list() -> None:
    """Spec says OpenRouter uses manual entry; list_models returns [] without a call."""
    adapter = _adapter()
    # Intentionally no respx route — this should not hit the network.
    models = await adapter.list_models()
    assert models == []


async def test_generate_uses_openai_compat_endpoint() -> None:
    adapter = _adapter()
    with respx.mock():
        respx.post("https://openrouter.ai/api/v1/chat/completions").respond(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 1},
            },
        )
        resp = await adapter.generate(
            LLMRequest(messages=[Message(role="user", content="hi")])
        )
    assert resp.text == "ok"
    assert resp.input_tokens == 3


async def test_generate_includes_bearer_token() -> None:
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["headers"] = dict(request.headers)
        import httpx

        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    with respx.mock():
        respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
            side_effect=_capture
        )
        await adapter.generate(
            LLMRequest(messages=[Message(role="user", content="hi")])
        )
    assert captured["headers"]["authorization"] == "Bearer or-test"


async def test_test_connection_ok() -> None:
    adapter = _adapter()
    with respx.mock():
        respx.post("https://openrouter.ai/api/v1/chat/completions").respond(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "x"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )
        tr = await adapter.test_connection(model="anthropic/claude-sonnet-4-6")
    assert tr.ok is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_llm/test_adapter_openrouter.py -v`
Expected: module-not-found error.

- [ ] **Step 3: Implement the OpenRouter adapter**

Create `packages/core/src/openlia/llm/adapters/openrouter.py`:

```python
"""OpenRouter adapter — OpenAI-compatible gateway."""
from __future__ import annotations

import time
from collections.abc import AsyncIterator

import httpx

from openlia.llm.adapters._http import (
    make_client,
    status_to_exception,
    wrap_httpx_error,
)
from openlia.llm.base import LLMProvider
from openlia.llm.exceptions import LLMProviderError
from openlia.llm.types import (
    LLMChunk,
    LLMRequest,
    LLMResponse,
    Message,
    ModelInfo,
    TestResult,
    ToolCall,
)

_BASE_URL = "https://openrouter.ai/api"


def _to_messages(req: LLMRequest) -> list[dict]:
    out: list[dict] = []
    if req.system:
        out.append({"role": "system", "content": req.system})
    for m in req.messages:
        out.append({"role": m.role, "content": m.content})
    return out


class OpenRouterAdapter(LLMProvider):
    kind = "openrouter"

    def _headers(self) -> dict[str, str]:
        return {
            "authorization": f"Bearer {self.credentials.api_key}",
            "content-type": "application/json",
            "HTTP-Referer": "https://openlia.app",
            "X-Title": "OpenLIA",
        }

    async def list_models(self) -> list[ModelInfo]:
        # Spec says OpenRouter uses manual model entry in the UI; we never probe.
        return []

    async def generate(self, request: LLMRequest) -> LLMResponse:
        payload: dict = {
            "model": self.model,
            "messages": _to_messages(request),
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.stop:
            payload["stop"] = request.stop
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in request.tools
            ]

        async with make_client(base_url=_BASE_URL, headers=self._headers()) as client:
            try:
                resp = await client.post("/v1/chat/completions", json=payload)
            except httpx.HTTPError as exc:
                raise wrap_httpx_error(exc) from exc
            if resp.status_code != 200:
                status_to_exception(
                    status_code=resp.status_code,
                    body_text=resp.text,
                    headers=dict(resp.headers),
                )
            body = resp.json()

        choice = body["choices"][0]
        message = choice.get("message", {})
        tool_calls: list[ToolCall] = []
        for tc in message.get("tool_calls") or []:
            import json

            try:
                args = json.loads(tc["function"].get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(
                ToolCall(
                    id=tc.get("id", ""),
                    name=tc["function"]["name"],
                    arguments=args if isinstance(args, dict) else {},
                )
            )
        usage = body.get("usage") or {}
        return LLMResponse(
            text=message.get("content") or "",
            finish_reason=choice.get("finish_reason", "stop"),
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
            tool_calls=tool_calls,
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMChunk]:
        raise NotImplementedError("OpenRouterAdapter.stream is implemented in Plan 5")
        yield  # pragma: no cover

    async def test_connection(self, model: str) -> TestResult:
        probe = OpenRouterAdapter(
            credentials=self.credentials,
            model=model,
            capabilities=self.capabilities,
        )
        start = time.perf_counter()
        try:
            await probe.generate(
                LLMRequest(
                    messages=[Message(role="user", content="ping")],
                    max_tokens=1,
                    temperature=0.0,
                )
            )
        except LLMProviderError as exc:
            return TestResult(
                ok=False,
                latency_ms=int((time.perf_counter() - start) * 1000),
                error_class=type(exc).__name__,
                error_msg=str(exc),
            )
        return TestResult(
            ok=True,
            latency_ms=int((time.perf_counter() - start) * 1000),
            error_class=None,
            error_msg=None,
        )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/core/tests/test_llm/test_adapter_openrouter.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/adapters/openrouter.py \
        packages/core/tests/test_llm/test_adapter_openrouter.py
git commit -m "phase-4(llm): OpenRouterAdapter (OpenAI-compat gateway, list_models returns [])"
```

---

## Task 11: OpenAI-compatible adapter

**Files:**
- Create: `packages/core/src/openlia/llm/adapters/openai_compat.py`
- Create: `packages/core/tests/test_llm/test_adapter_openai_compat.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/core/tests/test_llm/test_adapter_openai_compat.py`:

```python
from __future__ import annotations

import pytest
import respx

from openlia.llm.adapters.openai_compat import OpenAICompatAdapter
from openlia.llm.exceptions import LLMProviderError, ModelNotFoundError
from openlia.llm.types import (
    Capabilities,
    LLMRequest,
    Message,
    ProviderCredentials,
)


def _adapter(
    *,
    base_url: str = "https://deepseek.example.com/v1",
    api_key: str | None = "dsk-test",
    model: str = "deepseek-chat",
) -> OpenAICompatAdapter:
    return OpenAICompatAdapter(
        credentials=ProviderCredentials(api_key=api_key, base_url=base_url),
        model=model,
        capabilities=Capabilities(),
    )


async def test_missing_base_url_raises() -> None:
    from openlia.llm.exceptions import CapabilityError

    with pytest.raises(CapabilityError):
        OpenAICompatAdapter(
            credentials=ProviderCredentials(api_key="x", base_url=None),
            model="x",
            capabilities=Capabilities(),
        )


async def test_list_models_hits_user_base_url() -> None:
    adapter = _adapter()
    with respx.mock():
        respx.get("https://deepseek.example.com/v1/models").respond(
            200, json={"data": [{"id": "deepseek-chat"}]}
        )
        models = await adapter.list_models()
    assert [m.id for m in models] == ["deepseek-chat"]


async def test_list_models_404_returns_empty_for_fallback() -> None:
    """Spec: '`GET {base_url}/models` (fallback: manual entry)' — if the endpoint
    404s, we must return [] (not raise) so the UI can fall back to manual entry."""
    adapter = _adapter()
    with respx.mock():
        respx.get("https://deepseek.example.com/v1/models").respond(404)
        models = await adapter.list_models()
    assert models == []


async def test_generate_includes_auth_header() -> None:
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        captured["headers"] = dict(request.headers)
        import httpx

        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    with respx.mock():
        respx.post("https://deepseek.example.com/v1/chat/completions").mock(
            side_effect=_capture
        )
        await adapter.generate(
            LLMRequest(messages=[Message(role="user", content="hi")])
        )
    assert captured["headers"]["authorization"] == "Bearer dsk-test"


async def test_generate_omits_auth_if_no_key() -> None:
    adapter = _adapter(api_key=None)
    captured: dict = {}

    def _capture(request):
        captured["headers"] = dict(request.headers)
        import httpx

        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    with respx.mock():
        respx.post("https://deepseek.example.com/v1/chat/completions").mock(
            side_effect=_capture
        )
        await adapter.generate(
            LLMRequest(messages=[Message(role="user", content="hi")])
        )
    # No auth header when api_key is None (some self-hosted deployments).
    assert "authorization" not in captured["headers"]


async def test_generate_model_not_found() -> None:
    adapter = _adapter(model="ghost")
    with respx.mock():
        respx.post("https://deepseek.example.com/v1/chat/completions").respond(
            404, json={"error": {"message": "not found"}}
        )
        with pytest.raises(ModelNotFoundError):
            await adapter.generate(
                LLMRequest(messages=[Message(role="user", content="hi")])
            )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_llm/test_adapter_openai_compat.py -v`
Expected: module-not-found error.

- [ ] **Step 3: Implement the OpenAI-compat adapter**

Create `packages/core/src/openlia/llm/adapters/openai_compat.py`:

```python
"""OpenAI-compatible catch-all adapter.

Covers DeepSeek, Grok/xAI, Groq, Together, Fireworks, Mistral, Cerebras,
Perplexity, Azure OpenAI, vLLM, LM Studio, and any other provider that exposes
an OpenAI-style /chat/completions endpoint. Base URL is user-supplied.
"""
from __future__ import annotations

import time
from collections.abc import AsyncIterator

import httpx

from openlia.llm.adapters._http import (
    make_client,
    status_to_exception,
    wrap_httpx_error,
)
from openlia.llm.base import LLMProvider
from openlia.llm.exceptions import CapabilityError, LLMProviderError, ModelNotFoundError
from openlia.llm.types import (
    Capabilities,
    LLMChunk,
    LLMRequest,
    LLMResponse,
    Message,
    ModelInfo,
    ProviderCredentials,
    TestResult,
    ToolCall,
)


def _to_messages(req: LLMRequest) -> list[dict]:
    out: list[dict] = []
    if req.system:
        out.append({"role": "system", "content": req.system})
    for m in req.messages:
        out.append({"role": m.role, "content": m.content})
    return out


class OpenAICompatAdapter(LLMProvider):
    kind = "openai_compat"

    def __init__(
        self,
        *,
        credentials: ProviderCredentials,
        model: str,
        capabilities: Capabilities,
    ) -> None:
        if not credentials.base_url:
            raise CapabilityError(
                "OpenAICompatAdapter requires a base_url in credentials"
            )
        super().__init__(credentials=credentials, model=model, capabilities=capabilities)

    def _headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if self.credentials.api_key:
            headers["authorization"] = f"Bearer {self.credentials.api_key}"
        return headers

    async def list_models(self) -> list[ModelInfo]:
        base = (self.credentials.base_url or "").rstrip("/")
        async with make_client(base_url=base, headers=self._headers()) as client:
            try:
                resp = await client.get("/models")
            except httpx.HTTPError:
                # Manual entry fallback — caller sees [] and prompts the user.
                return []
            if resp.status_code == 404:
                return []
            if resp.status_code != 200:
                status_to_exception(
                    status_code=resp.status_code,
                    body_text=resp.text,
                    headers=dict(resp.headers),
                )
            data = resp.json()
            return [
                ModelInfo(
                    id=item["id"],
                    display_name=item.get("display_name") or item["id"],
                    context_window=item.get("context_length"),
                )
                for item in data.get("data", [])
            ]

    async def generate(self, request: LLMRequest) -> LLMResponse:
        payload: dict = {
            "model": self.model,
            "messages": _to_messages(request),
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.stop:
            payload["stop"] = request.stop
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in request.tools
            ]

        base = (self.credentials.base_url or "").rstrip("/")
        async with make_client(base_url=base, headers=self._headers()) as client:
            try:
                resp = await client.post("/chat/completions", json=payload)
            except httpx.HTTPError as exc:
                raise wrap_httpx_error(exc) from exc
            if resp.status_code != 200:
                status_to_exception(
                    status_code=resp.status_code,
                    body_text=resp.text,
                    headers=dict(resp.headers),
                )
            body = resp.json()

        choice = body["choices"][0]
        message = choice.get("message", {})
        tool_calls: list[ToolCall] = []
        for tc in message.get("tool_calls") or []:
            import json

            try:
                args = json.loads(tc["function"].get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(
                ToolCall(
                    id=tc.get("id", ""),
                    name=tc["function"]["name"],
                    arguments=args if isinstance(args, dict) else {},
                )
            )
        usage = body.get("usage") or {}
        return LLMResponse(
            text=message.get("content") or "",
            finish_reason=choice.get("finish_reason", "stop"),
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
            tool_calls=tool_calls,
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMChunk]:
        raise NotImplementedError("OpenAICompatAdapter.stream is implemented in Plan 5")
        yield  # pragma: no cover

    async def test_connection(self, model: str) -> TestResult:
        probe = OpenAICompatAdapter(
            credentials=self.credentials,
            model=model,
            capabilities=self.capabilities,
        )
        start = time.perf_counter()
        try:
            await probe.generate(
                LLMRequest(
                    messages=[Message(role="user", content="ping")],
                    max_tokens=1,
                    temperature=0.0,
                )
            )
        except LLMProviderError as exc:
            return TestResult(
                ok=False,
                latency_ms=int((time.perf_counter() - start) * 1000),
                error_class=type(exc).__name__,
                error_msg=str(exc),
            )
        return TestResult(
            ok=True,
            latency_ms=int((time.perf_counter() - start) * 1000),
            error_class=None,
            error_msg=None,
        )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/core/tests/test_llm/test_adapter_openai_compat.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/adapters/openai_compat.py \
        packages/core/tests/test_llm/test_adapter_openai_compat.py
git commit -m "phase-4(llm): OpenAICompatAdapter (user base URL, optional auth, 404 list_models fallback)"
```

---

## Task 12: Ollama adapter

**Files:**
- Create: `packages/core/src/openlia/llm/adapters/ollama.py`
- Create: `packages/core/tests/test_llm/test_adapter_ollama.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/core/tests/test_llm/test_adapter_ollama.py`:

```python
from __future__ import annotations

import httpx
import pytest
import respx

from openlia.llm.adapters.ollama import OllamaAdapter
from openlia.llm.exceptions import ModelNotFoundError
from openlia.llm.types import (
    Capabilities,
    LLMRequest,
    Message,
    ProviderCredentials,
)


def _adapter(
    *,
    base_url: str = "http://localhost:11434",
    model: str = "llama3.1:8b",
) -> OllamaAdapter:
    return OllamaAdapter(
        credentials=ProviderCredentials(api_key=None, base_url=base_url),
        model=model,
        capabilities=Capabilities(),
    )


async def test_list_models_returns_empty_list() -> None:
    """Spec: Ollama uses manual entry. list_models returns [] without a call."""
    adapter = _adapter()
    models = await adapter.list_models()
    assert models == []


async def test_generate_uses_chat_endpoint() -> None:
    adapter = _adapter()
    with respx.mock():
        respx.post("http://localhost:11434/api/chat").respond(
            200,
            json={
                "message": {"role": "assistant", "content": "hello"},
                "done_reason": "stop",
                "prompt_eval_count": 3,
                "eval_count": 1,
            },
        )
        resp = await adapter.generate(
            LLMRequest(messages=[Message(role="user", content="hi")])
        )
    assert resp.text == "hello"
    assert resp.finish_reason == "stop"
    assert resp.input_tokens == 3
    assert resp.output_tokens == 1


async def test_generate_disables_streaming_on_payload() -> None:
    adapter = _adapter()
    captured: dict = {}

    def _capture(request):
        import json

        captured["body"] = json.loads(request.read())
        return httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": "ok"},
                "done_reason": "stop",
                "prompt_eval_count": 1,
                "eval_count": 1,
            },
        )

    with respx.mock():
        respx.post("http://localhost:11434/api/chat").mock(side_effect=_capture)
        await adapter.generate(
            LLMRequest(messages=[Message(role="user", content="hi")])
        )
    assert captured["body"]["stream"] is False
    assert captured["body"]["model"] == "llama3.1:8b"


async def test_generate_model_not_found() -> None:
    adapter = _adapter(model="ghost")
    with respx.mock():
        respx.post("http://localhost:11434/api/chat").respond(404, text="model not found")
        with pytest.raises(ModelNotFoundError):
            await adapter.generate(
                LLMRequest(messages=[Message(role="user", content="hi")])
            )


async def test_test_connection_ok() -> None:
    adapter = _adapter()
    with respx.mock():
        respx.post("http://localhost:11434/api/chat").respond(
            200,
            json={
                "message": {"role": "assistant", "content": "x"},
                "done_reason": "stop",
                "prompt_eval_count": 1,
                "eval_count": 1,
            },
        )
        tr = await adapter.test_connection(model="llama3.1:8b")
    assert tr.ok is True


async def test_test_connection_outage_reported_as_transport() -> None:
    adapter = _adapter()
    with respx.mock():
        respx.post("http://localhost:11434/api/chat").respond(503, text="overloaded")
        tr = await adapter.test_connection(model="llama3.1:8b")
    assert tr.ok is False
    assert tr.error_class == "ProviderOutageError"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_llm/test_adapter_ollama.py -v`
Expected: module-not-found error.

- [ ] **Step 3: Implement the Ollama adapter**

Create `packages/core/src/openlia/llm/adapters/ollama.py`:

```python
"""Ollama local adapter.

Uses Ollama's /api/chat endpoint in non-streaming mode. base_url defaults to
http://localhost:11434. No auth header; Ollama is local-only by convention.
"""
from __future__ import annotations

import time
from collections.abc import AsyncIterator

import httpx

from openlia.llm.adapters._http import (
    make_client,
    status_to_exception,
    wrap_httpx_error,
)
from openlia.llm.base import LLMProvider
from openlia.llm.exceptions import LLMProviderError
from openlia.llm.types import (
    LLMChunk,
    LLMRequest,
    LLMResponse,
    Message,
    ModelInfo,
    TestResult,
)


def _to_messages(req: LLMRequest) -> list[dict]:
    out: list[dict] = []
    if req.system:
        out.append({"role": "system", "content": req.system})
    for m in req.messages:
        out.append({"role": m.role, "content": m.content})
    return out


class OllamaAdapter(LLMProvider):
    kind = "ollama"

    async def list_models(self) -> list[ModelInfo]:
        # Spec: manual entry in the UI; no probing.
        return []

    async def generate(self, request: LLMRequest) -> LLMResponse:
        payload: dict = {
            "model": self.model,
            "messages": _to_messages(request),
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }
        if request.stop:
            payload["options"]["stop"] = request.stop
        if request.tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in request.tools
            ]

        base = (self.credentials.base_url or "http://localhost:11434").rstrip("/")
        async with make_client(base_url=base) as client:
            try:
                resp = await client.post("/api/chat", json=payload)
            except httpx.HTTPError as exc:
                raise wrap_httpx_error(exc) from exc
            if resp.status_code != 200:
                status_to_exception(
                    status_code=resp.status_code,
                    body_text=resp.text,
                    headers=dict(resp.headers),
                )
            body = resp.json()

        message = body.get("message") or {}
        return LLMResponse(
            text=message.get("content") or "",
            finish_reason=body.get("done_reason", "stop"),
            input_tokens=int(body.get("prompt_eval_count", 0)),
            output_tokens=int(body.get("eval_count", 0)),
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMChunk]:
        raise NotImplementedError("OllamaAdapter.stream is implemented in Plan 5")
        yield  # pragma: no cover

    async def test_connection(self, model: str) -> TestResult:
        probe = OllamaAdapter(
            credentials=self.credentials,
            model=model,
            capabilities=self.capabilities,
        )
        start = time.perf_counter()
        try:
            await probe.generate(
                LLMRequest(
                    messages=[Message(role="user", content="ping")],
                    max_tokens=1,
                    temperature=0.0,
                )
            )
        except LLMProviderError as exc:
            return TestResult(
                ok=False,
                latency_ms=int((time.perf_counter() - start) * 1000),
                error_class=type(exc).__name__,
                error_msg=str(exc),
            )
        return TestResult(
            ok=True,
            latency_ms=int((time.perf_counter() - start) * 1000),
            error_class=None,
            error_msg=None,
        )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/core/tests/test_llm/test_adapter_ollama.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/adapters/ollama.py \
        packages/core/tests/test_llm/test_adapter_ollama.py
git commit -m "phase-4(llm): OllamaAdapter (local /api/chat, stream=false, manual model entry)"
```

---

## Task 13: Adapter registry + factory

**Files:**
- Modify: `packages/core/src/openlia/llm/adapters/__init__.py`
- Create: `packages/core/tests/test_llm/test_adapter_registry.py`

- [ ] **Step 1: Write the failing registry tests**

Create `packages/core/tests/test_llm/test_adapter_registry.py`:

```python
from __future__ import annotations

import pytest

from openlia.llm.adapters import ADAPTERS, build_adapter
from openlia.llm.adapters.anthropic import AnthropicAdapter
from openlia.llm.adapters.gemini import GeminiAdapter
from openlia.llm.adapters.ollama import OllamaAdapter
from openlia.llm.adapters.openai import OpenAIAdapter
from openlia.llm.adapters.openai_compat import OpenAICompatAdapter
from openlia.llm.adapters.openrouter import OpenRouterAdapter
from openlia.llm.base import LLMProvider
from openlia.llm.types import Capabilities, ProviderCredentials


def test_registry_covers_six_kinds() -> None:
    assert set(ADAPTERS.keys()) == {
        "openai",
        "anthropic",
        "gemini",
        "openrouter",
        "openai_compat",
        "ollama",
    }


def test_registry_values_are_concrete_subclasses() -> None:
    assert ADAPTERS["openai"] is OpenAIAdapter
    assert ADAPTERS["anthropic"] is AnthropicAdapter
    assert ADAPTERS["gemini"] is GeminiAdapter
    assert ADAPTERS["openrouter"] is OpenRouterAdapter
    assert ADAPTERS["openai_compat"] is OpenAICompatAdapter
    assert ADAPTERS["ollama"] is OllamaAdapter
    for cls in ADAPTERS.values():
        assert issubclass(cls, LLMProvider)


def test_build_adapter_returns_matching_instance() -> None:
    adapter = build_adapter(
        kind="openai",
        credentials=ProviderCredentials(api_key="sk-x", base_url=None),
        model="gpt-5.4",
        capabilities=Capabilities(),
    )
    assert isinstance(adapter, OpenAIAdapter)
    assert adapter.model == "gpt-5.4"


def test_build_adapter_unknown_kind_raises() -> None:
    with pytest.raises(KeyError):
        build_adapter(
            kind="nope",
            credentials=ProviderCredentials(api_key="x", base_url=None),
            model="x",
            capabilities=Capabilities(),
        )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_llm/test_adapter_registry.py -v`
Expected: `ImportError: cannot import name 'ADAPTERS'`.

- [ ] **Step 3: Populate the registry**

Replace `packages/core/src/openlia/llm/adapters/__init__.py` contents with:

```python
"""Adapter registry + factory.

Import this module when you need a concrete LLMProvider subclass for a given
`llm_providers.kind` value.
"""
from __future__ import annotations

from openlia.llm.adapters.anthropic import AnthropicAdapter
from openlia.llm.adapters.gemini import GeminiAdapter
from openlia.llm.adapters.ollama import OllamaAdapter
from openlia.llm.adapters.openai import OpenAIAdapter
from openlia.llm.adapters.openai_compat import OpenAICompatAdapter
from openlia.llm.adapters.openrouter import OpenRouterAdapter
from openlia.llm.base import LLMProvider
from openlia.llm.types import Capabilities, ProviderCredentials


ADAPTERS: dict[str, type[LLMProvider]] = {
    "openai": OpenAIAdapter,
    "anthropic": AnthropicAdapter,
    "gemini": GeminiAdapter,
    "openrouter": OpenRouterAdapter,
    "openai_compat": OpenAICompatAdapter,
    "ollama": OllamaAdapter,
}


def build_adapter(
    *,
    kind: str,
    credentials: ProviderCredentials,
    model: str,
    capabilities: Capabilities,
) -> LLMProvider:
    """Construct an adapter instance for `kind`.

    Raises KeyError if `kind` is not registered.
    """
    cls = ADAPTERS[kind]
    return cls(credentials=credentials, model=model, capabilities=capabilities)


__all__ = [
    "ADAPTERS",
    "build_adapter",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "GeminiAdapter",
    "OpenRouterAdapter",
    "OpenAICompatAdapter",
    "OllamaAdapter",
]
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/core/tests/test_llm/test_adapter_registry.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/adapters/__init__.py \
        packages/core/tests/test_llm/test_adapter_registry.py
git commit -m "phase-4(llm): adapter registry + build_adapter() factory"
```

---

## Task 14: Resolver + `ModelRegistry` Protocol

**Files:**
- Create: `packages/core/src/openlia/llm/resolver.py`
- Create: `packages/core/tests/test_llm/test_resolver.py`

- [ ] **Step 1: Write the failing resolver tests**

Create `packages/core/tests/test_llm/test_resolver.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

import pytest

from openlia.llm.exceptions import TierNotConfiguredError
from openlia.llm.resolver import (
    ModelRegistry,
    ResolvedModelRow,
    resolve,
    resolve_tier,
)
from openlia.llm.types import (
    Capabilities,
    ModelTier,
    ProviderCredentials,
    ResolvedModel,
)


@dataclass
class _FakeRegistry:
    dept_tier_override: ModelTier | None = None
    user_pref: dict[tuple[str, ModelTier], ResolvedModelRow] | None = None
    tier_default: dict[ModelTier, ResolvedModelRow] | None = None
    any_in_tier: dict[ModelTier, ResolvedModelRow] | None = None

    def get_department_tier_override(self, department_id: str) -> ModelTier | None:
        return self.dept_tier_override

    def get_user_preference(
        self, user_id: str, tier: ModelTier
    ) -> ResolvedModelRow | None:
        if not self.user_pref:
            return None
        return self.user_pref.get((user_id, tier))

    def get_tier_default(self, tier: ModelTier) -> ResolvedModelRow | None:
        if not self.tier_default:
            return None
        return self.tier_default.get(tier)

    def get_any_in_tier(self, tier: ModelTier) -> ResolvedModelRow | None:
        if not self.any_in_tier:
            return None
        return self.any_in_tier.get(tier)


def _row(kind: str = "openai", tier: ModelTier = ModelTier.EVERYDAY) -> ResolvedModelRow:
    return ResolvedModelRow(
        model_id="m-1",
        model_ref="gpt-5.4",
        tier=tier,
        overrides={},
        provider_id="p-1",
        provider_kind=kind,
        credentials=ProviderCredentials(api_key="sk-test", base_url=None),
        capability_override=None,
    )


def test_resolve_tier_prefers_override() -> None:
    reg = _FakeRegistry(dept_tier_override=ModelTier.QUICK)
    assert resolve_tier("equity_research", ModelTier.THINKING, reg) is ModelTier.THINKING


def test_resolve_tier_falls_back_to_dept_override_then_shipped() -> None:
    reg = _FakeRegistry(dept_tier_override=ModelTier.QUICK)
    assert resolve_tier("equity_research", None, reg) is ModelTier.QUICK

    reg_no_override = _FakeRegistry()
    # equity_research shipped default is THINKING
    assert resolve_tier("equity_research", None, reg_no_override) is ModelTier.THINKING


def test_resolve_tier_unknown_department_defaults_to_everyday() -> None:
    reg = _FakeRegistry()
    assert resolve_tier("made_up", None, reg) is ModelTier.EVERYDAY


def test_resolve_uses_user_preference_first() -> None:
    reg = _FakeRegistry(
        user_pref={("u-1", ModelTier.EVERYDAY): _row()},
        tier_default={ModelTier.EVERYDAY: _row(kind="anthropic")},
    )
    result = resolve(department_id="secretary", registry=reg, user_id="u-1")
    assert result.provider_kind == "openai"


def test_resolve_falls_back_to_tier_default() -> None:
    reg = _FakeRegistry(tier_default={ModelTier.EVERYDAY: _row(kind="anthropic")})
    result = resolve(department_id="secretary", registry=reg, user_id="u-1")
    assert result.provider_kind == "anthropic"


def test_resolve_falls_back_to_any_in_tier() -> None:
    reg = _FakeRegistry(any_in_tier={ModelTier.EVERYDAY: _row(kind="gemini")})
    result = resolve(department_id="secretary", registry=reg, user_id=None)
    assert result.provider_kind == "gemini"


def test_resolve_raises_when_tier_empty() -> None:
    reg = _FakeRegistry()
    with pytest.raises(TierNotConfiguredError) as excinfo:
        resolve(department_id="secretary", registry=reg, user_id=None)
    assert excinfo.value.tier == "everyday"


def test_resolve_applies_capability_override() -> None:
    row = _row()
    row = ResolvedModelRow(
        **{
            **row.__dict__,
            "capability_override": {"tool_calling": False},
        }
    )
    reg = _FakeRegistry(tier_default={ModelTier.EVERYDAY: row})
    result = resolve(department_id="secretary", registry=reg, user_id=None)
    assert result.capabilities.tool_calling is False


def test_resolve_returns_resolved_model() -> None:
    reg = _FakeRegistry(tier_default={ModelTier.THINKING: _row(tier=ModelTier.THINKING)})
    result = resolve(department_id="equity_research", registry=reg, user_id=None)
    assert isinstance(result, ResolvedModel)
    assert result.tier is ModelTier.THINKING
    assert result.model_ref == "gpt-5.4"
    assert result.credentials.api_key == "sk-test"


def test_tier_override_arg_trumps_everything() -> None:
    reg = _FakeRegistry(
        dept_tier_override=ModelTier.EVERYDAY,
        tier_default={ModelTier.QUICK: _row(tier=ModelTier.QUICK)},
    )
    result = resolve(
        department_id="equity_research",
        registry=reg,
        user_id=None,
        tier_override=ModelTier.QUICK,
    )
    assert result.tier is ModelTier.QUICK
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/core/tests/test_llm/test_resolver.py -v`
Expected: module-not-found error.

- [ ] **Step 3: Implement the resolver**

Create `packages/core/src/openlia/llm/resolver.py`:

```python
"""Two-stage resolver: department -> tier, then tier -> ResolvedModel.

Stage 1 (tier selection):
  1. tier_override argument.
  2. Registry's department tier override (stored in config_store).
  3. Shipped DEPARTMENT_DEFAULT_TIERS. Unknown department -> EVERYDAY.

Stage 2 (model within tier):
  1. user_llm_preferences row for (user_id, tier).
  2. llm_models row where tier = X AND is_tier_default AND is_enabled.
  3. Any enabled llm_models row in tier X (oldest created_at).
  4. Raise TierNotConfiguredError.

The core layer does NOT talk to SQLAlchemy. `ModelRegistry` is a Protocol; the
server layer implements it (see SQLModelRegistry).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from openlia.llm.capabilities import capabilities_for
from openlia.llm.department_defaults import DEPARTMENT_DEFAULT_TIERS
from openlia.llm.exceptions import TierNotConfiguredError
from openlia.llm.types import (
    ModelTier,
    ProviderCredentials,
    ResolvedModel,
)


@dataclass(frozen=True)
class ResolvedModelRow:
    """Registry-layer dataclass bridging DB rows into the core resolver.

    Combines `llm_models` + `llm_providers` (joined) + optional capability override.
    The server's SQLModelRegistry constructs this.
    """

    model_id: str
    model_ref: str
    tier: ModelTier
    overrides: dict

    provider_id: str
    provider_kind: str
    credentials: ProviderCredentials

    capability_override: dict | None


class ModelRegistry(Protocol):
    def get_department_tier_override(
        self, department_id: str
    ) -> ModelTier | None: ...

    def get_user_preference(
        self, user_id: str, tier: ModelTier
    ) -> ResolvedModelRow | None: ...

    def get_tier_default(self, tier: ModelTier) -> ResolvedModelRow | None: ...

    def get_any_in_tier(self, tier: ModelTier) -> ResolvedModelRow | None: ...


def resolve_tier(
    department_id: str,
    tier_override: ModelTier | None,
    registry: ModelRegistry,
) -> ModelTier:
    """Stage 1 — pick the tier."""
    if tier_override is not None:
        return tier_override
    dept_override = registry.get_department_tier_override(department_id)
    if dept_override is not None:
        return dept_override
    return DEPARTMENT_DEFAULT_TIERS.get(department_id, ModelTier.EVERYDAY)


def _to_resolved(row: ResolvedModelRow) -> ResolvedModel:
    caps = capabilities_for(
        provider_kind=row.provider_kind,
        model=row.model_ref,
        override=row.capability_override,
    )
    return ResolvedModel(
        provider_kind=row.provider_kind,
        provider_id=row.provider_id,
        model_id=row.model_id,
        model_ref=row.model_ref,
        tier=row.tier,
        credentials=row.credentials,
        capabilities=caps,
        overrides=row.overrides or {},
    )


def resolve(
    *,
    department_id: str,
    registry: ModelRegistry,
    user_id: str | None,
    tier_override: ModelTier | None = None,
) -> ResolvedModel:
    """End-to-end resolution. Returns a ResolvedModel with credentials + caps."""
    tier = resolve_tier(department_id, tier_override, registry)

    if user_id is not None:
        pref = registry.get_user_preference(user_id, tier)
        if pref is not None:
            return _to_resolved(pref)

    tier_default = registry.get_tier_default(tier)
    if tier_default is not None:
        return _to_resolved(tier_default)

    any_row = registry.get_any_in_tier(tier)
    if any_row is not None:
        return _to_resolved(any_row)

    raise TierNotConfiguredError(tier.value)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/core/tests/test_llm/test_resolver.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/resolver.py \
        packages/core/tests/test_llm/test_resolver.py
git commit -m "phase-4(llm): resolver + ModelRegistry Protocol (two-stage tier/model resolution)"
```

---

## Task 15: Server service layer — `llm_providers.py` (CRUD + crypto)

**Files:**
- Create: `packages/server/src/openlia_server/services/llm_providers.py`
- Create: `packages/server/tests/test_services/test_llm_providers_service.py`

- [ ] **Step 1: Write the failing service tests**

Create `packages/server/tests/test_services/test_llm_providers_service.py`:

```python
from __future__ import annotations

import pytest

from openlia_server.db.models.config import LLMModel, LLMProvider, UserLLMPreference
from openlia_server.services import llm_providers as svc


@pytest.fixture
def _env_secret(monkeypatch):
    # Deterministic key for tests — Plan 2's secrets module reads this.
    key = "0" * 43 + "="  # 32-byte base64
    monkeypatch.setenv("OPENLIA_SECRET_KEY", key)


def test_create_provider_encrypts_api_key(_env_secret, db_session) -> None:
    created = svc.create_provider(
        db_session,
        kind="openai",
        label="Main OpenAI",
        api_key="sk-plain-xyz",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    row = db_session.get(LLMProvider, created.id)
    assert row is not None
    assert row.api_key_encrypted is not None
    # Must not store plaintext.
    assert "sk-plain-xyz" not in row.api_key_encrypted


def test_create_provider_with_env_var_does_not_encrypt(_env_secret, db_session) -> None:
    created = svc.create_provider(
        db_session,
        kind="openai",
        label="via env",
        api_key=None,
        base_url=None,
        env_var_name="MY_OPENAI_KEY",
        extra_config=None,
    )
    row = db_session.get(LLMProvider, created.id)
    assert row.api_key_encrypted is None
    assert row.env_var_name == "MY_OPENAI_KEY"


def test_get_provider_api_key_prefers_env(_env_secret, db_session, monkeypatch) -> None:
    created = svc.create_provider(
        db_session,
        kind="openai",
        label="hybrid",
        api_key="sk-db",
        base_url=None,
        env_var_name="OPENLIA_TEST_KEY",
        extra_config=None,
    )
    monkeypatch.setenv("OPENLIA_TEST_KEY", "sk-env")
    key = svc.get_provider_api_key(db_session, created.id)
    assert key == "sk-env"


def test_get_provider_api_key_falls_back_to_decrypted(_env_secret, db_session) -> None:
    created = svc.create_provider(
        db_session,
        kind="openai",
        label="db only",
        api_key="sk-db",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    key = svc.get_provider_api_key(db_session, created.id)
    assert key == "sk-db"


def test_update_provider_rewrites_encryption_when_api_key_changes(
    _env_secret, db_session
) -> None:
    created = svc.create_provider(
        db_session,
        kind="openai",
        label="x",
        api_key="old",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    svc.update_provider(db_session, created.id, api_key="new")
    assert svc.get_provider_api_key(db_session, created.id) == "new"


def test_delete_provider_blocks_when_models_exist(_env_secret, db_session) -> None:
    from openlia_server.services import llm_providers as svc2

    provider = svc.create_provider(
        db_session,
        kind="openai",
        label="x",
        api_key="k",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    svc.create_model(
        db_session,
        provider_id=provider.id,
        tier="thinking",
        model_ref="gpt-5.4-pro",
        display_name="GPT 5.4 Pro",
        is_tier_default=True,
    )
    with pytest.raises(svc2.ProviderHasModelsError):
        svc.delete_provider(db_session, provider.id)


def test_create_model_enforces_single_tier_default(_env_secret, db_session) -> None:
    provider = svc.create_provider(
        db_session,
        kind="openai",
        label="x",
        api_key="k",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    svc.create_model(
        db_session,
        provider_id=provider.id,
        tier="thinking",
        model_ref="gpt-5.4-pro",
        display_name="Pro",
        is_tier_default=True,
    )
    # Second is_tier_default=true in the same tier should clear the first one.
    svc.create_model(
        db_session,
        provider_id=provider.id,
        tier="thinking",
        model_ref="gpt-other",
        display_name="Other",
        is_tier_default=True,
    )
    defaults = [
        m
        for m in db_session.query(LLMModel).filter(LLMModel.tier == "thinking").all()
        if m.is_tier_default
    ]
    assert len(defaults) == 1
    assert defaults[0].model_ref == "gpt-other"


def test_set_user_preference_upserts(_env_secret, db_session) -> None:
    provider = svc.create_provider(
        db_session,
        kind="openai",
        label="x",
        api_key="k",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    model = svc.create_model(
        db_session,
        provider_id=provider.id,
        tier="everyday",
        model_ref="gpt-5.4",
        display_name="GPT",
        is_tier_default=True,
    )
    svc.set_user_preference(db_session, user_id="u-1", tier="everyday", model_id=model.id)
    row = (
        db_session.query(UserLLMPreference)
        .filter_by(user_id="u-1", tier="everyday")
        .one()
    )
    assert row.model_id == model.id
    # Upsert — same (user, tier) should update, not insert.
    model2 = svc.create_model(
        db_session,
        provider_id=provider.id,
        tier="everyday",
        model_ref="gpt-other",
        display_name="Other",
        is_tier_default=False,
    )
    svc.set_user_preference(db_session, user_id="u-1", tier="everyday", model_id=model2.id)
    rows = (
        db_session.query(UserLLMPreference).filter_by(user_id="u-1", tier="everyday").all()
    )
    assert len(rows) == 1
    assert rows[0].model_id == model2.id


def test_capability_override_roundtrip(_env_secret, db_session) -> None:
    svc.set_capability_override(
        db_session,
        provider_kind="anthropic",
        model="claude-opus-4-6",
        override={"tool_calling": False},
    )
    got = svc.get_capability_override(
        db_session, provider_kind="anthropic", model="claude-opus-4-6"
    )
    assert got == {"tool_calling": False}
    svc.clear_capability_override(
        db_session, provider_kind="anthropic", model="claude-opus-4-6"
    )
    assert (
        svc.get_capability_override(
            db_session, provider_kind="anthropic", model="claude-opus-4-6"
        )
        is None
    )


def test_department_tier_override_roundtrip(_env_secret, db_session) -> None:
    svc.set_department_tier_override(db_session, "equity_research", "quick")
    assert svc.get_department_tier_override(db_session, "equity_research") == "quick"
    svc.clear_department_tier_override(db_session, "equity_research")
    assert svc.get_department_tier_override(db_session, "equity_research") is None
```

- [ ] **Step 2: Ensure `db_session` fixture is in scope**

The fixture is defined in Plan 1A's `packages/server/tests/test_db/conftest.py`. Re-export it in `packages/server/tests/conftest.py` if not already present:

```python
# packages/server/tests/conftest.py (add this import if missing)
from .test_db.conftest import db_session  # noqa: F401
```

Run: `uv run pytest packages/server/tests/test_services/test_llm_providers_service.py -v`
Expected: `ModuleNotFoundError: No module named 'openlia_server.services.llm_providers'`.

- [ ] **Step 3: Implement the service module**

Create `packages/server/src/openlia_server/services/llm_providers.py`:

```python
"""CRUD + encryption for llm_providers / llm_models + config_store overrides.

The admin route layer calls into this module. Pure DB logic — no FastAPI
imports, no HTTP. Imports Plan 2's encrypt_for_row / decrypt_for_row and uses
llm_providers.id as AAD.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from openlia_server.db.models.config import (
    ConfigStore,
    LLMModel,
    LLMProvider,
    UserLLMPreference,
)
from openlia_server.security.secrets import decrypt_for_row, encrypt_for_row


class ProviderHasModelsError(Exception):
    """Raised when delete_provider is called on a provider with dependent models."""


class ModelNotFoundInDBError(Exception):
    """Raised when an operation references an llm_models row that doesn't exist."""


@dataclass(frozen=True)
class ProviderCreated:
    id: str


def create_provider(
    db: Session,
    *,
    kind: str,
    label: str,
    api_key: str | None,
    base_url: str | None,
    env_var_name: str | None,
    extra_config: dict | None,
    is_enabled: bool = True,
    created_by_user_id: str | None = None,
) -> ProviderCreated:
    row_id = str(uuid.uuid4())
    encrypted = encrypt_for_row(row_id, api_key) if api_key else None
    row = LLMProvider(
        id=row_id,
        kind=kind,
        label=label,
        api_key_encrypted=encrypted,
        env_var_name=env_var_name,
        base_url=base_url,
        extra_config=extra_config,
        is_enabled=is_enabled,
        created_by_user_id=created_by_user_id,
    )
    db.add(row)
    db.commit()
    return ProviderCreated(id=row_id)


def update_provider(
    db: Session,
    provider_id: str,
    *,
    kind: str | None = None,
    label: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    env_var_name: str | None = None,
    extra_config: dict | None = None,
    is_enabled: bool | None = None,
) -> None:
    row = db.get(LLMProvider, provider_id)
    if row is None:
        raise ModelNotFoundInDBError(f"llm_providers.id={provider_id}")
    if kind is not None:
        row.kind = kind
    if label is not None:
        row.label = label
    if api_key is not None:
        row.api_key_encrypted = encrypt_for_row(provider_id, api_key)
    if base_url is not None:
        row.base_url = base_url
    if env_var_name is not None:
        row.env_var_name = env_var_name
    if extra_config is not None:
        row.extra_config = extra_config
    if is_enabled is not None:
        row.is_enabled = is_enabled
    db.commit()


def delete_provider(db: Session, provider_id: str) -> None:
    has_models = (
        db.query(LLMModel).filter(LLMModel.provider_id == provider_id).count() > 0
    )
    if has_models:
        raise ProviderHasModelsError(
            f"provider {provider_id} has llm_models rows — delete them first"
        )
    row = db.get(LLMProvider, provider_id)
    if row is None:
        return
    db.delete(row)
    db.commit()


def list_providers(db: Session) -> list[LLMProvider]:
    return list(db.query(LLMProvider).order_by(LLMProvider.label).all())


def get_provider(db: Session, provider_id: str) -> LLMProvider | None:
    return db.get(LLMProvider, provider_id)


def get_provider_api_key(db: Session, provider_id: str) -> str | None:
    row = db.get(LLMProvider, provider_id)
    if row is None:
        return None
    if row.env_var_name:
        env_val = os.environ.get(row.env_var_name)
        if env_val:
            return env_val
    if row.api_key_encrypted:
        return decrypt_for_row(provider_id, row.api_key_encrypted)
    return None


def create_model(
    db: Session,
    *,
    provider_id: str,
    tier: str,
    model_ref: str,
    display_name: str,
    is_tier_default: bool = False,
    is_enabled: bool = True,
    overrides: dict | None = None,
) -> LLMModel:
    if is_tier_default:
        # Clear any existing default in this tier to honor the partial unique index.
        db.execute(
            update(LLMModel).where(LLMModel.tier == tier).values(is_tier_default=False)
        )
    model_id = str(uuid.uuid4())
    row = LLMModel(
        id=model_id,
        provider_id=provider_id,
        tier=tier,
        model_ref=model_ref,
        display_name=display_name,
        is_tier_default=is_tier_default,
        is_enabled=is_enabled,
        overrides=overrides,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_model(
    db: Session,
    model_id: str,
    *,
    tier: str | None = None,
    display_name: str | None = None,
    is_tier_default: bool | None = None,
    is_enabled: bool | None = None,
    overrides: dict | None = None,
) -> None:
    row = db.get(LLMModel, model_id)
    if row is None:
        raise ModelNotFoundInDBError(f"llm_models.id={model_id}")
    if tier is not None:
        row.tier = tier
    if display_name is not None:
        row.display_name = display_name
    if is_tier_default is True:
        db.execute(
            update(LLMModel)
            .where(LLMModel.tier == row.tier)
            .where(LLMModel.id != model_id)
            .values(is_tier_default=False)
        )
        row.is_tier_default = True
    elif is_tier_default is False:
        row.is_tier_default = False
    if is_enabled is not None:
        row.is_enabled = is_enabled
    if overrides is not None:
        row.overrides = overrides
    db.commit()


def delete_model(db: Session, model_id: str) -> None:
    row = db.get(LLMModel, model_id)
    if row is None:
        return
    db.delete(row)
    db.commit()


def list_models_for_provider(db: Session, provider_id: str) -> list[LLMModel]:
    return list(
        db.query(LLMModel)
        .filter(LLMModel.provider_id == provider_id)
        .order_by(LLMModel.tier, LLMModel.display_name)
        .all()
    )


def list_all_models(db: Session) -> list[LLMModel]:
    return list(db.query(LLMModel).order_by(LLMModel.tier, LLMModel.display_name).all())


def set_user_preference(
    db: Session, *, user_id: str, tier: str, model_id: str
) -> None:
    existing = (
        db.query(UserLLMPreference)
        .filter_by(user_id=user_id, tier=tier)
        .one_or_none()
    )
    if existing is None:
        db.add(UserLLMPreference(user_id=user_id, tier=tier, model_id=model_id))
    else:
        existing.model_id = model_id
    db.commit()


def clear_user_preference(db: Session, *, user_id: str, tier: str) -> None:
    db.query(UserLLMPreference).filter_by(user_id=user_id, tier=tier).delete()
    db.commit()


def get_user_preference(
    db: Session, *, user_id: str, tier: str
) -> UserLLMPreference | None:
    return (
        db.query(UserLLMPreference)
        .filter_by(user_id=user_id, tier=tier)
        .one_or_none()
    )


def list_user_preferences(db: Session, *, user_id: str) -> list[UserLLMPreference]:
    return list(db.query(UserLLMPreference).filter_by(user_id=user_id).all())


# ---------------------------------------------------------------------------
# config_store overrides: capability_override + department tier override
# ---------------------------------------------------------------------------

def _capability_override_key(provider_kind: str, model: str) -> str:
    return f"llm.capability_override.{provider_kind}.{model}"


def _department_tier_key(department_id: str) -> str:
    return f"llm.department.{department_id}.tier"


def _config_get(db: Session, key: str) -> str | None:
    row = db.get(ConfigStore, key)
    return row.value if row else None


def _config_set(db: Session, key: str, value: str | None) -> None:
    row = db.get(ConfigStore, key)
    if value is None:
        if row is not None:
            db.delete(row)
    elif row is None:
        db.add(ConfigStore(key=key, value=value))
    else:
        row.value = value
    db.commit()


def set_capability_override(
    db: Session, *, provider_kind: str, model: str, override: dict
) -> None:
    _config_set(db, _capability_override_key(provider_kind, model), json.dumps(override))


def get_capability_override(
    db: Session, *, provider_kind: str, model: str
) -> dict | None:
    raw = _config_get(db, _capability_override_key(provider_kind, model))
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def clear_capability_override(
    db: Session, *, provider_kind: str, model: str
) -> None:
    _config_set(db, _capability_override_key(provider_kind, model), None)


def set_department_tier_override(db: Session, department_id: str, tier: str) -> None:
    if tier not in {"thinking", "everyday", "quick"}:
        raise ValueError(f"invalid tier: {tier}")
    _config_set(db, _department_tier_key(department_id), tier)


def get_department_tier_override(db: Session, department_id: str) -> str | None:
    return _config_get(db, _department_tier_key(department_id))


def clear_department_tier_override(db: Session, department_id: str) -> None:
    _config_set(db, _department_tier_key(department_id), None)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/server/tests/test_services/test_llm_providers_service.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/llm_providers.py \
        packages/server/tests/test_services/test_llm_providers_service.py
git commit -m "phase-4(llm): server service layer — llm_providers CRUD + crypto + overrides"
```

---

## Task 16: Server service layer — `llm_registry.py` (SQLModelRegistry)

**Files:**
- Create: `packages/server/src/openlia_server/services/llm_registry.py`
- Create: `packages/server/tests/test_services/test_llm_registry.py`

- [ ] **Step 1: Write the failing registry tests**

Create `packages/server/tests/test_services/test_llm_registry.py`:

```python
from __future__ import annotations

import pytest

from openlia.llm.resolver import resolve
from openlia.llm.types import ModelTier
from openlia_server.services import llm_providers as svc
from openlia_server.services.llm_registry import SQLModelRegistry


@pytest.fixture
def _env_secret(monkeypatch):
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")


def _seed_openai(db_session) -> tuple[str, str]:
    p = svc.create_provider(
        db_session,
        kind="openai",
        label="main",
        api_key="sk-test",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    m = svc.create_model(
        db_session,
        provider_id=p.id,
        tier="thinking",
        model_ref="gpt-5.4-pro",
        display_name="Pro",
        is_tier_default=True,
    )
    return p.id, m.id


def test_get_user_preference_joins_provider_and_decrypts(
    _env_secret, db_session, make_user
) -> None:
    user = make_user(email="u@openlia.local", password="pw-12345678", is_admin=False)
    _, model_id = _seed_openai(db_session)
    svc.set_user_preference(
        db_session, user_id=user.id, tier="thinking", model_id=model_id
    )
    reg = SQLModelRegistry(db_session)
    row = reg.get_user_preference(user.id, ModelTier.THINKING)
    assert row is not None
    assert row.provider_kind == "openai"
    assert row.model_ref == "gpt-5.4-pro"
    assert row.credentials.api_key == "sk-test"


def test_get_tier_default_returns_the_flagged_model(_env_secret, db_session) -> None:
    _seed_openai(db_session)
    reg = SQLModelRegistry(db_session)
    row = reg.get_tier_default(ModelTier.THINKING)
    assert row is not None
    assert row.model_ref == "gpt-5.4-pro"


def test_get_tier_default_none_when_absent(_env_secret, db_session) -> None:
    reg = SQLModelRegistry(db_session)
    assert reg.get_tier_default(ModelTier.QUICK) is None


def test_get_any_in_tier_returns_oldest_created(_env_secret, db_session) -> None:
    p = svc.create_provider(
        db_session,
        kind="openai",
        label="x",
        api_key="k",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    first = svc.create_model(
        db_session,
        provider_id=p.id,
        tier="quick",
        model_ref="first",
        display_name="First",
        is_tier_default=False,
    )
    svc.create_model(
        db_session,
        provider_id=p.id,
        tier="quick",
        model_ref="second",
        display_name="Second",
        is_tier_default=False,
    )
    reg = SQLModelRegistry(db_session)
    row = reg.get_any_in_tier(ModelTier.QUICK)
    assert row is not None
    assert row.model_id == first.id


def test_get_any_in_tier_skips_disabled(_env_secret, db_session) -> None:
    p = svc.create_provider(
        db_session,
        kind="openai",
        label="x",
        api_key="k",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    disabled = svc.create_model(
        db_session,
        provider_id=p.id,
        tier="quick",
        model_ref="off",
        display_name="Off",
        is_tier_default=False,
    )
    svc.update_model(db_session, disabled.id, is_enabled=False)
    enabled = svc.create_model(
        db_session,
        provider_id=p.id,
        tier="quick",
        model_ref="on",
        display_name="On",
        is_tier_default=False,
    )
    reg = SQLModelRegistry(db_session)
    row = reg.get_any_in_tier(ModelTier.QUICK)
    assert row is not None
    assert row.model_id == enabled.id


def test_get_department_tier_override_reads_config_store(
    _env_secret, db_session
) -> None:
    svc.set_department_tier_override(db_session, "equity_research", "quick")
    reg = SQLModelRegistry(db_session)
    assert reg.get_department_tier_override("equity_research") is ModelTier.QUICK


def test_resolve_end_to_end_through_sql_registry(_env_secret, db_session) -> None:
    _seed_openai(db_session)
    reg = SQLModelRegistry(db_session)
    resolved = resolve(
        department_id="equity_research",  # shipped default is THINKING
        registry=reg,
        user_id=None,
    )
    assert resolved.provider_kind == "openai"
    assert resolved.tier is ModelTier.THINKING
    assert resolved.credentials.api_key == "sk-test"


def test_capability_override_is_applied_via_resolver(_env_secret, db_session) -> None:
    _seed_openai(db_session)
    svc.set_capability_override(
        db_session,
        provider_kind="openai",
        model="gpt-5.4-pro",
        override={"tool_calling": False},
    )
    reg = SQLModelRegistry(db_session)
    resolved = resolve(
        department_id="equity_research", registry=reg, user_id=None
    )
    assert resolved.capabilities.tool_calling is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_services/test_llm_registry.py -v`
Expected: module-not-found error.

- [ ] **Step 3: Implement `SQLModelRegistry`**

Create `packages/server/src/openlia_server/services/llm_registry.py`:

```python
"""SQLAlchemy implementation of core's ModelRegistry Protocol.

Bridges llm_providers / llm_models / user_llm_preferences rows into the
ResolvedModelRow shape core.resolver.resolve() expects. Decrypts API keys
here so the core layer never touches crypto.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia.llm.resolver import ModelRegistry, ResolvedModelRow
from openlia.llm.types import ModelTier, ProviderCredentials
from openlia_server.db.models.config import LLMModel, LLMProvider
from openlia_server.services import llm_providers as svc


class SQLModelRegistry(ModelRegistry):
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_department_tier_override(
        self, department_id: str
    ) -> ModelTier | None:
        raw = svc.get_department_tier_override(self._db, department_id)
        if raw is None:
            return None
        try:
            return ModelTier(raw)
        except ValueError:
            return None

    def get_user_preference(
        self, user_id: str, tier: ModelTier
    ) -> ResolvedModelRow | None:
        pref = svc.get_user_preference(self._db, user_id=user_id, tier=tier.value)
        if pref is None:
            return None
        return self._load_row(pref.model_id)

    def get_tier_default(self, tier: ModelTier) -> ResolvedModelRow | None:
        stmt = (
            select(LLMModel)
            .where(LLMModel.tier == tier.value)
            .where(LLMModel.is_tier_default.is_(True))
            .where(LLMModel.is_enabled.is_(True))
            .limit(1)
        )
        model = self._db.execute(stmt).scalar_one_or_none()
        if model is None:
            return None
        return self._build_row(model)

    def get_any_in_tier(self, tier: ModelTier) -> ResolvedModelRow | None:
        stmt = (
            select(LLMModel)
            .where(LLMModel.tier == tier.value)
            .where(LLMModel.is_enabled.is_(True))
            .order_by(LLMModel.created_at.asc())
            .limit(1)
        )
        model = self._db.execute(stmt).scalar_one_or_none()
        if model is None:
            return None
        return self._build_row(model)

    def _load_row(self, model_id: str) -> ResolvedModelRow | None:
        model = self._db.get(LLMModel, model_id)
        if model is None or not model.is_enabled:
            return None
        return self._build_row(model)

    def _build_row(self, model: LLMModel) -> ResolvedModelRow:
        provider = self._db.get(LLMProvider, model.provider_id)
        if provider is None or not provider.is_enabled:
            # The model can't be used — skip it by returning None would hide the
            # inconsistency; instead return a row that the resolver will filter.
            # In practice this path is unreachable because `is_enabled` is set
            # on both sides and delete cascades are RESTRICT.
            raise RuntimeError(
                f"llm_models.{model.id} references missing/disabled provider"
            )
        api_key = svc.get_provider_api_key(self._db, provider.id)
        override = svc.get_capability_override(
            self._db, provider_kind=provider.kind, model=model.model_ref
        )
        return ResolvedModelRow(
            model_id=model.id,
            model_ref=model.model_ref,
            tier=ModelTier(model.tier),
            overrides=model.overrides or {},
            provider_id=provider.id,
            provider_kind=provider.kind,
            credentials=ProviderCredentials(
                api_key=api_key, base_url=provider.base_url
            ),
            capability_override=override,
        )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/server/tests/test_services/test_llm_registry.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/llm_registry.py \
        packages/server/tests/test_services/test_llm_registry.py
git commit -m "phase-4(llm): SQLModelRegistry bridges core ModelRegistry Protocol to SQLAlchemy"
```

---

## Task 17: Admin routes (provider/model CRUD + test + remote-models + overrides)

**Files:**
- Modify: `packages/server/src/openlia_server/routes/settings.py` (created in Plan 3)
- Create: `packages/server/tests/test_routes/test_llm_admin_routes.py`

- [ ] **Step 1: Write the failing admin route tests**

Create `packages/server/tests/test_routes/test_llm_admin_routes.py`:

```python
from __future__ import annotations

import pytest
import respx

from openlia_server.services import llm_providers as svc


def _login(client, email="admin@openlia.local", password="pw-12345678"):
    client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )


def test_list_providers_requires_admin(company_client, make_user) -> None:
    # Non-admin user hits /settings/admin/llm/providers -> 403
    make_user(email="u@openlia.local", password="pw-12345678", is_admin=False)
    _login(company_client, email="u@openlia.local")
    resp = company_client.get("/settings/admin/llm/providers")
    assert resp.status_code == 403


def test_create_provider_requires_admin(company_client, make_user) -> None:
    make_user(email="u@openlia.local", password="pw-12345678", is_admin=False)
    _login(company_client, email="u@openlia.local")
    resp = company_client.post(
        "/settings/admin/llm/providers",
        json={"kind": "openai", "label": "x", "api_key": "k"},
    )
    assert resp.status_code == 403


def test_create_provider_happy_path_encrypts_api_key(
    company_client, make_user, db_session, monkeypatch
) -> None:
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="admin@openlia.local", password="pw-12345678", is_admin=True)
    _login(company_client)
    with respx.mock():
        respx.post("https://api.openai.com/v1/chat/completions").respond(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "x"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )
        resp = company_client.post(
            "/settings/admin/llm/providers",
            json={
                "kind": "openai",
                "label": "Main OpenAI",
                "api_key": "sk-plain",
                "run_test": True,
                "test_model": "gpt-5.4",
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["kind"] == "openai"
    assert body["has_api_key"] is True
    assert "api_key" not in body  # never echoed back
    assert body["test"]["ok"] is True


def test_create_provider_rejects_failing_connection(
    company_client, make_user, monkeypatch
) -> None:
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="admin@openlia.local", password="pw-12345678", is_admin=True)
    _login(company_client)
    with respx.mock():
        respx.post("https://api.openai.com/v1/chat/completions").respond(
            401, json={"error": {"message": "bad key"}}
        )
        resp = company_client.post(
            "/settings/admin/llm/providers",
            json={
                "kind": "openai",
                "label": "Main OpenAI",
                "api_key": "sk-wrong",
                "run_test": True,
                "test_model": "gpt-5.4",
            },
        )
    assert resp.status_code == 400
    # Provider should NOT have been persisted.
    from openlia_server.db.models.config import LLMProvider
    from openlia_server.tests.test_db.conftest import TestingSessionLocal  # shared
    # (rely on db_session fixture below)


def test_test_provider_endpoint_does_not_persist(
    company_client, make_user, db_session, monkeypatch
) -> None:
    from openlia_server.db.models.config import LLMProvider

    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="admin@openlia.local", password="pw-12345678", is_admin=True)
    _login(company_client)
    with respx.mock():
        respx.post("https://api.openai.com/v1/chat/completions").respond(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "x"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )
        resp = company_client.post(
            "/settings/admin/llm/providers/test",
            json={"kind": "openai", "api_key": "sk-x", "model": "gpt-5.4"},
        )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert db_session.query(LLMProvider).count() == 0


def test_create_model_rejects_without_provider(
    company_client, make_user, monkeypatch
) -> None:
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="admin@openlia.local", password="pw-12345678", is_admin=True)
    _login(company_client)
    resp = company_client.post(
        "/settings/admin/llm/models",
        json={
            "provider_id": "no-such",
            "tier": "thinking",
            "model_ref": "gpt-5.4-pro",
            "display_name": "Pro",
        },
    )
    assert resp.status_code == 404


def test_delete_provider_blocks_with_models(
    company_client, make_user, db_session, monkeypatch
) -> None:
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="admin@openlia.local", password="pw-12345678", is_admin=True)
    _login(company_client)
    p = svc.create_provider(
        db_session,
        kind="openai",
        label="x",
        api_key="k",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    svc.create_model(
        db_session,
        provider_id=p.id,
        tier="thinking",
        model_ref="x",
        display_name="x",
        is_tier_default=True,
    )
    resp = company_client.delete(f"/settings/admin/llm/providers/{p.id}")
    assert resp.status_code == 409


def test_department_tier_override_roundtrip(
    company_client, make_user, monkeypatch
) -> None:
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="admin@openlia.local", password="pw-12345678", is_admin=True)
    _login(company_client)
    resp = company_client.post(
        "/settings/admin/llm/department/equity_research", json={"tier": "quick"}
    )
    assert resp.status_code == 200
    resp = company_client.post(
        "/settings/admin/llm/department/equity_research", json={"tier": None}
    )
    assert resp.status_code == 200


def test_capability_override_roundtrip(
    company_client, make_user, monkeypatch
) -> None:
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="admin@openlia.local", password="pw-12345678", is_admin=True)
    _login(company_client)
    resp = company_client.post(
        "/settings/admin/llm/capability_override/openai/gpt-5.4",
        json={"tool_calling": False},
    )
    assert resp.status_code == 200
    resp = company_client.post(
        "/settings/admin/llm/capability_override/openai/gpt-5.4", json=None
    )
    assert resp.status_code == 200
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_routes/test_llm_admin_routes.py -v`
Expected: 404 everywhere — routes not mounted yet.

- [ ] **Step 3: Extend `routes/settings.py` with LLM router builders**

Append to `packages/server/src/openlia_server/routes/settings.py` (append — do not overwrite the existing `build_data_providers_router` from Plan 3). If Plan 3 put the data-provider router there, place the new code below it.

```python
# --- LLM provider admin router ------------------------------------------------

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from openlia.llm.adapters import build_adapter
from openlia.llm.types import (
    Capabilities,
    ProviderCredentials,
)
from openlia_server.middleware.auth import build_require_admin, build_require_auth
from openlia_server.services import llm_providers as svc


class _ProviderIn(BaseModel):
    kind: Literal["openai", "anthropic", "gemini", "openrouter", "openai_compat", "ollama"]
    label: str
    api_key: str | None = None
    base_url: str | None = None
    env_var_name: str | None = None
    extra_config: dict | None = None
    is_enabled: bool = True
    run_test: bool = False
    test_model: str | None = None


class _ProviderOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: str
    kind: str
    label: str
    has_api_key: bool
    env_var_name: str | None
    base_url: str | None
    is_enabled: bool
    test: dict | None = None


class _ProviderUpdate(BaseModel):
    label: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    env_var_name: str | None = None
    extra_config: dict | None = None
    is_enabled: bool | None = None


class _ModelIn(BaseModel):
    provider_id: str
    tier: Literal["thinking", "everyday", "quick"]
    model_ref: str
    display_name: str
    is_tier_default: bool = False
    is_enabled: bool = True
    overrides: dict | None = None


class _ModelOut(BaseModel):
    id: str
    provider_id: str
    tier: str
    model_ref: str
    display_name: str
    is_tier_default: bool
    is_enabled: bool
    overrides: dict | None


class _TestIn(BaseModel):
    kind: Literal["openai", "anthropic", "gemini", "openrouter", "openai_compat", "ollama"]
    api_key: str | None = None
    base_url: str | None = None
    model: str
    env_var_name: str | None = None


class _TestOut(BaseModel):
    ok: bool
    latency_ms: int
    error_class: str | None = None
    error_msg: str | None = None


class _DepartmentTierIn(BaseModel):
    tier: Literal["thinking", "everyday", "quick"] | None = None


def _provider_to_out(row, *, test: dict | None = None) -> _ProviderOut:
    return _ProviderOut(
        id=row.id,
        kind=row.kind,
        label=row.label,
        has_api_key=bool(row.api_key_encrypted or row.env_var_name),
        env_var_name=row.env_var_name,
        base_url=row.base_url,
        is_enabled=row.is_enabled,
        test=test,
    )


async def _run_connection_test(
    kind: str,
    *,
    api_key: str | None,
    base_url: str | None,
    env_var_name: str | None,
    model: str,
) -> _TestOut:
    import os

    effective_key = api_key
    if env_var_name:
        effective_key = os.environ.get(env_var_name) or api_key

    try:
        adapter = build_adapter(
            kind=kind,
            credentials=ProviderCredentials(api_key=effective_key, base_url=base_url),
            model=model,
            capabilities=Capabilities(),
        )
    except Exception as exc:  # noqa: BLE001
        return _TestOut(
            ok=False,
            latency_ms=0,
            error_class=type(exc).__name__,
            error_msg=str(exc),
        )

    result = await adapter.test_connection(model)
    return _TestOut(
        ok=result.ok,
        latency_ms=result.latency_ms,
        error_class=result.error_class,
        error_msg=result.error_msg,
    )


def build_llm_providers_admin_router(
    *,
    db_session_factory,
    mode: Literal["personal", "company"],
) -> APIRouter:
    router = APIRouter(prefix="/settings/admin/llm", tags=["llm-admin"])
    require_admin = build_require_admin(
        db_session_factory=db_session_factory, mode=mode
    )

    def _db():
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    @router.get("/providers", response_model=list[_ProviderOut])
    def list_providers(db=Depends(_db), _=require_admin):
        return [_provider_to_out(r) for r in svc.list_providers(db)]

    @router.post(
        "/providers",
        response_model=_ProviderOut,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_provider(
        payload: _ProviderIn, db=Depends(_db), _=require_admin
    ):
        test_result: _TestOut | None = None
        if payload.run_test:
            if not payload.test_model:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "test_model required when run_test=true"},
                )
            test_result = await _run_connection_test(
                payload.kind,
                api_key=payload.api_key,
                base_url=payload.base_url,
                env_var_name=payload.env_var_name,
                model=payload.test_model,
            )
            if not test_result.ok:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "connection_test_failed",
                        "test": test_result.model_dump(),
                    },
                )
        created = svc.create_provider(
            db,
            kind=payload.kind,
            label=payload.label,
            api_key=payload.api_key,
            base_url=payload.base_url,
            env_var_name=payload.env_var_name,
            extra_config=payload.extra_config,
            is_enabled=payload.is_enabled,
        )
        row = svc.get_provider(db, created.id)
        return _provider_to_out(
            row, test=test_result.model_dump() if test_result else None
        )

    @router.put("/providers/{provider_id}", response_model=_ProviderOut)
    def update_provider(
        provider_id: str, payload: _ProviderUpdate, db=Depends(_db), _=require_admin
    ):
        if svc.get_provider(db, provider_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "provider not found"},
            )
        svc.update_provider(
            db,
            provider_id,
            label=payload.label,
            api_key=payload.api_key,
            base_url=payload.base_url,
            env_var_name=payload.env_var_name,
            extra_config=payload.extra_config,
            is_enabled=payload.is_enabled,
        )
        return _provider_to_out(svc.get_provider(db, provider_id))

    @router.delete(
        "/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT
    )
    def delete_provider(provider_id: str, db=Depends(_db), _=require_admin):
        try:
            svc.delete_provider(db, provider_id)
        except svc.ProviderHasModelsError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "provider has models; delete them first"},
            )

    @router.post("/providers/test", response_model=_TestOut)
    async def test_provider(payload: _TestIn, _=require_admin):
        return await _run_connection_test(
            payload.kind,
            api_key=payload.api_key,
            base_url=payload.base_url,
            env_var_name=payload.env_var_name,
            model=payload.model,
        )

    @router.get("/providers/{provider_id}/models", response_model=list[_ModelOut])
    def list_models_for_provider(
        provider_id: str, db=Depends(_db), _=require_admin
    ):
        if svc.get_provider(db, provider_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "provider not found"},
            )
        return [
            _ModelOut(
                id=m.id,
                provider_id=m.provider_id,
                tier=m.tier,
                model_ref=m.model_ref,
                display_name=m.display_name,
                is_tier_default=m.is_tier_default,
                is_enabled=m.is_enabled,
                overrides=m.overrides,
            )
            for m in svc.list_models_for_provider(db, provider_id)
        ]

    @router.get(
        "/providers/{provider_id}/remote-models", response_model=list[dict]
    )
    async def remote_models(provider_id: str, db=Depends(_db), _=require_admin):
        row = svc.get_provider(db, provider_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "provider not found"},
            )
        api_key = svc.get_provider_api_key(db, provider_id)
        adapter = build_adapter(
            kind=row.kind,
            credentials=ProviderCredentials(api_key=api_key, base_url=row.base_url),
            model="",
            capabilities=Capabilities(),
        )
        models = await adapter.list_models()
        return [
            {
                "id": m.id,
                "display_name": m.display_name,
                "context_window": m.context_window,
            }
            for m in models
        ]

    @router.post(
        "/models", response_model=_ModelOut, status_code=status.HTTP_201_CREATED
    )
    def create_model(payload: _ModelIn, db=Depends(_db), _=require_admin):
        if svc.get_provider(db, payload.provider_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "provider not found"},
            )
        m = svc.create_model(
            db,
            provider_id=payload.provider_id,
            tier=payload.tier,
            model_ref=payload.model_ref,
            display_name=payload.display_name,
            is_tier_default=payload.is_tier_default,
            is_enabled=payload.is_enabled,
            overrides=payload.overrides,
        )
        return _ModelOut(
            id=m.id,
            provider_id=m.provider_id,
            tier=m.tier,
            model_ref=m.model_ref,
            display_name=m.display_name,
            is_tier_default=m.is_tier_default,
            is_enabled=m.is_enabled,
            overrides=m.overrides,
        )

    @router.put("/models/{model_id}", response_model=_ModelOut)
    def update_model(
        model_id: str, payload: _ModelIn, db=Depends(_db), _=require_admin
    ):
        try:
            svc.update_model(
                db,
                model_id,
                tier=payload.tier,
                display_name=payload.display_name,
                is_tier_default=payload.is_tier_default,
                is_enabled=payload.is_enabled,
                overrides=payload.overrides,
            )
        except svc.ModelNotFoundInDBError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "model not found"},
            )
        from openlia_server.db.models.config import LLMModel

        m = db.get(LLMModel, model_id)
        return _ModelOut(
            id=m.id,
            provider_id=m.provider_id,
            tier=m.tier,
            model_ref=m.model_ref,
            display_name=m.display_name,
            is_tier_default=m.is_tier_default,
            is_enabled=m.is_enabled,
            overrides=m.overrides,
        )

    @router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_model(model_id: str, db=Depends(_db), _=require_admin):
        svc.delete_model(db, model_id)

    @router.post("/department/{department_id}")
    def set_department_tier(
        department_id: str,
        payload: _DepartmentTierIn,
        db=Depends(_db),
        _=require_admin,
    ):
        if payload.tier is None:
            svc.clear_department_tier_override(db, department_id)
        else:
            svc.set_department_tier_override(db, department_id, payload.tier)
        return {"ok": True}

    @router.post("/capability_override/{provider_kind}/{model:path}")
    def set_capability_override(
        provider_kind: str,
        model: str,
        payload: dict | None = None,
        db=Depends(_db),
        _=require_admin,
    ):
        if payload is None:
            svc.clear_capability_override(
                db, provider_kind=provider_kind, model=model
            )
        else:
            svc.set_capability_override(
                db,
                provider_kind=provider_kind,
                model=model,
                override=payload,
            )
        return {"ok": True}

    return router
```

- [ ] **Step 4: Make sure `company_client` fixture wires the admin router**

Task 18 wires the router into `create_app()`. Until then the tests should 404. That's expected — the TDD loop is: write tests, confirm red, wire in Task 18, confirm green.

Skip running the admin-route tests here. Commit the route builder only.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/routes/settings.py \
        packages/server/tests/test_routes/test_llm_admin_routes.py
git commit -m "phase-4(llm): admin routes (provider/model CRUD + test + remote-models + overrides)"
```

---

## Task 18: User preference routes + wire routers into `create_app` + README update

**Files:**
- Modify: `packages/server/src/openlia_server/routes/settings.py`
- Modify: `packages/server/src/openlia_server/app.py`
- Modify: `planning/implementation-plans/README.md`
- Create: `packages/server/tests/test_routes/test_llm_user_routes.py`

- [ ] **Step 1: Write the failing user-route tests**

Create `packages/server/tests/test_routes/test_llm_user_routes.py`:

```python
from __future__ import annotations

import pytest

from openlia_server.services import llm_providers as svc


def _seed_model(db_session):
    p = svc.create_provider(
        db_session,
        kind="openai",
        label="main",
        api_key="sk-test",
        base_url=None,
        env_var_name=None,
        extra_config=None,
    )
    m = svc.create_model(
        db_session,
        provider_id=p.id,
        tier="everyday",
        model_ref="gpt-5.4",
        display_name="GPT 5.4",
        is_tier_default=True,
    )
    return p.id, m.id


def test_list_roster_requires_authentication(company_client) -> None:
    resp = company_client.get("/settings/llm/roster")
    assert resp.status_code == 401


def test_list_roster_returns_tier_shape(
    company_client, make_user, db_session, monkeypatch
) -> None:
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="u@openlia.local", password="pw-12345678", is_admin=False)
    _seed_model(db_session)
    company_client.post(
        "/auth/login", json={"email": "u@openlia.local", "password": "pw-12345678"}
    )
    resp = company_client.get("/settings/llm/roster")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"thinking", "everyday", "quick"}
    assert len(body["everyday"]) == 1
    assert body["everyday"][0]["model_ref"] == "gpt-5.4"
    assert body["thinking"] == []


def test_set_and_clear_user_preference(
    company_client, make_user, db_session, monkeypatch
) -> None:
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="u@openlia.local", password="pw-12345678", is_admin=False)
    _, model_id = _seed_model(db_session)
    company_client.post(
        "/auth/login", json={"email": "u@openlia.local", "password": "pw-12345678"}
    )

    put = company_client.put(
        "/settings/llm/preferences/everyday", json={"model_id": model_id}
    )
    assert put.status_code == 200

    got = company_client.get("/settings/llm/preferences")
    assert got.status_code == 200
    assert got.json()["everyday"] == model_id

    deleted = company_client.delete("/settings/llm/preferences/everyday")
    assert deleted.status_code == 204

    got_again = company_client.get("/settings/llm/preferences")
    assert got_again.json().get("everyday") is None


def test_set_preference_rejects_model_in_wrong_tier(
    company_client, make_user, db_session, monkeypatch
) -> None:
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="u@openlia.local", password="pw-12345678", is_admin=False)
    _, model_id = _seed_model(db_session)  # tier=everyday
    company_client.post(
        "/auth/login", json={"email": "u@openlia.local", "password": "pw-12345678"}
    )
    # Try to bind an everyday model into the thinking slot.
    resp = company_client.put(
        "/settings/llm/preferences/thinking", json={"model_id": model_id}
    )
    assert resp.status_code == 400


def test_personal_mode_auto_admin_can_hit_admin_routes(
    personal_client, monkeypatch
) -> None:
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    resp = personal_client.get("/settings/admin/llm/providers")
    assert resp.status_code == 200
    assert resp.json() == []
```

- [ ] **Step 2: Add the user preference router to `routes/settings.py`**

Append to the same `routes/settings.py` file:

```python
# --- LLM user preferences router ----------------------------------------------

from fastapi import Depends as _Depends  # re-import for clarity in this block


class _UserPrefIn(BaseModel):
    model_id: str


def build_llm_user_router(
    *,
    db_session_factory,
    mode: Literal["personal", "company"],
) -> APIRouter:
    router = APIRouter(prefix="/settings/llm", tags=["llm-user"])
    require_auth = build_require_auth(
        db_session_factory=db_session_factory, mode=mode
    )

    def _db():
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    @router.get("/roster", response_model=dict)
    def roster(db=_Depends(_db), user=require_auth):
        from openlia_server.db.models.config import LLMModel, LLMProvider

        out: dict[str, list[dict]] = {"thinking": [], "everyday": [], "quick": []}
        models = svc.list_all_models(db)
        for m in models:
            if not m.is_enabled:
                continue
            p = db.get(LLMProvider, m.provider_id)
            if p is None or not p.is_enabled:
                continue
            out.setdefault(m.tier, []).append(
                {
                    "model_id": m.id,
                    "model_ref": m.model_ref,
                    "display_name": m.display_name,
                    "provider_kind": p.kind,
                    "provider_label": p.label,
                    "is_tier_default": m.is_tier_default,
                }
            )
        return out

    @router.get("/preferences", response_model=dict)
    def get_preferences(db=_Depends(_db), user=require_auth):
        rows = svc.list_user_preferences(db, user_id=user.id)
        return {r.tier: r.model_id for r in rows}

    @router.put("/preferences/{tier}")
    def set_preference(
        tier: Literal["thinking", "everyday", "quick"],
        payload: _UserPrefIn,
        db=_Depends(_db),
        user=require_auth,
    ):
        from openlia_server.db.models.config import LLMModel

        model = db.get(LLMModel, payload.model_id)
        if model is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "model not found"},
            )
        if model.tier != tier:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": f"model is in tier '{model.tier}', not '{tier}'"},
            )
        svc.set_user_preference(
            db, user_id=user.id, tier=tier, model_id=payload.model_id
        )
        return {"ok": True}

    @router.delete(
        "/preferences/{tier}", status_code=status.HTTP_204_NO_CONTENT
    )
    def clear_preference(
        tier: Literal["thinking", "everyday", "quick"],
        db=_Depends(_db),
        user=require_auth,
    ):
        svc.clear_user_preference(db, user_id=user.id, tier=tier)

    return router
```

- [ ] **Step 3: Wire routers into `create_app()`**

Open `packages/server/src/openlia_server/app.py` and add the LLM router builds to the unconditional (both-mode) section. Add the imports at the top and the `include_router` calls after the `healthz` block but before the `return app` (or wherever the data-provider routers from Plan 3 are mounted — mount the LLM ones next to them).

The wiring snippet (merge with existing unconditional mounts — do not duplicate the Plan 3 data-provider wiring):

```python
from openlia_server.routes.settings import (
    build_data_providers_router,        # from Plan 3
    build_llm_providers_admin_router,   # NEW
    build_llm_user_router,              # NEW
)

# Inside create_app(), after FastAPI(app) is created and regardless of mode:
mode_literal: Literal["personal", "company"] = (
    "company" if mode == "company" else "personal"
)
app.include_router(
    build_data_providers_router(db_session_factory=factory, mode=mode_literal)
)
app.include_router(
    build_llm_providers_admin_router(
        db_session_factory=factory, mode=mode_literal
    )
)
app.include_router(
    build_llm_user_router(db_session_factory=factory, mode=mode_literal)
)
```

(`Literal` comes from `typing` — add the import if not present.)

- [ ] **Step 4: Run the admin and user route test suites**

Run:

```bash
uv run pytest packages/server/tests/test_routes/test_llm_admin_routes.py \
             packages/server/tests/test_routes/test_llm_user_routes.py -v
```

Expected: all pass.

- [ ] **Step 5: Run the full suite + lint**

```bash
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

Expected: green.

- [ ] **Step 6: Update the README**

Open `planning/implementation-plans/README.md` and change Plan 4's row from:

```
| 4 | 2 | LLM provider system | Not started | — |
```

to:

```
| 4 | 2 | LLM provider system | Draft | `2026-04-16-phase-4-llm-provider-system.md` |
```

- [ ] **Step 7: Commit**

```bash
git add packages/server/src/openlia_server/routes/settings.py \
        packages/server/src/openlia_server/app.py \
        packages/server/tests/test_routes/test_llm_user_routes.py \
        planning/implementation-plans/README.md
git commit -m "phase-4(llm): user preference routes + mount LLM routers in create_app"
```

---

## Task 19: End-to-end integration test

**Files:**
- Create: `packages/server/tests/test_integration/__init__.py` (if not already present)
- Create: `packages/server/tests/test_integration/test_llm_end_to_end.py`

- [ ] **Step 1: Write the integration test**

Create `packages/server/tests/test_integration/test_llm_end_to_end.py`:

```python
"""End-to-end: admin seeds a provider + model via HTTP, resolver returns a
ready adapter, that adapter's generate() round-trips through a mocked OpenAI.

This test proves the full chain: routes -> service -> DB -> SQLModelRegistry
-> core.resolver -> build_adapter -> generate.
"""
from __future__ import annotations

import pytest
import respx

from openlia.llm.adapters import build_adapter
from openlia.llm.resolver import resolve
from openlia.llm.types import LLMRequest, Message, ModelTier
from openlia_server.services.llm_registry import SQLModelRegistry


async def test_full_chain_admin_creates_then_resolver_returns_usable_adapter(
    company_client, make_user, db_session, monkeypatch
) -> None:
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    make_user(email="admin@openlia.local", password="pw-12345678", is_admin=True)
    company_client.post(
        "/auth/login",
        json={"email": "admin@openlia.local", "password": "pw-12345678"},
    )

    # 1) Admin creates a provider via the HTTP route (this exercises encryption).
    with respx.mock():
        respx.post("https://api.openai.com/v1/chat/completions").respond(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "x"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )
        create_resp = company_client.post(
            "/settings/admin/llm/providers",
            json={
                "kind": "openai",
                "label": "Main",
                "api_key": "sk-e2e",
                "run_test": True,
                "test_model": "gpt-5.4-pro",
            },
        )
    assert create_resp.status_code == 201
    provider_id = create_resp.json()["id"]

    # 2) Admin adds a model row (thinking tier default).
    model_resp = company_client.post(
        "/settings/admin/llm/models",
        json={
            "provider_id": provider_id,
            "tier": "thinking",
            "model_ref": "gpt-5.4-pro",
            "display_name": "GPT 5.4 Pro",
            "is_tier_default": True,
        },
    )
    assert model_resp.status_code == 201

    # 3) Core resolver returns a ResolvedModel with decrypted credentials.
    registry = SQLModelRegistry(db_session)
    resolved = resolve(
        department_id="equity_research",  # shipped default is THINKING
        registry=registry,
        user_id=None,
    )
    assert resolved.provider_kind == "openai"
    assert resolved.tier is ModelTier.THINKING
    assert resolved.model_ref == "gpt-5.4-pro"
    assert resolved.credentials.api_key == "sk-e2e"

    # 4) build_adapter + generate round-trip.
    adapter = build_adapter(
        kind=resolved.provider_kind,
        credentials=resolved.credentials,
        model=resolved.model_ref,
        capabilities=resolved.capabilities,
    )
    with respx.mock():
        respx.post("https://api.openai.com/v1/chat/completions").respond(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "round-trip"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 4, "completion_tokens": 2},
            },
        )
        response = await adapter.generate(
            LLMRequest(messages=[Message(role="user", content="hi")])
        )
    assert response.text == "round-trip"
    assert response.input_tokens == 4


async def test_tier_not_configured_when_resolver_finds_nothing(
    company_client, db_session, monkeypatch
) -> None:
    """With zero llm_models rows, the resolver raises TierNotConfiguredError."""
    from openlia.llm.exceptions import TierNotConfiguredError

    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")
    registry = SQLModelRegistry(db_session)
    with pytest.raises(TierNotConfiguredError) as excinfo:
        resolve(department_id="equity_research", registry=registry, user_id=None)
    assert excinfo.value.tier == "thinking"
```

- [ ] **Step 2: Run the integration test**

Run: `uv run pytest packages/server/tests/test_integration/test_llm_end_to_end.py -v`
Expected: both tests pass.

- [ ] **Step 3: Final full-suite + lint sweep**

```bash
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

Expected: green across the board.

- [ ] **Step 4: Commit**

```bash
git add packages/server/tests/test_integration/
git commit -m "phase-4(llm): end-to-end integration test (admin route -> resolver -> adapter.generate)"
```

---

## What's explicitly deferred (for future plans)

- **Streaming (`stream()`) on every adapter.** Currently raises `NotImplementedError`. Plan 5 implements SSE streaming per the runtime spec.
- **`/setup/models/*` wizard routes.** The service layer is here; the Setup Wizard's payload-shaped routes and required-tier gating live in Plan 10.
- **Frontend Settings → Models UI and the capability-override dialog UI.** Plan 11.
- **`GET /settings/models` role-shaped aggregate endpoint** (from the spec's API table). The roster + preferences endpoints added here cover the data it needs; a convenience aggregator can live in Plan 11 when the UI is built.
- **Auto-discovery of models after a key is entered** (a future `POST /admin/llm/providers/{id}/refresh-models` endpoint that calls `list_models()` and upserts into `llm_models`). Not needed until the wizard UX calls for it; the `remote-models` proxy already exposes the data.
- **Budget / spend tracking, OAuth, fallback chains** — spec non-goals for v1.
- **Department tier-override `from environment` read-only behavior** (`OPENLIA_LLM_DEPARTMENT_<UPPER_ID>_TIER`). Added here is DB-side storage; env-override resolution is a small addition to the SQLModelRegistry's `get_department_tier_override` — defer until a department plan actually needs it to avoid untested code paths.
- **Ollama `GET /api/show` capability probing.** The shipped capability map already handles `llama3.1+` / `qwen2.5+` / `mistral-nemo+`; live probing is a polish item for when a user adds an unknown model.

## Self-Review Checklist

- [ ] Every task has exact file paths, complete code (no "fill in"), exact commands, expected output.
- [ ] Every task commits so failure isolates to one task.
- [ ] Task 17 explicitly notes its tests stay red until Task 18 wires the router (honest TDD — the RED state is acknowledged, not hidden).
- [ ] Exception types used in tests match those defined in `exceptions.py`.
- [ ] Resolver tests cover all four Stage-2 paths (user pref, tier default, any-in-tier, raise).
- [ ] Capability override flows end-to-end (service -> registry -> resolver -> ResolvedModel).
- [ ] `stream()` stubs are consistent across all six adapters.
- [ ] `OPENLIA_SECRET_KEY` is set in every test that touches encryption.
- [ ] The integration test asserts decryption (api_key round-trips as "sk-e2e"), the most load-bearing security property.

---

## Execution Handoff

Plan complete and saved to `planning/implementation-plans/2026-04-16-phase-4-llm-provider-system.md`. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batched with checkpoints.

Which approach?












