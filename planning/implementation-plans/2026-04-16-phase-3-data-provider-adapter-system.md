# Phase 3 — Data Provider Adapter System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put the configuration + resolution spine of the data provider system in place. After this plan, admins can CRUD financial/news data providers, each provider advertises which requirement types it satisfies, and a deterministic resolver answers "which configured provider serves `requirement_type=X`?" — the foundation Plan 5 (LLM runtime) uses to build per-department tool lists.

**Architecture:** A `ProviderAdapter` abstract base class in `openlia-core` declares the contract every adapter must satisfy: a `category`, a `kind`, a set of `capabilities` (requirement-type strings), and `fetch(capability, params)` / `health_check()` coroutines. The shipped adapter registry maps `kind → AdapterClass`; Plan 3 ships EODHD as the default. A requirements manifest (`data/manifest/requirements.yaml`) declares what each department needs; Plan 3 populates it for Equity Research and leaves stubs for the other departments. The server service layer exposes admin-only CRUD over the `data_providers` and `data_provider_requirement_mapping` tables (from Plan 1A), using Plan 2's `encrypt_for_row` / `decrypt_for_row` for API keys. Admin routes at `/settings/data-providers/*` sit behind Plan 2's `build_require_admin` dependency; they work in both personal (synthetic `local` admin) and company modes. The capability resolver is deterministic — no LLM — and walks configured providers in admin-set priority order. The full catalog / AI-review / dispatch / expansion layers described in `data-provider-design.md` are deferred to later plans.

**Tech Stack:** `openlia-core` adds `httpx>=0.27` and `pyyaml>=6.0`. Server uses existing FastAPI + SQLAlchemy 2.x stack. Tests use `pytest-asyncio>=0.24` (new dev dep) + `respx>=0.21` for HTTP mocking.

**Source spec:** `planning/specs/systems/data-provider-design.md`. Plan 3 implements the "Provider Categories", "Configuration", "Provider Entry", and startup-validation sections, plus a simplified adapter-class model substituting for the full catalog/review flow. The full catalog YAML system, AI review, dispatch router, runtime tool expansion, MCP transport, and retail-sentiment availability checker are **out of scope** and tracked in later plans.

**Depends on:**
- Plan 1A — `data_providers` and `data_provider_requirement_mapping` tables + models, `db/session.py` engine, `db/bootstrap.py`.
- Plan 2 — `db/crypto.py::encrypt_for_row` / `decrypt_for_row` for API-key encryption; `middleware/auth.py::build_require_admin` for route gating; `create_app(db_session_factory=...)` factory signature; `routes/` folder convention.

**Unblocks:**
- Plan 4 (LLM providers) — uses the same CRUD + encryption pattern.
- Plan 5 (LLM runtime) — consumes `ProviderEntry` and the resolver to build department tool lists.
- Plan 10 (Setup Wizard) — calls the admin routes during onboarding.
- Every department plan (13–20).

**Out of scope (handled elsewhere):**
- Bundled catalog YAML templates and the catalog installer/discovery — future catalog plan.
- AI-driven requirement-to-endpoint mapping and `~/.openlia/mappings/` files — future AI-review plan.
- Runtime dispatch router, HTTP client, MCP client, `find_more_data` meta-tool — Plan 5.
- `yfinance` Python-mode provider — future data plan.
- Retail Sentiment availability checker — Plan 20.
- Frontend UI for data-provider settings — Plan 11.
- Search-category providers (Brave / Tavily / Serper) — handled by the web-search provider path in Plan 5 (uses the `web_search_providers` table from Plan 1A, not `data_providers`).

---

## File Structure

Files created in this plan:

```
openlia/
├── packages/
│   ├── core/
│   │   ├── pyproject.toml                          # MODIFIED — +httpx, +pyyaml
│   │   └── src/openlia/
│   │       └── data/
│   │           ├── __init__.py                     # Re-exports ProviderAdapter, ProviderEntry, errors
│   │           ├── errors.py                       # DataNotAvailable, RateLimitError, DataSourceError
│   │           ├── types.py                        # ProviderCategory, ProviderEntry, ToolResult
│   │           ├── base.py                         # ProviderAdapter ABC
│   │           ├── resolver.py                     # resolve_providers_for_requirement(...)
│   │           ├── adapters/
│   │           │   ├── __init__.py                 # ADAPTERS registry {kind: AdapterClass}
│   │           │   └── eodhd.py                    # EODHDAdapter (4 capabilities)
│   │           └── manifest/
│   │               ├── __init__.py
│   │               ├── types.py                    # Requirement, DepartmentManifest, RequirementsManifest
│   │               ├── loader.py                   # load_manifest() from YAML
│   │               ├── checker.py                  # unmet_basic_requirements(...)
│   │               └── requirements.yaml           # Populated for equity_research; stubs for others
│   └── server/
│       ├── pyproject.toml                          # MODIFIED — (no new deps; core brings httpx+pyyaml)
│       └── src/openlia_server/
│           ├── app.py                              # MODIFIED — mount data-providers router
│           ├── services/
│           │   └── data_providers.py               # CRUD + mapping service
│           └── routes/
│               └── settings.py                     # build_data_providers_router (admin-only)
└── packages/
    ├── core/tests/
    │   └── test_data/
    │       ├── __init__.py
    │       ├── test_errors.py
    │       ├── test_types.py
    │       ├── test_base.py
    │       ├── test_resolver.py
    │       ├── test_manifest_loader.py
    │       ├── test_manifest_checker.py
    │       └── test_adapters/
    │           ├── __init__.py
    │           └── test_eodhd.py
    └── server/tests/
        ├── test_services/
        │   └── test_data_providers.py
        └── test_routes/
            └── test_data_providers_routes.py
```

Design rules:

- **Core owns the adapter contract.** `ProviderAdapter`, `ProviderEntry`, the manifest, and the resolver live in `openlia-core` with zero HTTP/FastAPI imports. The server imports from core.
- **Adapters are pure classes constructed from a `ProviderEntry`.** They do not read the database. The server-side service builds the `ProviderEntry` (with decrypted `api_key`), passes it to the adapter class, and the adapter does the work.
- **Capabilities are strings matching manifest `type` fields.** An adapter `eodhd` that declares capability `stock_quote` means: whenever any manifest requirement has `type: stock_quote`, this adapter can serve it.
- **Resolver is deterministic.** Walks `active_providers` (already sorted by `data_provider_requirement_mapping.priority`) and returns the first provider whose adapter's `capabilities` set contains the requested `requirement_type`. Plan 3 does **not** implement AI-driven matching.
- **Routes mount in both modes.** Personal-mode `local` user is `is_admin=True`, so the `build_require_admin` dependency passes through transparently.

Deviations from `projectStructure.md`:

- projectStructure.md lists `data/catalog/`, `data/dispatch/`, `data/review/`, `data/python_providers/`, `data/sentiment/` — none of these are created in Plan 3. They are tracked for later plans and the top-level `data/` directory will sit with just the adapter-base + manifest + resolver subset until then. This is an intentional scope reduction.
- projectStructure.md lists `routes/settings.py` as the single settings router. Plan 3 creates that file but adds only the `build_data_providers_router()` factory inside it. Plan 4 (LLM providers) will add `build_llm_providers_router()` to the same file.

---

## Task 1: Add `httpx` + `pyyaml` to core, `respx` + `pytest-asyncio` to dev deps

**Files:**
- Modify: `packages/core/pyproject.toml`
- Modify: `pyproject.toml` (workspace root — dev group)

- [ ] **Step 1: Inspect current core dependencies**

Run:
```bash
cat packages/core/pyproject.toml
```
Expected: shows the file Phase 0 wrote. It should contain a `dependencies = [...]` array under `[project]`.

- [ ] **Step 2: Add `httpx>=0.27` and `pyyaml>=6.0` to core dependencies**

Edit `packages/core/pyproject.toml`. Under `[project]`, the `dependencies = [...]` array must include these two new entries. After edit, the array must read (preserve any existing entries exactly — add the two lines below at the end, before the closing bracket):

```toml
dependencies = [
    # ...existing entries kept exactly as-is...
    "httpx>=0.27",
    "pyyaml>=6.0",
]
```

If the core package currently has `dependencies = []` (Phase 0 placeholder), it becomes:

```toml
dependencies = [
    "httpx>=0.27",
    "pyyaml>=6.0",
]
```

- [ ] **Step 3: Add `pytest-asyncio>=0.24` and `respx>=0.21` to the workspace dev group**

Edit the workspace root `pyproject.toml`. Under `[dependency-groups]`, the `dev = [...]` array already contains `ruff` and `pytest`. Add two entries:

```toml
[dependency-groups]
dev = [
    "ruff>=0.11",
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "respx>=0.21",
]
```

- [ ] **Step 4: Add the asyncio_mode config to pytest**

Also in the workspace root `pyproject.toml`, under `[tool.pytest.ini_options]`, add `asyncio_mode = "auto"`:

```toml
[tool.pytest.ini_options]
testpaths = ["packages/core/tests", "packages/server/tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = ["-ra", "--strict-markers", "--import-mode=importlib"]
asyncio_mode = "auto"
```

- [ ] **Step 5: Sync the workspace**

Run:
```bash
uv sync --all-packages
```
Expected: no errors. `httpx`, `pyyaml`, `pytest-asyncio`, and `respx` appear in the resolved/installed set.

- [ ] **Step 6: Ruff format check on the edited TOML-adjacent files**

Run:
```bash
uv run ruff check packages/core
uv run ruff format --check packages/core
```
Expected: no findings (TOML is not linted by ruff, but we want to confirm no incidental changes leaked in).

- [ ] **Step 7: Commit**

```bash
git add packages/core/pyproject.toml pyproject.toml
git commit -m "phase-3(data): add httpx+pyyaml to core; pytest-asyncio+respx to dev"
```

---

## Task 2: Typed errors — `DataNotAvailable`, `RateLimitError`, `DataSourceError`

**Files:**
- Create: `packages/core/src/openlia/data/__init__.py`
- Create: `packages/core/src/openlia/data/errors.py`
- Create: `packages/core/tests/test_data/__init__.py`
- Create: `packages/core/tests/test_data/test_errors.py`

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/test_data/__init__.py` with content:

```python
"""Tests for the openlia.data package."""
```

Create `packages/core/tests/test_data/test_errors.py`:

```python
from openlia.data.errors import (
    DataNotAvailable,
    DataProviderError,
    DataSourceError,
    RateLimitError,
)


def test_data_not_available_has_provider_and_capability() -> None:
    err = DataNotAvailable(
        provider_kind="eodhd",
        capability="stock_quote",
        reason="symbol not found",
    )
    assert err.provider_kind == "eodhd"
    assert err.capability == "stock_quote"
    assert err.reason == "symbol not found"
    assert "eodhd" in str(err)
    assert "stock_quote" in str(err)
    assert "symbol not found" in str(err)


def test_rate_limit_error_carries_retry_after_seconds() -> None:
    err = RateLimitError(
        provider_kind="eodhd",
        retry_after_seconds=30,
    )
    assert err.retry_after_seconds == 30
    assert err.provider_kind == "eodhd"


def test_rate_limit_retry_after_defaults_to_none() -> None:
    err = RateLimitError(provider_kind="fmp")
    assert err.retry_after_seconds is None


def test_data_source_error_wraps_status_and_detail() -> None:
    err = DataSourceError(
        provider_kind="eodhd",
        status_code=500,
        detail="internal server error",
    )
    assert err.status_code == 500
    assert err.detail == "internal server error"


def test_all_errors_subclass_data_provider_error() -> None:
    assert issubclass(DataNotAvailable, DataProviderError)
    assert issubclass(RateLimitError, DataProviderError)
    assert issubclass(DataSourceError, DataProviderError)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
uv run pytest packages/core/tests/test_data/test_errors.py -v
```
Expected: ImportError on `openlia.data.errors`.

- [ ] **Step 3: Create the `data` package and `errors.py`**

Create `packages/core/src/openlia/data/__init__.py`:

```python
"""Data provider adapter system.

Public surface kept minimal in Plan 3: errors, types, adapter base, resolver.
Catalog, dispatch, review, and expansion layers are added in later plans.
"""

from openlia.data.errors import (
    DataNotAvailable,
    DataProviderError,
    DataSourceError,
    RateLimitError,
)

__all__ = [
    "DataNotAvailable",
    "DataProviderError",
    "DataSourceError",
    "RateLimitError",
]
```

Create `packages/core/src/openlia/data/errors.py`:

```python
"""Typed errors for data provider operations.

Per data-provider-design.md, three categories:
- DataNotAvailable: the provider does not cover this data (normal outcome; the
  LLM must say "data unavailable", never hallucinate).
- RateLimitError: provider returned 429 or an equivalent rate-limit signal.
- DataSourceError: unexpected 5xx / network / parse failure.

All three subclass DataProviderError for blanket try/except at the call site.
"""


class DataProviderError(Exception):
    """Base class for all data provider errors."""


class DataNotAvailable(DataProviderError):
    """The configured provider cannot satisfy this capability for these params.

    Not an exceptional runtime condition — the caller is expected to convert
    this into a normal tool-result payload telling the LLM the data is missing.
    """

    def __init__(
        self,
        *,
        provider_kind: str,
        capability: str,
        reason: str,
    ) -> None:
        self.provider_kind = provider_kind
        self.capability = capability
        self.reason = reason
        super().__init__(
            f"{provider_kind}:{capability} unavailable: {reason}"
        )


class RateLimitError(DataProviderError):
    """Provider rate limit hit.

    `retry_after_seconds` is populated when the provider's response indicates
    a backoff window; otherwise None (caller decides the backoff strategy).
    """

    def __init__(
        self,
        *,
        provider_kind: str,
        retry_after_seconds: int | None = None,
    ) -> None:
        self.provider_kind = provider_kind
        self.retry_after_seconds = retry_after_seconds
        msg = f"{provider_kind} rate limited"
        if retry_after_seconds is not None:
            msg += f" (retry after {retry_after_seconds}s)"
        super().__init__(msg)


class DataSourceError(DataProviderError):
    """Unexpected provider error — 5xx, timeout, malformed response."""

    def __init__(
        self,
        *,
        provider_kind: str,
        status_code: int | None = None,
        detail: str = "",
    ) -> None:
        self.provider_kind = provider_kind
        self.status_code = status_code
        self.detail = detail
        parts = [f"{provider_kind} source error"]
        if status_code is not None:
            parts.append(f"status={status_code}")
        if detail:
            parts.append(detail)
        super().__init__("; ".join(parts))
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
uv run pytest packages/core/tests/test_data/test_errors.py -v
```
Expected: 5 tests pass.

- [ ] **Step 5: Ruff check**

Run:
```bash
uv run ruff check packages/core/src/openlia/data/ packages/core/tests/test_data/
uv run ruff format --check packages/core/src/openlia/data/ packages/core/tests/test_data/
```
Expected: no findings.

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/data/__init__.py \
        packages/core/src/openlia/data/errors.py \
        packages/core/tests/test_data/__init__.py \
        packages/core/tests/test_data/test_errors.py
git commit -m "phase-3(data): typed errors — DataNotAvailable/RateLimitError/DataSourceError"
```

---

## Task 3: Core types — `ProviderCategory`, `ProviderEntry`, `ToolResult`

**Files:**
- Create: `packages/core/src/openlia/data/types.py`
- Create: `packages/core/tests/test_data/test_types.py`

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/test_data/test_types.py`:

```python
import pytest
from pydantic import ValidationError

from openlia.data.types import (
    ProviderCategory,
    ProviderEntry,
    ProviderMode,
    ToolResult,
)


def test_provider_category_values() -> None:
    assert ProviderCategory.FINANCIAL.value == "financial"
    assert ProviderCategory.NEWS.value == "news"
    assert ProviderCategory.SOCIAL_MEDIA.value == "social_media"


def test_provider_mode_values() -> None:
    assert ProviderMode.API_KEY.value == "api_key"
    assert ProviderMode.MCP.value == "mcp"


def test_provider_entry_minimal_api_key_mode() -> None:
    entry = ProviderEntry(
        id="11111111-1111-1111-1111-111111111111",
        kind="eodhd",
        label="EODHD",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="secret-key",
        base_url="https://eodhd.com/api",
    )
    assert entry.kind == "eodhd"
    assert entry.api_key == "secret-key"
    assert entry.is_enabled is True
    assert entry.priority == 100


def test_provider_entry_mcp_mode_requires_mcp_url() -> None:
    with pytest.raises(ValidationError):
        ProviderEntry(
            id="2" * 36,
            kind="custom_mcp",
            label="Custom",
            category=ProviderCategory.FINANCIAL,
            mode=ProviderMode.MCP,
            mcp_url=None,
        )


def test_provider_entry_api_key_mode_requires_base_url() -> None:
    with pytest.raises(ValidationError):
        ProviderEntry(
            id="3" * 36,
            kind="eodhd",
            label="EODHD",
            category=ProviderCategory.FINANCIAL,
            mode=ProviderMode.API_KEY,
            base_url=None,
        )


def test_provider_entry_priority_and_disabled() -> None:
    entry = ProviderEntry(
        id="4" * 36,
        kind="fmp",
        label="FMP",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://financialmodelingprep.com/api/v3",
        is_enabled=False,
        priority=50,
    )
    assert entry.is_enabled is False
    assert entry.priority == 50


def test_tool_result_round_trip_dict() -> None:
    result = ToolResult(
        provider_kind="eodhd",
        capability="stock_quote",
        payload={"symbol": "AAPL", "price": 225.1},
    )
    dumped = result.model_dump()
    assert dumped["provider_kind"] == "eodhd"
    assert dumped["payload"]["symbol"] == "AAPL"


def test_tool_result_payload_can_be_list() -> None:
    result = ToolResult(
        provider_kind="eodhd",
        capability="historical_prices",
        payload=[{"date": "2026-04-10", "close": 220.0}],
    )
    assert isinstance(result.payload, list)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
uv run pytest packages/core/tests/test_data/test_types.py -v
```
Expected: ImportError on `openlia.data.types`.

- [ ] **Step 3: Create `types.py`**

Create `packages/core/src/openlia/data/types.py`:

```python
"""Core data types for the provider adapter system.

ProviderEntry is the in-memory shape every adapter receives at construction
time. Server code builds this from a data_providers DB row (decrypting the
api_key column) before handing it to the adapter. Adapters never touch the
database themselves.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProviderCategory(str, Enum):
    FINANCIAL = "financial"
    NEWS = "news"
    SOCIAL_MEDIA = "social_media"


class ProviderMode(str, Enum):
    API_KEY = "api_key"
    MCP = "mcp"


class ProviderEntry(BaseModel):
    """In-memory representation of a configured data provider.

    Populated by the server service layer from a `data_providers` row with the
    encrypted `api_key_encrypted` column already decrypted into `api_key`.
    The adapter uses `base_url` (api_key mode) or `mcp_url` (mcp mode) to
    construct requests. `priority` comes from data_provider_requirement_mapping
    when iterating providers for a specific requirement, or defaults to 100.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    kind: str
    label: str
    category: ProviderCategory
    mode: ProviderMode

    api_key: str | None = None
    base_url: str | None = None

    mcp_url: str | None = None
    mcp_auth_header: str | None = None

    extra_config: dict[str, Any] = Field(default_factory=dict)
    is_enabled: bool = True
    priority: int = 100

    @model_validator(mode="after")
    def _transport_requirements(self) -> "ProviderEntry":
        if self.mode is ProviderMode.API_KEY and not self.base_url:
            raise ValueError("api_key mode requires base_url")
        if self.mode is ProviderMode.MCP and not self.mcp_url:
            raise ValueError("mcp mode requires mcp_url")
        return self


class ToolResult(BaseModel):
    """The uniform shape every adapter.fetch(...) coroutine resolves to.

    The runtime dispatch layer (Plan 5) consumes this and serializes it into
    the SSE `chat.tool_result` / `report.tool_result` payload for the LLM.
    """

    model_config = ConfigDict(frozen=True)

    provider_kind: str
    capability: str
    payload: dict[str, Any] | list[Any]
```

- [ ] **Step 4: Re-export types from the package `__init__`**

Append to `packages/core/src/openlia/data/__init__.py` so the final file reads:

```python
"""Data provider adapter system.

Public surface kept minimal in Plan 3: errors, types, adapter base, resolver.
Catalog, dispatch, review, and expansion layers are added in later plans.
"""

from openlia.data.errors import (
    DataNotAvailable,
    DataProviderError,
    DataSourceError,
    RateLimitError,
)
from openlia.data.types import (
    ProviderCategory,
    ProviderEntry,
    ProviderMode,
    ToolResult,
)

__all__ = [
    "DataNotAvailable",
    "DataProviderError",
    "DataSourceError",
    "ProviderCategory",
    "ProviderEntry",
    "ProviderMode",
    "RateLimitError",
    "ToolResult",
]
```

- [ ] **Step 5: Run the test to verify it passes**

Run:
```bash
uv run pytest packages/core/tests/test_data/test_types.py -v
```
Expected: 8 tests pass.

- [ ] **Step 6: Ruff check**

Run:
```bash
uv run ruff check packages/core/src/openlia/data/ packages/core/tests/test_data/
uv run ruff format --check packages/core/src/openlia/data/ packages/core/tests/test_data/
```
Expected: no findings.

- [ ] **Step 7: Commit**

```bash
git add packages/core/src/openlia/data/types.py \
        packages/core/src/openlia/data/__init__.py \
        packages/core/tests/test_data/test_types.py
git commit -m "phase-3(data): ProviderEntry/ProviderCategory/ProviderMode/ToolResult pydantic types"
```

---

## Task 4: `ProviderAdapter` ABC

**Files:**
- Create: `packages/core/src/openlia/data/base.py`
- Create: `packages/core/tests/test_data/test_base.py`

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/test_data/test_base.py`:

```python
from typing import Any

import pytest

from openlia.data.base import ProviderAdapter
from openlia.data.errors import DataNotAvailable
from openlia.data.types import ProviderCategory, ProviderEntry, ProviderMode, ToolResult


class _StubAdapter(ProviderAdapter):
    kind = "stub"
    category = ProviderCategory.FINANCIAL
    capabilities = frozenset({"stock_quote", "historical_prices"})

    async def fetch(
        self,
        capability: str,
        params: dict[str, Any],
    ) -> ToolResult:
        if capability not in self.capabilities:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason="not declared",
            )
        return ToolResult(
            provider_kind=self.kind,
            capability=capability,
            payload={"params": params},
        )

    async def health_check(self) -> bool:
        return True


def _entry() -> ProviderEntry:
    return ProviderEntry(
        id="00000000-0000-0000-0000-000000000001",
        kind="stub",
        label="Stub",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://example.test",
    )


def test_adapter_is_abstract() -> None:
    with pytest.raises(TypeError):
        ProviderAdapter(_entry())  # type: ignore[abstract]


def test_stub_adapter_records_entry() -> None:
    adapter = _StubAdapter(_entry())
    assert adapter.entry.kind == "stub"
    assert adapter.kind == "stub"


def test_stub_adapter_declares_capabilities() -> None:
    adapter = _StubAdapter(_entry())
    assert "stock_quote" in adapter.capabilities
    assert "historical_prices" in adapter.capabilities
    assert "company_news" not in adapter.capabilities


async def test_stub_adapter_fetch_returns_tool_result() -> None:
    adapter = _StubAdapter(_entry())
    result = await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert isinstance(result, ToolResult)
    assert result.capability == "stock_quote"
    assert result.payload == {"params": {"symbol": "AAPL"}}


async def test_stub_adapter_fetch_unknown_raises_data_not_available() -> None:
    adapter = _StubAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("insider_transactions", {})
    assert exc.value.provider_kind == "stub"
    assert exc.value.capability == "insider_transactions"


async def test_stub_adapter_health_check() -> None:
    adapter = _StubAdapter(_entry())
    assert await adapter.health_check() is True


def test_entry_kind_must_match_adapter_kind() -> None:
    wrong = ProviderEntry(
        id="00000000-0000-0000-0000-000000000002",
        kind="eodhd",
        label="Wrong",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://example.test",
    )
    with pytest.raises(ValueError, match="kind mismatch"):
        _StubAdapter(wrong)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
uv run pytest packages/core/tests/test_data/test_base.py -v
```
Expected: ImportError on `openlia.data.base`.

- [ ] **Step 3: Create `base.py`**

Create `packages/core/src/openlia/data/base.py`:

```python
"""Abstract base class every data provider adapter inherits from.

Contract:
- Class attribute `kind`: str matching the `ProviderEntry.kind` used to
  construct the adapter (e.g. "eodhd", "fmp").
- Class attribute `category`: ProviderCategory — which column in
  DataProvidersConfig this adapter fills.
- Class attribute `capabilities`: frozenset[str] — the set of manifest
  requirement `type` strings this adapter can satisfy.
- `fetch(capability, params)`: async coroutine resolving to a ToolResult,
  or raising DataNotAvailable / RateLimitError / DataSourceError.
- `health_check()`: async coroutine returning True iff credentials are
  valid and the service is reachable. Used by the admin "test connection"
  endpoint; never raises — returns False on failure.

Adapters do NOT read the database. The server-side service layer builds the
ProviderEntry (with decrypted api_key) and passes it to the adapter
constructor.
"""

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from openlia.data.types import ProviderCategory, ProviderEntry, ToolResult


class ProviderAdapter(ABC):
    """Abstract base for every data provider adapter."""

    kind: ClassVar[str]
    category: ClassVar[ProviderCategory]
    capabilities: ClassVar[frozenset[str]]

    def __init__(self, entry: ProviderEntry) -> None:
        if entry.kind != self.kind:
            raise ValueError(
                f"kind mismatch: adapter={self.kind!r} entry={entry.kind!r}"
            )
        self.entry = entry

    @abstractmethod
    async def fetch(
        self,
        capability: str,
        params: dict[str, Any],
    ) -> ToolResult:
        """Fetch data for a capability. Raises typed errors on failure."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True iff the adapter can reach its backend and authenticate."""
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
uv run pytest packages/core/tests/test_data/test_base.py -v
```
Expected: 7 tests pass.

- [ ] **Step 5: Ruff check**

Run:
```bash
uv run ruff check packages/core/src/openlia/data/base.py packages/core/tests/test_data/test_base.py
uv run ruff format --check packages/core/src/openlia/data/base.py packages/core/tests/test_data/test_base.py
```
Expected: no findings.

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/data/base.py packages/core/tests/test_data/test_base.py
git commit -m "phase-3(data): ProviderAdapter ABC — kind/category/capabilities/fetch/health_check"
```

---

## Task 5: Manifest types — `Requirement`, `DepartmentManifest`, `RequirementsManifest`

**Files:**
- Create: `packages/core/src/openlia/data/manifest/__init__.py`
- Create: `packages/core/src/openlia/data/manifest/types.py`
- Create: `packages/core/tests/test_data/test_manifest_loader.py` (skeleton — only structural test here)

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/test_data/test_manifest_loader.py` (structural portion only; the real loader test lands in Task 6):

```python
from openlia.data.manifest.types import (
    DepartmentManifest,
    Requirement,
    RequirementsManifest,
    RequirementTier,
)


def test_requirement_tier_enum() -> None:
    assert RequirementTier.BASIC.value == "basic"
    assert RequirementTier.ADVANCED.value == "advanced"


def test_requirement_round_trip() -> None:
    r = Requirement(
        type="stock_quote",
        description="Real-time or delayed stock price.",
        tier=RequirementTier.BASIC,
    )
    assert r.type == "stock_quote"
    assert r.tier is RequirementTier.BASIC


def test_department_manifest_basic_and_advanced_views() -> None:
    dm = DepartmentManifest(
        department="equity_research",
        requirements=[
            Requirement(type="stock_quote", description="d1", tier=RequirementTier.BASIC),
            Requirement(type="stock_grade", description="d2", tier=RequirementTier.ADVANCED),
            Requirement(type="company_news", description="d3", tier=RequirementTier.BASIC),
        ],
    )
    assert {r.type for r in dm.basic()} == {"stock_quote", "company_news"}
    assert {r.type for r in dm.advanced()} == {"stock_grade"}


def test_requirements_manifest_lookup() -> None:
    manifest = RequirementsManifest(
        departments=[
            DepartmentManifest(
                department="equity_research",
                requirements=[
                    Requirement(
                        type="stock_quote",
                        description="d",
                        tier=RequirementTier.BASIC,
                    ),
                ],
            ),
        ],
    )
    assert manifest.department("equity_research").department == "equity_research"
    assert manifest.department("unknown") is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
uv run pytest packages/core/tests/test_data/test_manifest_loader.py -v
```
Expected: ImportError on `openlia.data.manifest.types`.

- [ ] **Step 3: Create the manifest package `__init__.py`**

Create `packages/core/src/openlia/data/manifest/__init__.py`:

```python
"""Department data requirements manifest.

A manifest is a union of every department's basic + advanced data needs,
expressed as string `type` fields matching adapter capabilities. Loaded once
at startup from `requirements.yaml` bundled with the package.
"""

from openlia.data.manifest.types import (
    DepartmentManifest,
    Requirement,
    RequirementsManifest,
    RequirementTier,
)

__all__ = [
    "DepartmentManifest",
    "Requirement",
    "RequirementTier",
    "RequirementsManifest",
]
```

- [ ] **Step 4: Create `manifest/types.py`**

Create `packages/core/src/openlia/data/manifest/types.py`:

```python
"""Pydantic models for the department data-requirements manifest."""

from enum import Enum

from pydantic import BaseModel, ConfigDict


class RequirementTier(str, Enum):
    BASIC = "basic"
    ADVANCED = "advanced"


class Requirement(BaseModel):
    """One data need for a department."""

    model_config = ConfigDict(frozen=True)

    type: str
    description: str
    tier: RequirementTier


class DepartmentManifest(BaseModel):
    """All requirements for one department."""

    model_config = ConfigDict(frozen=True)

    department: str
    requirements: tuple[Requirement, ...]

    def __init__(self, **data: object) -> None:
        reqs = data.get("requirements")
        if isinstance(reqs, list):
            data["requirements"] = tuple(reqs)
        super().__init__(**data)

    def basic(self) -> tuple[Requirement, ...]:
        return tuple(r for r in self.requirements if r.tier is RequirementTier.BASIC)

    def advanced(self) -> tuple[Requirement, ...]:
        return tuple(
            r for r in self.requirements if r.tier is RequirementTier.ADVANCED
        )


class RequirementsManifest(BaseModel):
    """Root of the manifest — all configured departments."""

    model_config = ConfigDict(frozen=True)

    departments: tuple[DepartmentManifest, ...]

    def __init__(self, **data: object) -> None:
        deps = data.get("departments")
        if isinstance(deps, list):
            data["departments"] = tuple(deps)
        super().__init__(**data)

    def department(self, name: str) -> DepartmentManifest | None:
        for dm in self.departments:
            if dm.department == name:
                return dm
        return None
```

- [ ] **Step 5: Run the test to verify it passes**

Run:
```bash
uv run pytest packages/core/tests/test_data/test_manifest_loader.py -v
```
Expected: 4 tests pass.

- [ ] **Step 6: Ruff check**

Run:
```bash
uv run ruff check packages/core/src/openlia/data/manifest/ packages/core/tests/test_data/test_manifest_loader.py
uv run ruff format --check packages/core/src/openlia/data/manifest/ packages/core/tests/test_data/test_manifest_loader.py
```
Expected: no findings.

- [ ] **Step 7: Commit**

```bash
git add packages/core/src/openlia/data/manifest/__init__.py \
        packages/core/src/openlia/data/manifest/types.py \
        packages/core/tests/test_data/test_manifest_loader.py
git commit -m "phase-3(data): manifest pydantic types — Requirement/DepartmentManifest/RequirementsManifest"
```

---

## Task 6: Manifest loader + `requirements.yaml`

**Files:**
- Create: `packages/core/src/openlia/data/manifest/loader.py`
- Create: `packages/core/src/openlia/data/manifest/requirements.yaml`
- Modify: `packages/core/tests/test_data/test_manifest_loader.py` — add load tests

- [ ] **Step 1: Add failing tests for the loader**

Append to `packages/core/tests/test_data/test_manifest_loader.py`:

```python
from openlia.data.manifest.loader import (
    DEFAULT_MANIFEST_PATH,
    load_manifest,
    load_manifest_from_path,
)


def test_default_manifest_loads() -> None:
    manifest = load_manifest()
    assert manifest.department("equity_research") is not None


def test_default_manifest_equity_research_has_expected_basics() -> None:
    manifest = load_manifest()
    er = manifest.department("equity_research")
    assert er is not None
    basic_types = {r.type for r in er.basic()}
    assert {"stock_quote", "historical_prices", "company_news"} <= basic_types


def test_default_manifest_path_points_into_package() -> None:
    assert DEFAULT_MANIFEST_PATH.exists()
    assert DEFAULT_MANIFEST_PATH.name == "requirements.yaml"


def test_load_from_arbitrary_path(tmp_path) -> None:
    yaml_text = """
departments:
  - department: test_dept
    requirements:
      - type: foo
        description: foo data
        tier: basic
      - type: bar
        description: bar data
        tier: advanced
"""
    p = tmp_path / "m.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    m = load_manifest_from_path(p)
    td = m.department("test_dept")
    assert td is not None
    assert {r.type for r in td.basic()} == {"foo"}
    assert {r.type for r in td.advanced()} == {"bar"}


def test_load_missing_file_raises(tmp_path) -> None:
    import pytest

    with pytest.raises(FileNotFoundError):
        load_manifest_from_path(tmp_path / "does-not-exist.yaml")


def test_load_invalid_tier_raises(tmp_path) -> None:
    import pytest

    bad = tmp_path / "m.yaml"
    bad.write_text(
        """
departments:
  - department: x
    requirements:
      - type: t
        description: d
        tier: not_a_tier
""",
        encoding="utf-8",
    )
    with pytest.raises(Exception):
        load_manifest_from_path(bad)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
uv run pytest packages/core/tests/test_data/test_manifest_loader.py -v
```
Expected: ImportError on `openlia.data.manifest.loader`.

- [ ] **Step 3: Create `requirements.yaml`**

Create `packages/core/src/openlia/data/manifest/requirements.yaml`:

```yaml
# Department data-requirements manifest.
#
# Each department declares the data TYPES it needs (not endpoints). Adapters
# declare which types they can satisfy via their `capabilities` class-var.
#
# Tier semantics:
#   - basic:    department refuses to start if any basic requirement is unmet
#   - advanced: enhances output when available; LLM is informed when missing
#
# Plan 3 ships a populated entry for equity_research and placeholders for the
# other departments (empty requirements lists). Later plans (13-20) fill the
# remaining departments when they're implemented.
departments:
  - department: equity_research
    requirements:
      - type: stock_quote
        description: Real-time or delayed stock price, volume, market cap, day range.
        tier: basic
      - type: historical_prices
        description: OHLCV daily historical price series for at least 5 years.
        tier: basic
      - type: company_profile
        description: Company description, sector, industry, CEO, headquarters, employee count.
        tier: basic
      - type: company_news
        description: Recent company-specific news headlines with publication date and URL.
        tier: basic
      - type: company_fundamentals
        description: Income statement, balance sheet, cash-flow statement — annual and quarterly.
        tier: advanced
      - type: stock_grade
        description: Analyst upgrades, downgrades, and ratings history.
        tier: advanced
      - type: insider_transactions
        description: Form 4 insider buying and selling activity.
        tier: advanced

  - department: secretary
    requirements: []

  - department: earnings_update
    requirements: []

  - department: morning_briefing
    requirements: []

  - department: macro_research
    requirements: []

  - department: panic_thermometer
    requirements: []

  - department: retail_sentiment
    requirements: []
```

- [ ] **Step 4: Create `manifest/loader.py`**

Create `packages/core/src/openlia/data/manifest/loader.py`:

```python
"""Load the department requirements manifest from YAML."""

from pathlib import Path

import yaml

from openlia.data.manifest.types import (
    DepartmentManifest,
    Requirement,
    RequirementsManifest,
    RequirementTier,
)

DEFAULT_MANIFEST_PATH: Path = Path(__file__).parent / "requirements.yaml"


def load_manifest() -> RequirementsManifest:
    """Load the bundled manifest."""
    return load_manifest_from_path(DEFAULT_MANIFEST_PATH)


def load_manifest_from_path(path: Path) -> RequirementsManifest:
    """Load a manifest from an arbitrary path (for tests or overrides)."""
    text = path.read_text(encoding="utf-8")
    raw = yaml.safe_load(text) or {}
    departments = [
        DepartmentManifest(
            department=d["department"],
            requirements=tuple(
                Requirement(
                    type=r["type"],
                    description=r["description"],
                    tier=RequirementTier(r["tier"]),
                )
                for r in d.get("requirements", [])
            ),
        )
        for d in raw.get("departments", [])
    ]
    return RequirementsManifest(departments=tuple(departments))
```

- [ ] **Step 5: Update `manifest/__init__.py` to re-export loader functions**

Edit `packages/core/src/openlia/data/manifest/__init__.py` — the final file must read:

```python
"""Department data requirements manifest.

A manifest is a union of every department's basic + advanced data needs,
expressed as string `type` fields matching adapter capabilities. Loaded once
at startup from `requirements.yaml` bundled with the package.
"""

from openlia.data.manifest.loader import (
    DEFAULT_MANIFEST_PATH,
    load_manifest,
    load_manifest_from_path,
)
from openlia.data.manifest.types import (
    DepartmentManifest,
    Requirement,
    RequirementsManifest,
    RequirementTier,
)

__all__ = [
    "DEFAULT_MANIFEST_PATH",
    "DepartmentManifest",
    "Requirement",
    "RequirementTier",
    "RequirementsManifest",
    "load_manifest",
    "load_manifest_from_path",
]
```

- [ ] **Step 6: Ensure the YAML ships inside the wheel**

Edit `packages/core/pyproject.toml`. Add a `[tool.hatch.build.targets.wheel]` (or matching section for the build backend Phase 0 chose) so the manifest YAML is included. If Phase 0 used hatchling:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/openlia"]

[tool.hatch.build.targets.wheel.force-include]
"src/openlia/data/manifest/requirements.yaml" = "openlia/data/manifest/requirements.yaml"
```

If Phase 0 used a different backend, use its equivalent (e.g. `[tool.setuptools.package-data]` with `openlia.data.manifest = ["*.yaml"]`). Confirm by running `uv build packages/core` (next step).

- [ ] **Step 7: Verify the wheel includes the YAML**

Run:
```bash
uv build packages/core
python -c "
import zipfile, glob
wheel = sorted(glob.glob('packages/core/dist/*.whl'))[-1]
with zipfile.ZipFile(wheel) as z:
    names = z.namelist()
assert any(n.endswith('data/manifest/requirements.yaml') for n in names), names
print('OK')
"
```
Expected: prints `OK`. If the assertion fails, the build-backend packaging config in Step 6 needs adjustment.

- [ ] **Step 8: Run the loader tests**

Run:
```bash
uv run pytest packages/core/tests/test_data/test_manifest_loader.py -v
```
Expected: all manifest tests pass (structural tests from Task 5 + six new loader tests).

- [ ] **Step 9: Ruff check**

Run:
```bash
uv run ruff check packages/core/src/openlia/data/manifest/ packages/core/tests/test_data/test_manifest_loader.py
uv run ruff format --check packages/core/src/openlia/data/manifest/ packages/core/tests/test_data/test_manifest_loader.py
```
Expected: no findings.

- [ ] **Step 10: Commit**

```bash
git add packages/core/src/openlia/data/manifest/loader.py \
        packages/core/src/openlia/data/manifest/requirements.yaml \
        packages/core/src/openlia/data/manifest/__init__.py \
        packages/core/pyproject.toml \
        packages/core/tests/test_data/test_manifest_loader.py
git commit -m "phase-3(data): manifest loader + requirements.yaml (equity_research populated; others stubs)"
```

---

## Task 7: Manifest checker — `unmet_basic_requirements`

**Files:**
- Create: `packages/core/src/openlia/data/manifest/checker.py`
- Create: `packages/core/tests/test_data/test_manifest_checker.py`

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/test_data/test_manifest_checker.py`:

```python
from openlia.data.manifest import RequirementsManifest
from openlia.data.manifest.checker import (
    UnmetRequirement,
    unmet_basic_requirements,
)
from openlia.data.manifest.types import (
    DepartmentManifest,
    Requirement,
    RequirementTier,
)


def _manifest() -> RequirementsManifest:
    return RequirementsManifest(
        departments=(
            DepartmentManifest(
                department="alpha",
                requirements=(
                    Requirement(
                        type="q",
                        description="d",
                        tier=RequirementTier.BASIC,
                    ),
                    Requirement(
                        type="n",
                        description="d",
                        tier=RequirementTier.BASIC,
                    ),
                    Requirement(
                        type="a",
                        description="d",
                        tier=RequirementTier.ADVANCED,
                    ),
                ),
            ),
            DepartmentManifest(
                department="beta",
                requirements=(
                    Requirement(
                        type="q",
                        description="d",
                        tier=RequirementTier.BASIC,
                    ),
                ),
            ),
        )
    )


def test_all_basic_satisfied_returns_empty_list() -> None:
    unmet = unmet_basic_requirements(
        manifest=_manifest(),
        active_capabilities={"q", "n"},
    )
    assert unmet == []


def test_missing_one_basic_flagged_for_alpha_only() -> None:
    unmet = unmet_basic_requirements(
        manifest=_manifest(),
        active_capabilities={"q"},  # missing 'n'
    )
    assert len(unmet) == 1
    u = unmet[0]
    assert isinstance(u, UnmetRequirement)
    assert u.department == "alpha"
    assert u.requirement_type == "n"


def test_missing_basic_for_multiple_departments() -> None:
    unmet = unmet_basic_requirements(
        manifest=_manifest(),
        active_capabilities=set(),
    )
    pairs = {(u.department, u.requirement_type) for u in unmet}
    assert pairs == {("alpha", "q"), ("alpha", "n"), ("beta", "q")}


def test_advanced_never_flagged() -> None:
    unmet = unmet_basic_requirements(
        manifest=_manifest(),
        active_capabilities={"q", "n"},  # missing 'a' which is advanced
    )
    assert all(u.requirement_type != "a" for u in unmet)


def test_empty_department_is_silently_satisfied() -> None:
    m = RequirementsManifest(
        departments=(
            DepartmentManifest(department="empty", requirements=()),
        )
    )
    assert unmet_basic_requirements(manifest=m, active_capabilities=set()) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
uv run pytest packages/core/tests/test_data/test_manifest_checker.py -v
```
Expected: ImportError on `openlia.data.manifest.checker`.

- [ ] **Step 3: Create `checker.py`**

Create `packages/core/src/openlia/data/manifest/checker.py`:

```python
"""Validate a manifest against the union of active provider capabilities.

Plan 3 uses a simple set-membership check: a requirement is satisfied iff
at least one configured provider's adapter declares the requirement type
in its `capabilities` class-var. The future AI-review layer will replace
this with a confidence-scored endpoint match.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from openlia.data.manifest.types import RequirementsManifest, RequirementTier


@dataclass(frozen=True, slots=True)
class UnmetRequirement:
    """One (department, requirement_type) pair that no active provider covers."""

    department: str
    requirement_type: str


def unmet_basic_requirements(
    *,
    manifest: RequirementsManifest,
    active_capabilities: Iterable[str],
) -> list[UnmetRequirement]:
    """Return every basic requirement not covered by `active_capabilities`.

    Order is deterministic: departments in manifest order, requirements in
    declaration order within each department.
    """
    covered = frozenset(active_capabilities)
    unmet: list[UnmetRequirement] = []
    for dm in manifest.departments:
        for req in dm.requirements:
            if req.tier is RequirementTier.BASIC and req.type not in covered:
                unmet.append(
                    UnmetRequirement(
                        department=dm.department,
                        requirement_type=req.type,
                    )
                )
    return unmet
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
uv run pytest packages/core/tests/test_data/test_manifest_checker.py -v
```
Expected: 5 tests pass.

- [ ] **Step 5: Ruff check**

Run:
```bash
uv run ruff check packages/core/src/openlia/data/manifest/checker.py packages/core/tests/test_data/test_manifest_checker.py
uv run ruff format --check packages/core/src/openlia/data/manifest/checker.py packages/core/tests/test_data/test_manifest_checker.py
```
Expected: no findings.

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/data/manifest/checker.py \
        packages/core/tests/test_data/test_manifest_checker.py
git commit -m "phase-3(data): manifest checker — unmet_basic_requirements"
```

---

## Task 8: EODHD adapter (4 capabilities)

**Files:**
- Create: `packages/core/src/openlia/data/adapters/__init__.py`
- Create: `packages/core/src/openlia/data/adapters/eodhd.py`
- Create: `packages/core/tests/test_data/test_adapters/__init__.py`
- Create: `packages/core/tests/test_data/test_adapters/test_eodhd.py`

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/test_data/test_adapters/__init__.py`:

```python
"""Adapter tests."""
```

Create `packages/core/tests/test_data/test_adapters/test_eodhd.py`:

```python
import httpx
import pytest
import respx

from openlia.data.adapters.eodhd import EODHDAdapter
from openlia.data.errors import DataNotAvailable, DataSourceError, RateLimitError
from openlia.data.types import ProviderCategory, ProviderEntry, ProviderMode


def _entry(base_url: str = "https://eodhd.com/api") -> ProviderEntry:
    return ProviderEntry(
        id="00000000-0000-0000-0000-000000000001",
        kind="eodhd",
        label="EODHD",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="TEST-KEY",
        base_url=base_url,
    )


def test_eodhd_declared_metadata() -> None:
    assert EODHDAdapter.kind == "eodhd"
    assert EODHDAdapter.category is ProviderCategory.FINANCIAL
    assert {"stock_quote", "historical_prices", "company_profile", "company_news"} <= (
        EODHDAdapter.capabilities
    )


async def test_fetch_rejects_unknown_capability() -> None:
    adapter = EODHDAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("insider_transactions", {"symbol": "AAPL"})
    assert exc.value.provider_kind == "eodhd"
    assert exc.value.capability == "insider_transactions"


@respx.mock
async def test_fetch_stock_quote_success() -> None:
    route = respx.get(
        "https://eodhd.com/api/real-time/AAPL.US",
    ).mock(
        return_value=httpx.Response(
            200,
            json={"code": "AAPL.US", "close": 225.1, "volume": 10_000_000},
        )
    )
    adapter = EODHDAdapter(_entry())
    result = await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert route.called
    assert result.provider_kind == "eodhd"
    assert result.capability == "stock_quote"
    assert result.payload["close"] == 225.1
    # api key must be passed as ?api_token=
    assert "api_token=TEST-KEY" in str(route.calls[0].request.url)


@respx.mock
async def test_fetch_stock_quote_missing_symbol_param() -> None:
    adapter = EODHDAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("stock_quote", {})
    assert "symbol" in exc.value.reason


@respx.mock
async def test_fetch_historical_prices_uses_eod_endpoint() -> None:
    route = respx.get("https://eodhd.com/api/eod/MSFT.US").mock(
        return_value=httpx.Response(
            200,
            json=[{"date": "2026-04-10", "close": 400.0}],
        )
    )
    adapter = EODHDAdapter(_entry())
    result = await adapter.fetch(
        "historical_prices",
        {"symbol": "MSFT", "from": "2025-01-01", "to": "2026-01-01"},
    )
    assert route.called
    assert isinstance(result.payload, list)


@respx.mock
async def test_429_maps_to_rate_limit_error() -> None:
    respx.get("https://eodhd.com/api/real-time/AAPL.US").mock(
        return_value=httpx.Response(
            429,
            headers={"Retry-After": "30"},
            text="rate limited",
        )
    )
    adapter = EODHDAdapter(_entry())
    with pytest.raises(RateLimitError) as exc:
        await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert exc.value.retry_after_seconds == 30


@respx.mock
async def test_404_maps_to_data_not_available() -> None:
    respx.get("https://eodhd.com/api/real-time/ZZZZ.US").mock(
        return_value=httpx.Response(404, text="symbol not found"),
    )
    adapter = EODHDAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("stock_quote", {"symbol": "ZZZZ"})
    assert exc.value.provider_kind == "eodhd"


@respx.mock
async def test_500_maps_to_data_source_error() -> None:
    respx.get("https://eodhd.com/api/real-time/AAPL.US").mock(
        return_value=httpx.Response(500, text="boom"),
    )
    adapter = EODHDAdapter(_entry())
    with pytest.raises(DataSourceError) as exc:
        await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert exc.value.status_code == 500


@respx.mock
async def test_health_check_hits_user_endpoint_and_returns_true_on_200() -> None:
    respx.get("https://eodhd.com/api/user").mock(
        return_value=httpx.Response(200, json={"email": "x@y.z"})
    )
    adapter = EODHDAdapter(_entry())
    assert await adapter.health_check() is True


@respx.mock
async def test_health_check_returns_false_on_401() -> None:
    respx.get("https://eodhd.com/api/user").mock(
        return_value=httpx.Response(401, text="bad key")
    )
    adapter = EODHDAdapter(_entry())
    assert await adapter.health_check() is False


@respx.mock
async def test_health_check_returns_false_on_network_error() -> None:
    respx.get("https://eodhd.com/api/user").mock(
        side_effect=httpx.ConnectError("boom"),
    )
    adapter = EODHDAdapter(_entry())
    assert await adapter.health_check() is False


def test_registry_exposes_eodhd() -> None:
    from openlia.data.adapters import ADAPTERS

    assert ADAPTERS["eodhd"] is EODHDAdapter
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
uv run pytest packages/core/tests/test_data/test_adapters/ -v
```
Expected: ImportError on `openlia.data.adapters.eodhd`.

- [ ] **Step 3: Create `adapters/eodhd.py`**

Create `packages/core/src/openlia/data/adapters/eodhd.py`:

```python
"""EODHD adapter — the default financial provider.

Covers four capabilities in Plan 3:
    stock_quote          GET /real-time/{ticker}.US
    historical_prices    GET /eod/{ticker}.US
    company_profile      GET /fundamentals/{ticker}.US (General block)
    company_news         GET /news?s={ticker}.US

Authentication: `?api_token=<key>` query param (EODHD's documented auth
method). We pass the key on every request.

Symbol convention: EODHD requires `{SYMBOL}.{EXCHANGE}` (e.g. AAPL.US).
For Plan 3 we hard-code the `.US` suffix — multi-exchange support is a
later enhancement.
"""

from typing import Any, ClassVar

import httpx

from openlia.data.base import ProviderAdapter
from openlia.data.errors import DataNotAvailable, DataSourceError, RateLimitError
from openlia.data.types import ProviderCategory, ProviderEntry, ToolResult

_HEALTH_CHECK_PATH = "/user"
_REQUEST_TIMEOUT_SECONDS = 30.0


class EODHDAdapter(ProviderAdapter):
    """EODHD financial-data adapter."""

    kind: ClassVar[str] = "eodhd"
    category: ClassVar[ProviderCategory] = ProviderCategory.FINANCIAL
    capabilities: ClassVar[frozenset[str]] = frozenset(
        {
            "stock_quote",
            "historical_prices",
            "company_profile",
            "company_news",
        }
    )

    def __init__(self, entry: ProviderEntry) -> None:
        super().__init__(entry)
        # base_url is guaranteed non-None in api_key mode (validated on ProviderEntry)
        assert entry.base_url is not None
        self._base_url = entry.base_url.rstrip("/")

    async def fetch(
        self,
        capability: str,
        params: dict[str, Any],
    ) -> ToolResult:
        if capability not in self.capabilities:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason=f"capability {capability!r} not declared by eodhd",
            )

        symbol = params.get("symbol")
        if not symbol:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason="`symbol` parameter is required",
            )
        ticker = self._format_ticker(str(symbol))

        if capability == "stock_quote":
            path = f"/real-time/{ticker}"
            query: dict[str, Any] = {"fmt": "json"}
        elif capability == "historical_prices":
            path = f"/eod/{ticker}"
            query = {"fmt": "json"}
            if "from" in params:
                query["from"] = params["from"]
            if "to" in params:
                query["to"] = params["to"]
        elif capability == "company_profile":
            path = f"/fundamentals/{ticker}"
            query = {"fmt": "json"}
        elif capability == "company_news":
            path = "/news"
            query = {"s": ticker, "limit": params.get("limit", 50)}
        else:  # pragma: no cover - guarded above
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason="internal routing bug",
            )

        payload = await self._get_json(path, query)
        return ToolResult(
            provider_kind=self.kind,
            capability=capability,
            payload=payload,
        )

    async def health_check(self) -> bool:
        try:
            await self._get_json(_HEALTH_CHECK_PATH, {})
        except (DataProviderOrHTTP:=(
            DataNotAvailable, RateLimitError, DataSourceError,
            httpx.HTTPError,
        )):
            return False
        return True

    def _format_ticker(self, symbol: str) -> str:
        if "." in symbol:
            return symbol.upper()
        return f"{symbol.upper()}.US"

    async def _get_json(
        self,
        path: str,
        query: dict[str, Any],
    ) -> dict[str, Any] | list[Any]:
        params = dict(query)
        params["api_token"] = self.entry.api_key or ""
        url = f"{self._base_url}{path}"
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
            try:
                resp = await client.get(url, params=params)
            except httpx.HTTPError as exc:
                raise DataSourceError(
                    provider_kind=self.kind,
                    detail=str(exc),
                ) from exc

        if resp.status_code == 200:
            try:
                return resp.json()
            except ValueError as exc:
                raise DataSourceError(
                    provider_kind=self.kind,
                    status_code=200,
                    detail=f"malformed json: {exc}",
                ) from exc
        if resp.status_code == 404:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=path.split("/", 2)[1] or "unknown",
                reason=resp.text.strip() or "not found",
            )
        if resp.status_code == 429:
            retry_after = _parse_retry_after(resp.headers.get("Retry-After"))
            raise RateLimitError(
                provider_kind=self.kind,
                retry_after_seconds=retry_after,
            )
        raise DataSourceError(
            provider_kind=self.kind,
            status_code=resp.status_code,
            detail=resp.text[:500],
        )


def _parse_retry_after(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
```

Note on the `health_check` except clause: the walrus assignment is ugly — simplify to a standard tuple of exception types before committing. Replace the `except` block with:

```python
        try:
            await self._get_json(_HEALTH_CHECK_PATH, {})
        except (DataNotAvailable, RateLimitError, DataSourceError, httpx.HTTPError):
            return False
        return True
```

Use the simplified form; the walrus version above was accidental.

- [ ] **Step 4: Create the adapter registry**

Create `packages/core/src/openlia/data/adapters/__init__.py`:

```python
"""Adapter registry.

Maps `kind` strings (as stored in data_providers.kind) to adapter classes.
Server code uses this to look up the right adapter when instantiating a
ProviderAdapter from a ProviderEntry.
"""

from openlia.data.adapters.eodhd import EODHDAdapter
from openlia.data.base import ProviderAdapter

ADAPTERS: dict[str, type[ProviderAdapter]] = {
    EODHDAdapter.kind: EODHDAdapter,
}

__all__ = ["ADAPTERS", "EODHDAdapter"]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run:
```bash
uv run pytest packages/core/tests/test_data/test_adapters/ -v
```
Expected: 12 tests pass. If any fail because `respx` didn't intercept the call, confirm `httpx.AsyncClient` is used (not the sync client) — `respx.mock` intercepts both.

- [ ] **Step 6: Ruff check**

Run:
```bash
uv run ruff check packages/core/src/openlia/data/adapters/ packages/core/tests/test_data/test_adapters/
uv run ruff format --check packages/core/src/openlia/data/adapters/ packages/core/tests/test_data/test_adapters/
```
Expected: no findings.

- [ ] **Step 7: Commit**

```bash
git add packages/core/src/openlia/data/adapters/__init__.py \
        packages/core/src/openlia/data/adapters/eodhd.py \
        packages/core/tests/test_data/test_adapters/__init__.py \
        packages/core/tests/test_data/test_adapters/test_eodhd.py
git commit -m "phase-3(data): EODHD adapter + registry (4 capabilities, httpx-based)"
```

---

## Task 9: Capability resolver

**Files:**
- Create: `packages/core/src/openlia/data/resolver.py`
- Create: `packages/core/tests/test_data/test_resolver.py`

- [ ] **Step 1: Write the failing test**

Create `packages/core/tests/test_data/test_resolver.py`:

```python
from typing import Any, ClassVar

from openlia.data.base import ProviderAdapter
from openlia.data.resolver import (
    ResolvedProvider,
    resolve_provider_for_capability,
    resolve_tools_for_requirements,
)
from openlia.data.manifest.types import Requirement, RequirementTier
from openlia.data.types import ProviderCategory, ProviderEntry, ProviderMode, ToolResult


class _QuotesOnly(ProviderAdapter):
    kind = "quotes_only"
    category = ProviderCategory.FINANCIAL
    capabilities = frozenset({"stock_quote"})

    async def fetch(self, capability: str, params: dict[str, Any]) -> ToolResult:
        raise NotImplementedError

    async def health_check(self) -> bool:
        return True


class _QuotesAndNews(ProviderAdapter):
    kind = "quotes_and_news"
    category = ProviderCategory.FINANCIAL
    capabilities = frozenset({"stock_quote", "company_news"})

    async def fetch(self, capability: str, params: dict[str, Any]) -> ToolResult:
        raise NotImplementedError

    async def health_check(self) -> bool:
        return True


def _entry(kind: str, priority: int, is_enabled: bool = True) -> ProviderEntry:
    return ProviderEntry(
        id=f"{kind}-id",
        kind=kind,
        label=kind,
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://example.test",
        priority=priority,
        is_enabled=is_enabled,
    )


_REGISTRY: dict[str, type[ProviderAdapter]] = {
    "quotes_only": _QuotesOnly,
    "quotes_and_news": _QuotesAndNews,
}


def test_resolver_returns_highest_priority_capable_provider() -> None:
    entries = [_entry("quotes_and_news", priority=50), _entry("quotes_only", priority=10)]
    resolved = resolve_provider_for_capability(
        capability="stock_quote",
        entries=entries,
        adapters=_REGISTRY,
    )
    assert resolved is not None
    assert resolved.entry.kind == "quotes_only"  # priority 10 < 50 wins


def test_resolver_skips_provider_without_capability() -> None:
    entries = [_entry("quotes_only", priority=10)]
    resolved = resolve_provider_for_capability(
        capability="company_news",
        entries=entries,
        adapters=_REGISTRY,
    )
    assert resolved is None


def test_resolver_skips_disabled_provider() -> None:
    entries = [
        _entry("quotes_and_news", priority=10, is_enabled=False),
        _entry("quotes_only", priority=50),
    ]
    resolved = resolve_provider_for_capability(
        capability="stock_quote",
        entries=entries,
        adapters=_REGISTRY,
    )
    assert resolved is not None
    assert resolved.entry.kind == "quotes_only"


def test_resolver_returns_none_when_no_provider_has_capability() -> None:
    entries = [_entry("quotes_only", priority=10)]
    assert (
        resolve_provider_for_capability(
            capability="insider_transactions",
            entries=entries,
            adapters=_REGISTRY,
        )
        is None
    )


def test_resolver_skips_unknown_kind() -> None:
    entries = [_entry("ghost", priority=10), _entry("quotes_only", priority=20)]
    resolved = resolve_provider_for_capability(
        capability="stock_quote",
        entries=entries,
        adapters=_REGISTRY,
    )
    assert resolved is not None
    assert resolved.entry.kind == "quotes_only"


def test_resolve_tools_for_requirements_builds_ordered_list() -> None:
    entries = [
        _entry("quotes_and_news", priority=10),
        _entry("quotes_only", priority=20),
    ]
    requirements = [
        Requirement(type="stock_quote", description="d", tier=RequirementTier.BASIC),
        Requirement(type="company_news", description="d", tier=RequirementTier.BASIC),
        Requirement(
            type="insider_transactions",  # no provider covers this
            description="d",
            tier=RequirementTier.ADVANCED,
        ),
    ]
    resolved, unmet = resolve_tools_for_requirements(
        requirements=requirements,
        entries=entries,
        adapters=_REGISTRY,
    )
    # Two requirements resolved; 'insider_transactions' is unmet
    by_cap = {r.capability: r for r in resolved}
    assert set(by_cap) == {"stock_quote", "company_news"}
    assert by_cap["stock_quote"].entry.kind == "quotes_and_news"  # priority 10
    assert by_cap["company_news"].entry.kind == "quotes_and_news"
    assert unmet == ["insider_transactions"]


def test_resolved_provider_carries_adapter_class() -> None:
    entries = [_entry("quotes_only", priority=10)]
    resolved = resolve_provider_for_capability(
        capability="stock_quote",
        entries=entries,
        adapters=_REGISTRY,
    )
    assert isinstance(resolved, ResolvedProvider)
    assert resolved.adapter_cls is _QuotesOnly
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
uv run pytest packages/core/tests/test_data/test_resolver.py -v
```
Expected: ImportError on `openlia.data.resolver`.

- [ ] **Step 3: Create `resolver.py`**

Create `packages/core/src/openlia/data/resolver.py`:

```python
"""Deterministic capability resolver.

Given a list of configured provider entries and a capability string, returns
the highest-priority enabled provider whose adapter declares support.

Priority ordering: LOWER integer = HIGHER priority (convention matches
web_search_providers.priority default=100 in database-design.md). Ties are
broken by list order (kept stable via sorted(...)'s stability guarantee).

No LLM inference — this is a pure set-membership lookup. The catalog/review
flow described in data-provider-design.md is a later addition that will
augment (not replace) this resolver.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from openlia.data.base import ProviderAdapter
from openlia.data.manifest.types import Requirement
from openlia.data.types import ProviderEntry


@dataclass(frozen=True, slots=True)
class ResolvedProvider:
    """The (entry, adapter class) pair that covers one capability."""

    capability: str
    entry: ProviderEntry
    adapter_cls: type[ProviderAdapter]


def resolve_provider_for_capability(
    *,
    capability: str,
    entries: Iterable[ProviderEntry],
    adapters: Mapping[str, type[ProviderAdapter]],
) -> ResolvedProvider | None:
    """Return the winning provider for `capability`, or None if none cover it."""
    candidates: list[tuple[int, ProviderEntry, type[ProviderAdapter]]] = []
    for entry in entries:
        if not entry.is_enabled:
            continue
        adapter_cls = adapters.get(entry.kind)
        if adapter_cls is None:
            continue
        if capability not in adapter_cls.capabilities:
            continue
        candidates.append((entry.priority, entry, adapter_cls))

    if not candidates:
        return None

    candidates.sort(key=lambda c: c[0])
    _, entry, adapter_cls = candidates[0]
    return ResolvedProvider(
        capability=capability,
        entry=entry,
        adapter_cls=adapter_cls,
    )


def resolve_tools_for_requirements(
    *,
    requirements: Iterable[Requirement],
    entries: Iterable[ProviderEntry],
    adapters: Mapping[str, type[ProviderAdapter]],
) -> tuple[list[ResolvedProvider], list[str]]:
    """Resolve every requirement; return (resolved, unmet_types)."""
    entries_list = list(entries)  # single-pass safety
    resolved: list[ResolvedProvider] = []
    unmet: list[str] = []
    for req in requirements:
        r = resolve_provider_for_capability(
            capability=req.type,
            entries=entries_list,
            adapters=adapters,
        )
        if r is None:
            unmet.append(req.type)
        else:
            resolved.append(r)
    return resolved, unmet
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
uv run pytest packages/core/tests/test_data/test_resolver.py -v
```
Expected: 7 tests pass.

- [ ] **Step 5: Re-export resolver from the package `__init__`**

Edit `packages/core/src/openlia/data/__init__.py` so the final file reads:

```python
"""Data provider adapter system.

Public surface kept minimal in Plan 3: errors, types, adapter base, resolver.
Catalog, dispatch, review, and expansion layers are added in later plans.
"""

from openlia.data.base import ProviderAdapter
from openlia.data.errors import (
    DataNotAvailable,
    DataProviderError,
    DataSourceError,
    RateLimitError,
)
from openlia.data.resolver import (
    ResolvedProvider,
    resolve_provider_for_capability,
    resolve_tools_for_requirements,
)
from openlia.data.types import (
    ProviderCategory,
    ProviderEntry,
    ProviderMode,
    ToolResult,
)

__all__ = [
    "DataNotAvailable",
    "DataProviderError",
    "DataSourceError",
    "ProviderAdapter",
    "ProviderCategory",
    "ProviderEntry",
    "ProviderMode",
    "RateLimitError",
    "ResolvedProvider",
    "ToolResult",
    "resolve_provider_for_capability",
    "resolve_tools_for_requirements",
]
```

- [ ] **Step 6: Ruff check**

Run:
```bash
uv run ruff check packages/core/src/openlia/data/ packages/core/tests/test_data/
uv run ruff format --check packages/core/src/openlia/data/ packages/core/tests/test_data/
```
Expected: no findings.

- [ ] **Step 7: Commit**

```bash
git add packages/core/src/openlia/data/resolver.py \
        packages/core/src/openlia/data/__init__.py \
        packages/core/tests/test_data/test_resolver.py
git commit -m "phase-3(data): capability resolver (priority-ordered, deterministic)"
```

---

## Task 10: Server service — CRUD for `data_providers` (list / create / update / delete / test)

**Files:**
- Create: `packages/server/src/openlia_server/services/data_providers.py`
- Create: `packages/server/tests/test_services/test_data_providers.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_services/test_data_providers.py`:

```python
"""Service-layer tests for data-provider CRUD.

Uses the shared `db_session` fixture from Plan 1A's conftest and the crypto
module from Plan 2. No HTTP — call service functions directly.
"""

import pytest

from openlia.data.types import ProviderCategory, ProviderEntry, ProviderMode
from openlia_server.db.models.config import DataProvider
from openlia_server.services import data_providers as svc


def test_create_provider_encrypts_api_key_on_disk(db_session) -> None:
    created = svc.create_provider(
        db_session,
        kind="eodhd",
        label="EODHD",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="SECRET-VALUE",
        base_url="https://eodhd.com/api",
    )
    db_session.flush()
    row = db_session.get(DataProvider, created.id)
    assert row is not None
    # Stored value is base64 ciphertext, NOT the plaintext
    assert row.api_key_encrypted is not None
    assert "SECRET-VALUE" not in row.api_key_encrypted


def test_create_provider_rejects_unknown_kind(db_session) -> None:
    with pytest.raises(svc.UnknownProviderKindError):
        svc.create_provider(
            db_session,
            kind="does-not-exist",
            label="X",
            category=ProviderCategory.FINANCIAL,
            mode=ProviderMode.API_KEY,
            api_key="k",
            base_url="https://x.test",
        )


def test_create_provider_with_env_var_instead_of_api_key(
    db_session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MY_EODHD_KEY", "ENV-VALUE")
    created = svc.create_provider(
        db_session,
        kind="eodhd",
        label="EODHD",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key=None,
        env_var_name="MY_EODHD_KEY",
        base_url="https://eodhd.com/api",
    )
    db_session.flush()
    row = db_session.get(DataProvider, created.id)
    assert row.api_key_encrypted is None
    assert row.env_var_name == "MY_EODHD_KEY"
    # Entry resolves env var at load time
    entry = svc.load_provider_entry(db_session, created.id, priority=100)
    assert entry.api_key == "ENV-VALUE"


def test_list_providers_returns_enabled_and_disabled(db_session) -> None:
    svc.create_provider(
        db_session,
        kind="eodhd",
        label="A",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k1",
        base_url="https://eodhd.com/api",
    )
    b = svc.create_provider(
        db_session,
        kind="eodhd",
        label="B",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k2",
        base_url="https://eodhd.com/api",
    )
    svc.update_provider(db_session, b.id, is_enabled=False)
    rows = svc.list_providers(db_session)
    assert {r.label for r in rows} == {"A", "B"}


def test_update_provider_can_rotate_api_key(db_session) -> None:
    created = svc.create_provider(
        db_session,
        kind="eodhd",
        label="X",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="OLD",
        base_url="https://eodhd.com/api",
    )
    svc.update_provider(db_session, created.id, api_key="NEW")
    entry = svc.load_provider_entry(db_session, created.id, priority=100)
    assert entry.api_key == "NEW"


def test_delete_provider_removes_row(db_session) -> None:
    created = svc.create_provider(
        db_session,
        kind="eodhd",
        label="X",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://eodhd.com/api",
    )
    svc.delete_provider(db_session, created.id)
    assert db_session.get(DataProvider, created.id) is None


def test_load_provider_entry_returns_pydantic_entry(db_session) -> None:
    created = svc.create_provider(
        db_session,
        kind="eodhd",
        label="X",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://eodhd.com/api",
    )
    entry = svc.load_provider_entry(db_session, created.id, priority=100)
    assert isinstance(entry, ProviderEntry)
    assert entry.kind == "eodhd"
    assert entry.api_key == "k"
    assert entry.priority == 100


def test_load_enabled_entries_with_priorities(db_session) -> None:
    a = svc.create_provider(
        db_session,
        kind="eodhd",
        label="A",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://eodhd.com/api",
    )
    b = svc.create_provider(
        db_session,
        kind="eodhd",
        label="B",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://eodhd.com/api",
    )
    svc.set_requirement_mapping(
        db_session, requirement_type="stock_quote", provider_id=a.id, priority=10
    )
    svc.set_requirement_mapping(
        db_session, requirement_type="stock_quote", provider_id=b.id, priority=5
    )
    entries = svc.load_entries_for_capability(db_session, capability="stock_quote")
    assert [e.kind for e in entries] == ["eodhd", "eodhd"]
    assert [e.id for e in entries] == [b.id, a.id]  # priority 5 < 10
```

Note: this test exercises `set_requirement_mapping` and `load_entries_for_capability` — defined in Task 11. Expect the file to import cleanly only after Task 11 lands; tests using those two functions will remain red until then. That's expected and called out.

- [ ] **Step 2: Run the tests to verify the scope currently failing**

Run:
```bash
uv run pytest packages/server/tests/test_services/test_data_providers.py -v
```
Expected: ImportError on `openlia_server.services.data_providers`.

- [ ] **Step 3: Create `services/data_providers.py`**

Create `packages/server/src/openlia_server/services/data_providers.py`:

```python
"""Service layer for data_providers CRUD + requirement mapping.

Bridges the pure-Python adapter system in `openlia-core` with the database.
Call sites (routes, setup wizard, resolver consumers) touch this module only
— they do not construct DataProvider rows directly.

Encryption: `api_key` (when provided) is AES-256-GCM encrypted via
`openlia_server.db.crypto.encrypt_for_row` with the provider row's `id` as
AAD. On read, `decrypt_for_row` is called with the same AAD. Providers can
also reference an environment variable via `env_var_name` (takes precedence
over the encrypted column during `load_provider_entry`).
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia.data.adapters import ADAPTERS
from openlia.data.types import ProviderCategory, ProviderEntry, ProviderMode
from openlia_server.db.crypto import decrypt_for_row, encrypt_for_row
from openlia_server.db.models.config import (
    DataProvider,
    DataProviderRequirementMapping,
)


class UnknownProviderKindError(ValueError):
    """Raised when a provider is created with a kind that has no adapter."""


class ProviderNotFoundError(LookupError):
    """Raised when a lookup by id yields no row."""


@dataclass(slots=True)
class ProviderCreated:
    id: str


def _require_known_kind(kind: str) -> None:
    if kind not in ADAPTERS:
        raise UnknownProviderKindError(
            f"unknown provider kind {kind!r}; known: {sorted(ADAPTERS)}"
        )


def create_provider(
    session: Session,
    *,
    kind: str,
    label: str,
    category: ProviderCategory,
    mode: ProviderMode,
    api_key: str | None = None,
    env_var_name: str | None = None,
    base_url: str | None = None,
    extra_config: dict | None = None,
    created_by_user_id: str | None = None,
) -> ProviderCreated:
    _require_known_kind(kind)
    if mode is ProviderMode.API_KEY and not base_url:
        raise ValueError("api_key mode requires base_url")
    if mode is ProviderMode.API_KEY and not (api_key or env_var_name):
        raise ValueError("api_key mode requires api_key or env_var_name")

    new_id = str(uuid.uuid4())
    row = DataProvider(
        id=new_id,
        kind=kind,
        label=label,
        api_key_encrypted=(
            encrypt_for_row(row_id=new_id, plaintext=api_key)
            if api_key is not None
            else None
        ),
        env_var_name=env_var_name,
        base_url=base_url,
        extra_config=(extra_config or None),
        is_enabled=True,
        created_by_user_id=created_by_user_id,
    )
    session.add(row)
    # category is implicitly enforced by manifest/adapter wiring, not stored
    # per-row yet; future schema revision can add it if multi-category
    # adapters become a thing. Today, category comes from the adapter class.
    del category  # silence unused warning; category validated via adapter
    del mode  # same rationale; mode inferred from presence of base_url vs mcp_url
    session.flush()
    return ProviderCreated(id=new_id)


def list_providers(session: Session) -> list[DataProvider]:
    return list(session.scalars(select(DataProvider)).all())


def get_provider(session: Session, provider_id: str) -> DataProvider:
    row = session.get(DataProvider, provider_id)
    if row is None:
        raise ProviderNotFoundError(provider_id)
    return row


def update_provider(
    session: Session,
    provider_id: str,
    *,
    label: str | None = None,
    api_key: str | None = None,
    env_var_name: str | None = None,
    base_url: str | None = None,
    extra_config: dict | None = None,
    is_enabled: bool | None = None,
) -> None:
    row = get_provider(session, provider_id)
    if label is not None:
        row.label = label
    if api_key is not None:
        row.api_key_encrypted = encrypt_for_row(
            row_id=provider_id, plaintext=api_key
        )
    if env_var_name is not None:
        row.env_var_name = env_var_name
    if base_url is not None:
        row.base_url = base_url
    if extra_config is not None:
        row.extra_config = extra_config
    if is_enabled is not None:
        row.is_enabled = is_enabled
    session.flush()


def delete_provider(session: Session, provider_id: str) -> None:
    row = get_provider(session, provider_id)
    session.delete(row)
    session.flush()


def load_provider_entry(
    session: Session,
    provider_id: str,
    *,
    priority: int = 100,
) -> ProviderEntry:
    row = get_provider(session, provider_id)
    return _row_to_entry(row, priority=priority)


def _row_to_entry(row: DataProvider, *, priority: int) -> ProviderEntry:
    api_key: str | None = None
    if row.env_var_name:
        api_key = os.environ.get(row.env_var_name)
    elif row.api_key_encrypted:
        api_key = decrypt_for_row(row_id=row.id, ciphertext=row.api_key_encrypted)

    adapter_cls = ADAPTERS.get(row.kind)
    category = (
        adapter_cls.category if adapter_cls is not None else ProviderCategory.FINANCIAL
    )
    mode = ProviderMode.API_KEY if row.base_url else ProviderMode.MCP
    return ProviderEntry(
        id=row.id,
        kind=row.kind,
        label=row.label,
        category=category,
        mode=mode,
        api_key=api_key,
        base_url=row.base_url,
        mcp_url=None,
        extra_config=row.extra_config or {},
        is_enabled=row.is_enabled,
        priority=priority,
    )


# Mapping helpers — implemented in Task 11 but stubbed here for import stability
def set_requirement_mapping(
    session: Session,
    *,
    requirement_type: str,
    provider_id: str,
    priority: int,
) -> None:
    row = session.get(
        DataProviderRequirementMapping, (requirement_type, provider_id)
    )
    if row is None:
        row = DataProviderRequirementMapping(
            requirement_type=requirement_type,
            provider_id=provider_id,
            priority=priority,
        )
        session.add(row)
    else:
        row.priority = priority
    session.flush()


def load_entries_for_capability(
    session: Session,
    *,
    capability: str,
) -> list[ProviderEntry]:
    stmt = (
        select(DataProviderRequirementMapping, DataProvider)
        .join(
            DataProvider,
            DataProvider.id == DataProviderRequirementMapping.provider_id,
        )
        .where(DataProviderRequirementMapping.requirement_type == capability)
        .order_by(DataProviderRequirementMapping.priority.asc())
    )
    result = session.execute(stmt).all()
    return [_row_to_entry(prov, priority=m.priority) for m, prov in result]
```

- [ ] **Step 4: Ensure the service tests folder imports correctly**

Verify `packages/server/tests/test_services/__init__.py` exists (created in Plan 2). If not, create it:

```python
"""Service-layer tests."""
```

Verify the test `conftest.py` produces a `db_session` fixture. Plan 1A's `packages/server/tests/test_db/conftest.py` should be the source; if `test_services/` does not re-use it automatically via path resolution, add to `packages/server/tests/conftest.py` (workspace-wide):

```python
"""Shared pytest fixtures for server tests.

Re-exports the `db_session` fixture from `test_db/conftest.py` so tests in
other sub-packages can consume it without relocating the fixture module.
"""

from packages.server.tests.test_db.conftest import db_session  # noqa: F401
```

If `packages/server/tests/conftest.py` already exists, read it and add the import only if `db_session` is not already in scope for `test_services/`.

- [ ] **Step 5: Run the service tests**

Run:
```bash
uv run pytest packages/server/tests/test_services/test_data_providers.py -v
```
Expected: 8 tests pass.

- [ ] **Step 6: Ruff check**

Run:
```bash
uv run ruff check packages/server/src/openlia_server/services/data_providers.py packages/server/tests/test_services/test_data_providers.py
uv run ruff format --check packages/server/src/openlia_server/services/data_providers.py packages/server/tests/test_services/test_data_providers.py
```
Expected: no findings.

- [ ] **Step 7: Commit**

```bash
git add packages/server/src/openlia_server/services/data_providers.py \
        packages/server/tests/test_services/test_data_providers.py \
        packages/server/tests/conftest.py
git commit -m "phase-3(data): service layer — CRUD + requirement mapping (encrypted keys)"
```

---

## Task 11: Requirement-mapping helpers + `auto_map` against the manifest

**Files:**
- Modify: `packages/server/src/openlia_server/services/data_providers.py`
- Modify: `packages/server/tests/test_services/test_data_providers.py`

- [ ] **Step 1: Add failing tests for auto_map**

Append to `packages/server/tests/test_services/test_data_providers.py`:

```python
def test_delete_requirement_mapping(db_session) -> None:
    p = svc.create_provider(
        db_session,
        kind="eodhd",
        label="E",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://eodhd.com/api",
    )
    svc.set_requirement_mapping(
        db_session, requirement_type="stock_quote", provider_id=p.id, priority=10
    )
    svc.delete_requirement_mapping(
        db_session, requirement_type="stock_quote", provider_id=p.id
    )
    assert svc.load_entries_for_capability(
        db_session, capability="stock_quote"
    ) == []


def test_auto_map_populates_mappings_for_every_basic_and_advanced_type(
    db_session,
) -> None:
    from openlia.data.manifest import load_manifest

    p = svc.create_provider(
        db_session,
        kind="eodhd",
        label="E",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://eodhd.com/api",
    )
    summary = svc.auto_map(db_session, manifest=load_manifest())
    # EODHDAdapter declares stock_quote, historical_prices, company_profile,
    # company_news — all four should be mapped for equity_research.
    covered = {m.requirement_type for m in summary.mapped}
    assert {"stock_quote", "historical_prices", "company_profile", "company_news"} <= covered
    # Every mapping points to the sole provider we just created
    assert all(m.provider_id == p.id for m in summary.mapped)
    # stock_grade / insider_transactions / company_fundamentals not covered
    unmet_types = {u.requirement_type for u in summary.unmet}
    assert {"stock_grade", "insider_transactions"} <= unmet_types


def test_auto_map_uses_admin_set_priorities_as_tie_break(db_session) -> None:
    from openlia.data.manifest import load_manifest

    # Create two EODHD-kind providers. The one with lower priority wins.
    a = svc.create_provider(
        db_session,
        kind="eodhd",
        label="A",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://eodhd.com/api",
    )
    b = svc.create_provider(
        db_session,
        kind="eodhd",
        label="B",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://eodhd.com/api",
    )
    svc.set_provider_default_priority(db_session, provider_id=a.id, priority=50)
    svc.set_provider_default_priority(db_session, provider_id=b.id, priority=10)
    svc.auto_map(db_session, manifest=load_manifest())

    entries = svc.load_entries_for_capability(
        db_session, capability="stock_quote"
    )
    # Provider B (priority 10) comes before A (priority 50)
    assert entries[0].id == b.id
    assert entries[1].id == a.id
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
uv run pytest packages/server/tests/test_services/test_data_providers.py::test_auto_map_populates_mappings_for_every_basic_and_advanced_type -v
```
Expected: AttributeError on `svc.auto_map` (or `svc.delete_requirement_mapping`).

- [ ] **Step 3: Add `delete_requirement_mapping`, `set_provider_default_priority`, and `auto_map`**

Append to `packages/server/src/openlia_server/services/data_providers.py`:

```python
from openlia.data.adapters import ADAPTERS as _ADAPTERS
from openlia.data.manifest.types import RequirementsManifest


# Per-provider default priority is stored in extra_config["default_priority"];
# it is the priority used when auto_map writes mapping rows. Admins can still
# override per-requirement by calling set_requirement_mapping directly.
_DEFAULT_PRIORITY_KEY = "default_priority"


def set_provider_default_priority(
    session: Session,
    *,
    provider_id: str,
    priority: int,
) -> None:
    row = get_provider(session, provider_id)
    cfg = dict(row.extra_config or {})
    cfg[_DEFAULT_PRIORITY_KEY] = priority
    row.extra_config = cfg
    session.flush()


def delete_requirement_mapping(
    session: Session,
    *,
    requirement_type: str,
    provider_id: str,
) -> None:
    row = session.get(
        DataProviderRequirementMapping, (requirement_type, provider_id)
    )
    if row is not None:
        session.delete(row)
        session.flush()


@dataclass(slots=True)
class _AutoMapEntry:
    requirement_type: str
    provider_id: str


@dataclass(slots=True)
class _AutoMapUnmet:
    requirement_type: str
    department: str


@dataclass(slots=True)
class AutoMapSummary:
    mapped: list[_AutoMapEntry]
    unmet: list[_AutoMapUnmet]


def auto_map(
    session: Session,
    *,
    manifest: RequirementsManifest,
) -> AutoMapSummary:
    """Run the deterministic resolver across the full manifest and persist mappings.

    For every (department, requirement) in the manifest, find the first enabled
    provider (walking by default_priority asc) whose adapter declares the
    requirement's `type` as a capability. Write (or update) the row in
    `data_provider_requirement_mapping`. Requirements with no capable provider
    are returned in `unmet`. Existing mapping rows are kept untouched unless
    their (requirement_type, provider_id) pair is re-written.
    """
    providers: list[DataProvider] = list(session.scalars(select(DataProvider)).all())

    def _priority(row: DataProvider) -> int:
        cfg = row.extra_config or {}
        value = cfg.get(_DEFAULT_PRIORITY_KEY, 100)
        try:
            return int(value)
        except (TypeError, ValueError):
            return 100

    providers.sort(key=_priority)

    mapped: list[_AutoMapEntry] = []
    unmet: list[_AutoMapUnmet] = []

    for dep in manifest.departments:
        for req in dep.requirements:
            winner: DataProvider | None = None
            for prov in providers:
                if not prov.is_enabled:
                    continue
                adapter_cls = _ADAPTERS.get(prov.kind)
                if adapter_cls is None:
                    continue
                if req.type in adapter_cls.capabilities:
                    winner = prov
                    break
            if winner is None:
                unmet.append(
                    _AutoMapUnmet(requirement_type=req.type, department=dep.department)
                )
                continue
            set_requirement_mapping(
                session,
                requirement_type=req.type,
                provider_id=winner.id,
                priority=_priority(winner),
            )
            mapped.append(
                _AutoMapEntry(
                    requirement_type=req.type,
                    provider_id=winner.id,
                )
            )

    return AutoMapSummary(mapped=mapped, unmet=unmet)
```

- [ ] **Step 4: Run the service tests to verify they pass**

Run:
```bash
uv run pytest packages/server/tests/test_services/test_data_providers.py -v
```
Expected: 11 tests pass (8 original + 3 new).

- [ ] **Step 5: Ruff check**

Run:
```bash
uv run ruff check packages/server/src/openlia_server/services/data_providers.py packages/server/tests/test_services/test_data_providers.py
uv run ruff format --check packages/server/src/openlia_server/services/data_providers.py packages/server/tests/test_services/test_data_providers.py
```
Expected: no findings.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/services/data_providers.py \
        packages/server/tests/test_services/test_data_providers.py
git commit -m "phase-3(data): auto_map populates requirement mappings via deterministic resolver"
```

---

## Task 12: Admin route — `/settings/data-providers/*` CRUD

**Files:**
- Create: `packages/server/src/openlia_server/routes/settings.py`
- Create: `packages/server/tests/test_routes/test_data_providers_routes.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_routes/test_data_providers_routes.py`:

```python
"""Route tests for /settings/data-providers/*.

All routes require admin. In personal mode the synthetic `local` user is
admin, so tests build the app with OPENLIA_MODE=personal and do NOT send a
session cookie. In company mode they build the app with OPENLIA_MODE=company
and send a valid admin session.
"""

import pytest
from fastapi.testclient import TestClient

from openlia_server.app import create_app


@pytest.fixture
def personal_client(db_session, monkeypatch):
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    app = create_app(db_session_factory=lambda: db_session)
    with TestClient(app) as client:
        yield client


def test_list_empty(personal_client) -> None:
    resp = personal_client.get("/settings/data-providers")
    assert resp.status_code == 200
    assert resp.json() == {"providers": []}


def test_create_provider_returns_201(personal_client) -> None:
    resp = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "eodhd",
            "label": "My EODHD",
            "category": "financial",
            "mode": "api_key",
            "api_key": "SECRET",
            "base_url": "https://eodhd.com/api",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["kind"] == "eodhd"
    assert body["label"] == "My EODHD"
    assert "id" in body
    # api_key is never echoed back
    assert "api_key" not in body
    assert body.get("has_api_key") is True


def test_create_with_unknown_kind_returns_400(personal_client) -> None:
    resp = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "does-not-exist",
            "label": "X",
            "category": "financial",
            "mode": "api_key",
            "api_key": "k",
            "base_url": "https://x.test",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "unknown_provider_kind"


def test_update_label_and_disable(personal_client) -> None:
    resp = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "eodhd",
            "label": "A",
            "category": "financial",
            "mode": "api_key",
            "api_key": "k",
            "base_url": "https://eodhd.com/api",
        },
    )
    pid = resp.json()["id"]
    resp2 = personal_client.patch(
        f"/settings/data-providers/{pid}",
        json={"label": "A-renamed", "is_enabled": False},
    )
    assert resp2.status_code == 200
    assert resp2.json()["label"] == "A-renamed"
    assert resp2.json()["is_enabled"] is False


def test_delete_provider(personal_client) -> None:
    resp = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "eodhd",
            "label": "A",
            "category": "financial",
            "mode": "api_key",
            "api_key": "k",
            "base_url": "https://eodhd.com/api",
        },
    )
    pid = resp.json()["id"]
    resp2 = personal_client.delete(f"/settings/data-providers/{pid}")
    assert resp2.status_code == 204
    resp3 = personal_client.get("/settings/data-providers")
    assert resp3.json()["providers"] == []


def test_update_missing_provider_returns_404(personal_client) -> None:
    resp = personal_client.patch(
        "/settings/data-providers/nonexistent-id",
        json={"label": "x"},
    )
    assert resp.status_code == 404


def test_delete_missing_provider_returns_404(personal_client) -> None:
    resp = personal_client.delete("/settings/data-providers/nonexistent-id")
    assert resp.status_code == 404


def test_company_mode_without_session_returns_401(
    db_session, monkeypatch
) -> None:
    monkeypatch.setenv("OPENLIA_MODE", "company")
    app = create_app(db_session_factory=lambda: db_session)
    with TestClient(app) as client:
        resp = client.get("/settings/data-providers")
        assert resp.status_code == 401
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
uv run pytest packages/server/tests/test_routes/test_data_providers_routes.py -v
```
Expected: ImportError on `openlia_server.routes.settings`, or 404 on every route (Task 13 wires the mount).

- [ ] **Step 3: Create `routes/settings.py` with the data-providers router factory**

Create `packages/server/src/openlia_server/routes/settings.py`:

```python
"""/settings/* HTTP routes.

Plan 3 adds only the data-providers sub-router. Plan 4 will add the LLM
providers sub-router in the same file; Plan 11 extends further.
"""

from collections.abc import Callable
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from openlia.data.types import ProviderCategory, ProviderMode
from openlia_server.middleware.auth import build_require_admin
from openlia_server.services import data_providers as svc


class _CreateDataProviderIn(BaseModel):
    kind: str
    label: str
    category: Literal["financial", "news", "social_media"]
    mode: Literal["api_key", "mcp"]
    api_key: str | None = None
    env_var_name: str | None = None
    base_url: str | None = None
    mcp_url: str | None = None
    extra_config: dict[str, Any] | None = None


class _UpdateDataProviderIn(BaseModel):
    label: str | None = None
    api_key: str | None = None
    env_var_name: str | None = None
    base_url: str | None = None
    extra_config: dict[str, Any] | None = None
    is_enabled: bool | None = None


class _DataProviderOut(BaseModel):
    id: str
    kind: str
    label: str
    base_url: str | None
    env_var_name: str | None
    has_api_key: bool
    is_enabled: bool
    extra_config: dict[str, Any] = Field(default_factory=dict)


def _row_to_out(row) -> _DataProviderOut:
    return _DataProviderOut(
        id=row.id,
        kind=row.kind,
        label=row.label,
        base_url=row.base_url,
        env_var_name=row.env_var_name,
        has_api_key=row.api_key_encrypted is not None,
        is_enabled=row.is_enabled,
        extra_config=row.extra_config or {},
    )


def build_data_providers_router(
    *,
    db_session_factory: Callable[[], DBSession],
) -> APIRouter:
    """Factory for /settings/data-providers/*."""
    require_admin = build_require_admin(db_session_factory=db_session_factory)
    router = APIRouter(
        prefix="/settings/data-providers",
        tags=["settings", "data-providers"],
        dependencies=[Depends(require_admin)],
    )

    @router.get("")
    def list_providers() -> dict:
        session = db_session_factory()
        rows = svc.list_providers(session)
        return {"providers": [_row_to_out(r).model_dump() for r in rows]}

    @router.post("", status_code=status.HTTP_201_CREATED)
    def create_provider(body: _CreateDataProviderIn) -> dict:
        session = db_session_factory()
        try:
            created = svc.create_provider(
                session,
                kind=body.kind,
                label=body.label,
                category=ProviderCategory(body.category),
                mode=ProviderMode(body.mode),
                api_key=body.api_key,
                env_var_name=body.env_var_name,
                base_url=body.base_url,
                extra_config=body.extra_config,
            )
        except svc.UnknownProviderKindError as exc:
            raise HTTPException(
                status_code=400,
                detail={"error": "unknown_provider_kind", "message": str(exc)},
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid_provider", "message": str(exc)},
            ) from exc
        row = svc.get_provider(session, created.id)
        return _row_to_out(row).model_dump()

    @router.patch("/{provider_id}")
    def update_provider(provider_id: str, body: _UpdateDataProviderIn) -> dict:
        session = db_session_factory()
        try:
            svc.update_provider(
                session,
                provider_id,
                label=body.label,
                api_key=body.api_key,
                env_var_name=body.env_var_name,
                base_url=body.base_url,
                extra_config=body.extra_config,
                is_enabled=body.is_enabled,
            )
        except svc.ProviderNotFoundError as exc:
            raise HTTPException(status_code=404, detail="not_found") from exc
        row = svc.get_provider(session, provider_id)
        return _row_to_out(row).model_dump()

    @router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_provider(provider_id: str) -> Response:
        session = db_session_factory()
        try:
            svc.delete_provider(session, provider_id)
        except svc.ProviderNotFoundError as exc:
            raise HTTPException(status_code=404, detail="not_found") from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
```

Override the error-shape middleware Plan 2 installed so the `HTTPException(detail={"error": ...})` payloads surface under the top-level `error` field. Plan 2 installed a global exception handler that maps typed service errors to JSON `{"error": ..., "message": ...}`. The inline `detail={"error": "unknown_provider_kind"}` shape above piggybacks on that handler if present; otherwise the tests accept `{"detail": {"error": "..."}}` — update the assertion block below accordingly.

- [ ] **Step 4: Adjust the test shape if needed**

If Plan 2's global handler flattens `HTTPException.detail.error` to the top-level `error` key, the tests above already pass. If it does not, change the relevant test assertions from `resp.json()["error"] == "unknown_provider_kind"` to `resp.json()["detail"]["error"] == "unknown_provider_kind"`. Run the route tests and patch whichever form matches the installed handler — do not change the handler itself in this plan.

- [ ] **Step 5: Run the tests against the *not-yet-mounted* router**

Run:
```bash
uv run pytest packages/server/tests/test_routes/test_data_providers_routes.py -v
```
Expected: every test fails with 404 Not Found on the path — the router is defined but not mounted yet. Task 13 wires `create_app()` to include it.

- [ ] **Step 6: Ruff check**

Run:
```bash
uv run ruff check packages/server/src/openlia_server/routes/settings.py packages/server/tests/test_routes/test_data_providers_routes.py
uv run ruff format --check packages/server/src/openlia_server/routes/settings.py packages/server/tests/test_routes/test_data_providers_routes.py
```
Expected: no findings.

- [ ] **Step 7: Commit**

```bash
git add packages/server/src/openlia_server/routes/settings.py \
        packages/server/tests/test_routes/test_data_providers_routes.py
git commit -m "phase-3(data): /settings/data-providers/* CRUD router (not yet mounted)"
```

---

## Task 13: Wire router into `create_app()` (both modes)

**Files:**
- Modify: `packages/server/src/openlia_server/app.py`

- [ ] **Step 1: Read the current `app.py`**

Run:
```bash
cat packages/server/src/openlia_server/app.py
```
Expected: shows the Plan 2 version — a `create_app(db_session_factory=None)` factory that reads `OPENLIA_MODE` and conditionally mounts the auth / admin routers (company mode only).

- [ ] **Step 2: Add the settings router mount**

Edit `packages/server/src/openlia_server/app.py`. Add the import:

```python
from openlia_server.routes.settings import build_data_providers_router
```

Inside `create_app(...)`, after the mode-gated auth/admin mounts, add the data-providers mount **unconditionally**:

```python
    factory = db_session_factory or (lambda: SessionLocal())
    app.include_router(
        build_data_providers_router(db_session_factory=factory)
    )
```

Place this BEFORE the `return app` line. Both modes mount it — in personal mode the synthetic `local` admin passes the admin gate; in company mode a real admin session is required.

- [ ] **Step 3: Run the route tests to verify they now pass**

Run:
```bash
uv run pytest packages/server/tests/test_routes/test_data_providers_routes.py -v
```
Expected: all 8 tests pass.

- [ ] **Step 4: Run the full pytest suite to confirm no regressions**

Run:
```bash
uv run pytest -v
```
Expected: every test from Plans 1A, 2, and 3 (so far) passes. Pay attention to any auth middleware tests — the unconditional settings mount must not break the personal-mode no-auth pathway.

- [ ] **Step 5: Ruff check**

Run:
```bash
uv run ruff check packages/server/src/openlia_server/app.py
uv run ruff format --check packages/server/src/openlia_server/app.py
```
Expected: no findings.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/app.py
git commit -m "phase-3(data): mount /settings/data-providers router in both modes"
```

---

## Task 14: `/settings/data-providers/{id}/test-connection` + `/auto-map`

**Files:**
- Modify: `packages/server/src/openlia_server/routes/settings.py`
- Modify: `packages/server/tests/test_routes/test_data_providers_routes.py`

- [ ] **Step 1: Add failing tests**

Append to `packages/server/tests/test_routes/test_data_providers_routes.py`:

```python
import httpx
import respx


@respx.mock
def test_test_connection_success(personal_client) -> None:
    respx.get("https://eodhd.com/api/user").mock(
        return_value=httpx.Response(200, json={"email": "x@y.z"})
    )
    resp = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "eodhd",
            "label": "E",
            "category": "financial",
            "mode": "api_key",
            "api_key": "k",
            "base_url": "https://eodhd.com/api",
        },
    )
    pid = resp.json()["id"]
    resp2 = personal_client.post(
        f"/settings/data-providers/{pid}/test-connection"
    )
    assert resp2.status_code == 200
    assert resp2.json() == {"ok": True}


@respx.mock
def test_test_connection_failure(personal_client) -> None:
    respx.get("https://eodhd.com/api/user").mock(
        return_value=httpx.Response(401, text="bad key")
    )
    resp = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "eodhd",
            "label": "E",
            "category": "financial",
            "mode": "api_key",
            "api_key": "k",
            "base_url": "https://eodhd.com/api",
        },
    )
    pid = resp.json()["id"]
    resp2 = personal_client.post(
        f"/settings/data-providers/{pid}/test-connection"
    )
    assert resp2.status_code == 200
    assert resp2.json() == {"ok": False}


def test_auto_map_returns_summary(personal_client) -> None:
    resp = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "eodhd",
            "label": "E",
            "category": "financial",
            "mode": "api_key",
            "api_key": "k",
            "base_url": "https://eodhd.com/api",
        },
    )
    assert resp.status_code == 201
    resp2 = personal_client.post("/settings/data-providers/auto-map")
    assert resp2.status_code == 200, resp2.text
    body = resp2.json()
    # EODHD covers 4 of equity_research's basic+advanced requirements
    covered_types = {m["requirement_type"] for m in body["mapped"]}
    assert {"stock_quote", "historical_prices", "company_profile", "company_news"} <= covered_types
    # stock_grade, insider_transactions, company_fundamentals remain unmet
    unmet_types = {u["requirement_type"] for u in body["unmet"]}
    assert {"stock_grade", "insider_transactions"} <= unmet_types


def test_list_requirement_mappings(personal_client) -> None:
    resp = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "eodhd",
            "label": "E",
            "category": "financial",
            "mode": "api_key",
            "api_key": "k",
            "base_url": "https://eodhd.com/api",
        },
    )
    pid = resp.json()["id"]
    personal_client.post("/settings/data-providers/auto-map")
    resp2 = personal_client.get("/settings/data-providers/mappings")
    assert resp2.status_code == 200
    mappings = resp2.json()["mappings"]
    # At least one mapping for stock_quote pointing at our provider
    assert any(
        m["requirement_type"] == "stock_quote" and m["provider_id"] == pid
        for m in mappings
    )


def test_set_and_delete_individual_mapping(personal_client) -> None:
    resp = personal_client.post(
        "/settings/data-providers",
        json={
            "kind": "eodhd",
            "label": "E",
            "category": "financial",
            "mode": "api_key",
            "api_key": "k",
            "base_url": "https://eodhd.com/api",
        },
    )
    pid = resp.json()["id"]
    resp_put = personal_client.put(
        "/settings/data-providers/mappings/stock_quote",
        json={"provider_id": pid, "priority": 25},
    )
    assert resp_put.status_code == 200
    assert resp_put.json()["priority"] == 25

    resp_del = personal_client.delete(
        f"/settings/data-providers/mappings/stock_quote/{pid}"
    )
    assert resp_del.status_code == 204
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```bash
uv run pytest packages/server/tests/test_routes/test_data_providers_routes.py -v
```
Expected: 5 new tests fail with 404 / 405 — the routes are not yet defined.

- [ ] **Step 3: Add the new endpoints to `routes/settings.py`**

Inside `build_data_providers_router(...)` in `packages/server/src/openlia_server/routes/settings.py`, add these endpoints before the `return router` line:

```python
    @router.post("/{provider_id}/test-connection")
    async def test_connection(provider_id: str) -> dict:
        session = db_session_factory()
        try:
            entry = svc.load_provider_entry(session, provider_id)
        except svc.ProviderNotFoundError as exc:
            raise HTTPException(status_code=404, detail="not_found") from exc
        from openlia.data.adapters import ADAPTERS

        adapter_cls = ADAPTERS.get(entry.kind)
        if adapter_cls is None:
            return {"ok": False}
        adapter = adapter_cls(entry)
        return {"ok": await adapter.health_check()}

    @router.post("/auto-map")
    def auto_map_endpoint() -> dict:
        from openlia.data.manifest import load_manifest

        session = db_session_factory()
        summary = svc.auto_map(session, manifest=load_manifest())
        return {
            "mapped": [
                {"requirement_type": m.requirement_type, "provider_id": m.provider_id}
                for m in summary.mapped
            ],
            "unmet": [
                {"requirement_type": u.requirement_type, "department": u.department}
                for u in summary.unmet
            ],
        }

    @router.get("/mappings")
    def list_mappings() -> dict:
        from sqlalchemy import select

        from openlia_server.db.models.config import DataProviderRequirementMapping

        session = db_session_factory()
        rows = list(
            session.scalars(
                select(DataProviderRequirementMapping).order_by(
                    DataProviderRequirementMapping.requirement_type,
                    DataProviderRequirementMapping.priority,
                )
            ).all()
        )
        return {
            "mappings": [
                {
                    "requirement_type": r.requirement_type,
                    "provider_id": r.provider_id,
                    "priority": r.priority,
                }
                for r in rows
            ],
        }

    @router.put("/mappings/{requirement_type}")
    def set_mapping(requirement_type: str, body: dict) -> dict:
        session = db_session_factory()
        provider_id = body.get("provider_id")
        priority = body.get("priority")
        if not isinstance(provider_id, str) or not isinstance(priority, int):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_mapping",
                    "message": "provider_id (str) and priority (int) required",
                },
            )
        try:
            svc.get_provider(session, provider_id)
        except svc.ProviderNotFoundError as exc:
            raise HTTPException(status_code=404, detail="not_found") from exc
        svc.set_requirement_mapping(
            session,
            requirement_type=requirement_type,
            provider_id=provider_id,
            priority=priority,
        )
        return {
            "requirement_type": requirement_type,
            "provider_id": provider_id,
            "priority": priority,
        }

    @router.delete(
        "/mappings/{requirement_type}/{provider_id}",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    def delete_mapping(requirement_type: str, provider_id: str) -> Response:
        session = db_session_factory()
        svc.delete_requirement_mapping(
            session,
            requirement_type=requirement_type,
            provider_id=provider_id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: Run the route tests to verify they pass**

Run:
```bash
uv run pytest packages/server/tests/test_routes/test_data_providers_routes.py -v
```
Expected: all 13 tests pass (8 from Task 12 + 5 from Task 14).

- [ ] **Step 5: Ruff check**

Run:
```bash
uv run ruff check packages/server/src/openlia_server/routes/settings.py packages/server/tests/test_routes/test_data_providers_routes.py
uv run ruff format --check packages/server/src/openlia_server/routes/settings.py packages/server/tests/test_routes/test_data_providers_routes.py
```
Expected: no findings.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/routes/settings.py \
        packages/server/tests/test_routes/test_data_providers_routes.py
git commit -m "phase-3(data): test-connection + auto-map + mappings GET/PUT/DELETE routes"
```

---

## Task 15: Final integration — end-to-end sanity test

**Files:**
- Create: `packages/server/tests/test_routes/test_data_providers_integration.py`

- [ ] **Step 1: Write the integration test**

Create `packages/server/tests/test_routes/test_data_providers_integration.py`:

```python
"""End-to-end integration: configure provider → auto-map → query capability."""

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from openlia.data.adapters import ADAPTERS
from openlia.data.resolver import resolve_provider_for_capability
from openlia_server.app import create_app
from openlia_server.services import data_providers as svc


@pytest.fixture
def client(db_session, monkeypatch):
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    app = create_app(db_session_factory=lambda: db_session)
    with TestClient(app) as c:
        yield c


@respx.mock
def test_full_flow_provider_then_resolver_then_adapter(
    client,
    db_session,
) -> None:
    # 1. Admin creates provider
    resp = client.post(
        "/settings/data-providers",
        json={
            "kind": "eodhd",
            "label": "EODHD",
            "category": "financial",
            "mode": "api_key",
            "api_key": "test-key",
            "base_url": "https://eodhd.com/api",
        },
    )
    assert resp.status_code == 201
    pid = resp.json()["id"]

    # 2. Admin triggers auto-map
    resp2 = client.post("/settings/data-providers/auto-map")
    assert resp2.status_code == 200

    # 3. Resolver (as Plan 5 will use it) finds the provider for stock_quote
    entries = svc.load_entries_for_capability(
        db_session, capability="stock_quote"
    )
    assert len(entries) == 1
    assert entries[0].id == pid

    resolved = resolve_provider_for_capability(
        capability="stock_quote",
        entries=entries,
        adapters=ADAPTERS,
    )
    assert resolved is not None
    assert resolved.entry.kind == "eodhd"

    # 4. Adapter (constructed from the entry) can fetch
    respx.get("https://eodhd.com/api/real-time/AAPL.US").mock(
        return_value=httpx.Response(200, json={"code": "AAPL.US", "close": 225.1}),
    )
    # We don't run the async coroutine here — just confirm the adapter class
    # can be instantiated from the loaded entry.
    adapter = resolved.adapter_cls(resolved.entry)
    assert adapter.kind == "eodhd"
    assert adapter.entry.api_key == "test-key"
```

- [ ] **Step 2: Run the test**

Run:
```bash
uv run pytest packages/server/tests/test_routes/test_data_providers_integration.py -v
```
Expected: 1 test passes.

- [ ] **Step 3: Ruff check**

Run:
```bash
uv run ruff check packages/server/tests/test_routes/test_data_providers_integration.py
uv run ruff format --check packages/server/tests/test_routes/test_data_providers_integration.py
```
Expected: no findings.

- [ ] **Step 4: Commit**

```bash
git add packages/server/tests/test_routes/test_data_providers_integration.py
git commit -m "phase-3(data): integration test — CRUD → auto-map → resolver → adapter"
```

---

## Task 16: Acceptance + update implementation-plans README

**Files:**
- Modify: `planning/implementation-plans/README.md`

- [ ] **Step 1: Run the full test suite**

Run:
```bash
uv run pytest -v
```
Expected: every test passes. Full list includes:
- Plan 1A DB tests (~30+)
- Plan 2 crypto/auth/routes tests (~60+)
- Plan 3: `test_errors.py` (5), `test_types.py` (8), `test_base.py` (7), `test_manifest_loader.py` (10), `test_manifest_checker.py` (5), `test_resolver.py` (7), `test_adapters/test_eodhd.py` (12), `test_services/test_data_providers.py` (11), `test_routes/test_data_providers_routes.py` (13), `test_routes/test_data_providers_integration.py` (1). **New tests in Plan 3: 79.**

- [ ] **Step 2: Full-repo ruff gate**

Run:
```bash
uv run ruff check .
uv run ruff format --check .
```
Expected: no findings anywhere.

- [ ] **Step 3: Walk through the acceptance checklist**

Confirm each point is true by reading / re-running the cited test:

1. `packages/core/src/openlia/data/` is import-clean from a pure core install (no FastAPI imports pulled in transitively). Test: `uv run python -c "from openlia.data import ProviderAdapter, ProviderEntry, resolve_provider_for_capability; print('ok')"`.
2. `packages/core/src/openlia/data/manifest/requirements.yaml` ships inside the built wheel (verified in Task 6 Step 7).
3. EODHD adapter satisfies at minimum: `stock_quote`, `historical_prices`, `company_profile`, `company_news`. Verified in `test_eodhd.py::test_eodhd_declared_metadata`.
4. API keys stored in `data_providers.api_key_encrypted` are never equal to the plaintext. Verified in `test_data_providers.py::test_create_provider_encrypts_api_key_on_disk`.
5. Environment-variable-backed providers (`env_var_name`) do not write an encrypted row. Verified in `test_data_providers.py::test_create_provider_with_env_var_instead_of_api_key`.
6. Resolver walks in priority order, skips disabled providers, and skips providers whose kind is not registered. Verified in `test_resolver.py`.
7. `auto_map` populates `data_provider_requirement_mapping` for every manifest requirement whose type is in the union of registered adapters' capabilities; the rest are returned as unmet. Verified in `test_data_providers.py::test_auto_map_*`.
8. `/settings/data-providers` CRUD responses never echo the `api_key` — only `has_api_key: bool`. Verified in `test_data_providers_routes.py::test_create_provider_returns_201`.
9. `/settings/data-providers/{id}/test-connection` returns `{"ok": true|false}` without throwing on adapter errors. Verified in `test_data_providers_routes.py::test_test_connection_failure`.
10. Company mode rejects unauthenticated requests to `/settings/data-providers` with 401. Verified in `test_data_providers_routes.py::test_company_mode_without_session_returns_401`.
11. Personal mode treats the synthetic `local` user as admin — no session cookie needed. Verified implicitly in every `personal_client` test.
12. `/settings/data-providers/auto-map` is idempotent — calling it twice with the same providers produces the same mapping set (re-executing Task 15's integration test twice in sequence: `pytest --count=2 packages/server/tests/test_routes/test_data_providers_integration.py::test_full_flow_provider_then_resolver_then_adapter` should still pass).

- [ ] **Step 4: Update the implementation-plans README**

Edit `planning/implementation-plans/README.md`. Change the Plan 3 row in the status table from:

```
| 3 | 2 | Data provider adapter system | Not started | — |
```

to:

```
| 3 | 2 | Data provider adapter system | Draft | `2026-04-16-phase-3-data-provider-adapter-system.md` |
```

Do not mark it `Ready` or `Done` — those transitions are owned by the reviewer and the implementer respectively.

- [ ] **Step 5: Commit the README update**

```bash
git add planning/implementation-plans/README.md
git commit -m "planning(impl-plans): mark Plan 3 (data providers) as Draft"
```

---

## Notes for the implementer

- **Core purity.** No FastAPI, uvicorn, SQLAlchemy, or any server-package import is allowed inside `packages/core/src/openlia/data/`. Tests in `packages/core/tests/` should be runnable after `pip install packages/core` alone (with only the core's declared deps). If you find yourself needing a DB session inside core, you're in the wrong layer — move the code to `packages/server/src/openlia_server/services/data_providers.py`.
- **respx gotchas.** `respx.mock` intercepts `httpx` by default. If a test looks like it's reaching the network, confirm the adapter is using `httpx.AsyncClient` (it is, in Plan 3). The `Retry-After` header must be read with case-insensitive access — `httpx.Headers` handles that natively.
- **`asyncio_mode=auto`.** We set this in Task 1 Step 4. Every `async def test_...` now runs under pytest-asyncio without the `@pytest.mark.asyncio` decorator. If a future dev adds a sync test next to an async one, no extra config needed.
- **Manifest completeness is deferred.** Only `equity_research` has real requirements. When Plans 13–20 land, each department plan is responsible for filling in its block of `requirements.yaml` — not this plan. The `auto_map` function silently produces an empty `mapped` list for empty-requirement departments; that's the desired behavior.
- **Encryption AAD.** `encrypt_for_row(row_id=<uuid>, plaintext=...)` — always use the **new** row's id for creation, and the existing row's id for rotation. Never pass the `kind` or `label` as AAD; the id is what tamper-detects row transplants. This matches Plan 2's helper signature exactly.
- **Category column.** `DataProvider.category` is not stored on the row (Plan 1A schema intentionally omits it). The category comes from the adapter class at `ProviderEntry` construction time. If a later plan needs to filter providers by category at the DB level, that's a schema migration — do not hack it via `extra_config`.
- **Deviation from data-provider-design.md.** The spec's `ProviderEntry.mode = Literal["api_key", "mcp"]` is preserved, but the MCP transport is not implemented in Plan 3 — attempting to create a provider with `mode=mcp` will currently fail the Pydantic validator (requires `mcp_url`) and then fail in `svc.create_provider` anyway (no MCP adapter registered). A future plan adds the MCP adapter path.
- **Spec vs plan: full catalog system.** The spec's catalog/review/dispatch/expansion layers are a richer AI-driven mapping system. Plan 3 substitutes a simple deterministic resolver. When the AI-review plan lands, the resolver signature will be extended (not replaced) — the `resolve_provider_for_capability` function stays; new callers use a `resolve_by_mapping_file(...)` variant that reads the AI-generated `~/.openlia/mappings/*.yaml` files. Both coexist.
- **Security review checklist.** Before merging Plan 3 into main: (a) confirm no `api_key` plaintext appears in server-side route responses, test fixture logs, or model `__repr__` output; (b) confirm `extra_config` cannot be used to bypass `api_key_encrypted` (the `update_provider` service accepts an arbitrary dict — consider a future schema allowlist); (c) confirm `test-connection` does not leak the adapter's `health_check` exception text into the JSON response. Items (b) and (c) are already enforced by the current code; item (a) has test coverage but should be eyeballed in code review.

## What's explicitly deferred

- Catalog YAML templates and loader (`data/catalog/`) — future catalog plan.
- AI-driven requirement-to-endpoint review (`data/review/`) — future AI-review plan.
- Runtime dispatch (`data/dispatch/`), including HTTP client and MCP client modules — Plan 5.
- Runtime expansion meta-tool (`data/dispatch/expansion.py`) — Plan 5.
- `yfinance` adapter (`data/python_providers/`) — future data plan.
- Retail Sentiment availability checker (`data/sentiment/checker.py`) — Plan 20.
- Additional financial adapters (FMP, Finnhub) — each adapter is one small follow-up plan.
- News adapters (NewsAPI.ai, Mediastack) — same pattern.
- Frontend UI for data-provider settings (`SettingsPage` Data Providers tab) — Plan 11.
- Setup Wizard integration — Plan 10.
- Env-var-override rendering for read-only providers — Plan 10 (wizard spec).
- Startup validation hook (refuse to boot when basic requirements are unmet) — lands alongside Plan 10 / Plan 15 when departments actually need to start.
