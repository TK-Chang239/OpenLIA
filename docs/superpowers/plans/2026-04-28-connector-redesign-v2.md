# Connector Redesign v2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the connector subsystem from main as a fresh branch (`refactor/connector-redesign-v2`), implementing the three-layer customization model (MCP / skills slot / Python lib), unified Connector with multi-mode launch, structured callable specs for runner needs, conversation-scoped runtime tool routing with an escalation tool, and graceful department disable.

**Architecture summary:** Wizard-time adapter LLM produces structured `CallableSpec`s for declarative runner needs (`<dept>.needs.yaml`) via Python-lib introspection or MCP tool resolution. Runtime router LLM picks per-conversation tool subsets for chat departments using curated `<dept>.routing_context.md`. Deterministic runners walk persisted callable specs with no LLM in the runtime path. Department health (`active`/`disabled`) is derived from declared required categories and runner-need resolution; it surfaces in sidebar, Settings, dept page, scheduler, and the API boundary (409 on mutating endpoints when disabled).

**Tech stack:** Python 3.12+ (uv, ruff), FastAPI, SQLAlchemy 2 + Alembic, Anthropic SDK (Haiku for routing, user-quick-tier for adapter), MCP, React 18 + TypeScript + Vite + Vitest, pytest.

**Scope:**
- Canonical reference spec: `docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md`
- Supersedes: `docs/superpowers/plans/2026-04-27-connector-dataflow-redesign.md`

**Strategy:** Branch `refactor/connector-redesign-v2` from current `main`. Re-do the seven cutover-branch deletions as fresh commits. Then build forward, one component per phase. ~38 commits total. Each phase compiles + passes tests independently.

**Path B confirmation:** The earlier `refactor/connector-dataflow-redesign` branch (Path A: amend cutover in place) is archived. We do not cherry-pick from it. Technical content from its plan (the 5015-line predecessor) is reused freely as authoritative reference, but the commit graph starts fresh.

**Decisions locked during grilling (2026-04-27):**
- Q1: Supersede with new plan doc (this file).
- Q2: Candidate pool for the runtime router = full validated tool inventory across all connectors, with NO per-dept category filter (spec §8.1). Drop `tools_for_department`, `Dispatcher.allowlist`, and category-based runtime gating.
- Q3: Drop encryption entirely — `Connector.api_key_encrypted` becomes `Connector.secrets: dict[str, str]` plaintext map. Mirror change on `LlmProvider`. Spec edited accordingly (§3.2, §3.3, §4.1, §6.2, §11.2, §11.5).
- Q4: Connector re-validation is user-triggered only (spec §7.5). No weekly cron.
- Q5 absorptions: dept-flow per spec §10.1 — only MR and RS are deterministic; PT, MB, ER, EU, Sec are chat-flow. PT/MB scheduled execution = system-prompted chat turn. No "hybrid" runner kind. Connector ownership = global (admin-installed). Day-1 catalog = empty (spec §13.5). Web search = just another category, no special-case routing.

---

## Table of contents

- [Phase 0 — Pre-flight: branch from main](#phase-0--pre-flight-branch-from-main)
- [Phase 1 — Re-do the seven cutover deletions](#phase-1--re-do-the-seven-cutover-deletions)
- [Phase 2 — Component 1: Database schema + migrations](#phase-2--component-1-database-schema--migrations)
- [Phase 3 — Component 2: Core connector types](#phase-3--component-2-core-connector-types)
- [Phase 4 — Component 3: Dispatcher](#phase-4--component-3-dispatcher)
- [Phase 5 — Component 4: Transports](#phase-5--component-4-transports)
- [Phase 6 — Component 5: Wizard-time adapter LLM](#phase-6--component-5-wizard-time-adapter-llm)
- [Phase 7 — Component 6: Built-in template registry](#phase-7--component-6-built-in-template-registry)
- [Phase 8 — Component 7: Department artifacts](#phase-8--component-7-department-artifacts)
- [Phase 9 — Component 8: Runtime](#phase-9--component-8-runtime)
- [Phase 10 — Component 9: Department health](#phase-10--component-9-department-health)
- [Phase 11 — Component 10: Frontend](#phase-11--component-10-frontend)
- [Phase 12 — Component 11: Adjacent subsystems](#phase-12--component-11-adjacent-subsystems)
- [Phase 13 — Component 12: Quality + docs](#phase-13--component-12-quality--docs)

---

## Phase 0 — Pre-flight: branch from main

### Task 0.1 — Verify clean main + create branch

**Files:** (none — branch ops)

- [ ] **Step 1: Confirm working tree clean on main.**

```bash
git status
git log --oneline -1
```

Expected: HEAD on `main`. Untracked files (`.agents/`, `memo.txt`, `skills-lock.json`) are fine.

- [ ] **Step 2: Fetch all remotes and prune.**

```bash
git fetch --all --prune
```

- [ ] **Step 3: Create branch.**

```bash
git checkout -b refactor/connector-redesign-v2 main
```

- [ ] **Step 4: Push the branch upstream and confirm.**

```bash
git push -u origin refactor/connector-redesign-v2
git rev-parse --abbrev-ref HEAD
```

Expected: `refactor/connector-redesign-v2`.

### Task 0.2 — Mark the predecessor plan superseded

**Files:**
- `docs/superpowers/plans/2026-04-27-connector-dataflow-redesign.md`

- [ ] **Step 1: Add a header note at top of the file** (immediately under the H1 title):

```markdown
> **SUPERSEDED 2026-04-28** by `docs/superpowers/plans/2026-04-28-connector-redesign-v2.md`. The strategy described here (amend cutover branch in place) was abandoned; the v2 plan rebuilds from `main` instead. Technical content remains useful as reference; do not execute the steps in this document.
```

- [ ] **Step 2: Commit.**

```bash
git add docs/superpowers/plans/2026-04-27-connector-dataflow-redesign.md
git commit -m "docs(plan): mark old connector-dataflow-redesign plan superseded by v2"
```

---

## Phase 1 — Re-do the seven cutover deletions

The cutover branch (`refactor/connector-cutover`) deleted seven legacy modules. We replay those deletions as fresh commits on `refactor/connector-redesign-v2` so the v2 graph is self-contained and bisectable. Order matters: dependents first, dependencies last.

### Task 1.1 — Delete Macro Research's `_DataProvider` Protocol

**Files:**
- `packages/core/src/openlia/macro_research/protocol.py` (or wherever the legacy `_DataProvider` Protocol lives in MR)
- Any MR module that imports it

- [ ] **Step 1: Locate the MR `_DataProvider` Protocol** with `grep -rn "_DataProvider" packages/core/src/openlia/macro_research/`.
- [ ] **Step 2: Delete the Protocol module.**
- [ ] **Step 3: Drop imports from MR runtime modules** — runtime wiring is rebuilt in Phase 9, so MR temporarily has unresolved references; this is expected.
- [ ] **Step 4: Run** `uv run ruff check packages/core/src/openlia/macro_research/` — fix syntax errors only; ignore unresolved-name lint until Phase 9.
- [ ] **Step 5: Commit.**

```bash
git commit -m "refactor(mr): drop dead _DataProvider Protocol; runtime wiring pending"
```

### Task 1.2 — Delete Retail Sentiment's `_DataProvider` Protocol

**Files:**
- `packages/core/src/openlia/retail_sentiment/protocol.py` (or equivalent)

- [ ] **Step 1-4: Mirror Task 1.1 for `retail_sentiment/`.**
- [ ] **Step 5: Commit.**

```bash
git commit -m "refactor(rs): drop dead _DataProvider Protocol; runtime wiring pending"
```

### Task 1.3 — Delete server data-provider services and routes

**Files:**
- `packages/server/src/openlia_server/services/data_providers.py` (or `*_service.py` equivalents)
- `packages/server/src/openlia_server/routes/data_providers.py`
- Any `__init__.py` or `register_routes` that mounts the route module

- [ ] **Step 1: Identify** with `grep -rn "data_providers" packages/server/src/`.
- [ ] **Step 2: Delete the service module(s).**
- [ ] **Step 3: Delete the route module.**
- [ ] **Step 4: Remove the `app.include_router(data_providers.router, ...)` line** from `app.py` or wherever it mounts.
- [ ] **Step 5: Run** `uv run pytest packages/server/tests/ -k "not data_providers" --no-header -q` to confirm imports still resolve.
- [ ] **Step 6: Commit.**

```bash
git commit -m "refactor(server): delete legacy provider services + routes"
```

### Task 1.4 — Delete frontend `DataProvidersAdminPanel`

**Files:**
- `frontend/src/components/settings/admin/DataProvidersAdminPanel.tsx`
- `frontend/src/components/settings/admin/DataProvidersAdminPanel.test.tsx` (if present)
- `frontend/src/setup/setup.ts` — drop dead exports
- Any panel registry that mounts this component

- [ ] **Step 1: Delete the `.tsx` and any colocated test.**
- [ ] **Step 2: Drop dead exports from `setup.ts`.**
- [ ] **Step 3: Remove panel registry entry** if present.
- [ ] **Step 4: Run** `cd frontend && npm run build` — fix any unresolved-import errors caused by the deletion.
- [ ] **Step 5: Commit.**

```bash
git commit -m "refactor(frontend): delete legacy DataProvidersAdminPanel + setup.ts dead exports"
```

### Task 1.5 — Delete the `openlia.data` package

**Files:**
- `packages/core/src/openlia/data/` (entire directory)
- Any cross-package imports of `openlia.data.*`

- [ ] **Step 1: Locate consumers** with `grep -rn "from openlia.data" packages/`.
- [ ] **Step 2: Delete the `data/` package.**
- [ ] **Step 3: Drop unresolved imports from consumers** — they get re-wired in Phases 4-9.
- [ ] **Step 4: Run** `uv run pytest packages/core/tests/ --co -q` to confirm tests at least collect.
- [ ] **Step 5: Commit.**

```bash
git commit -m "refactor: delete openlia.data package (replaced by openlia.connectors)"
```

### Task 1.6 — Drop the `data_providers` migration table

**Files:**
- New migration: `packages/server/src/openlia_server/db/migrations/versions/2026-04-28-0001_drop_data_providers.py`
- ORM model: `packages/server/src/openlia_server/db/models/config.py` (drop `DataProvider` class if present)
- `register_all.py` — drop side-effect import of `DataProvider`

- [ ] **Step 1: Generate migration scaffold.**

```bash
uv run alembic -c packages/server/alembic.ini revision -m "drop data_providers tables"
```

Rename to the `2026-04-28-0001_drop_data_providers.py` convention.

- [ ] **Step 2: Author the migration.**

```python
"""Drop data_providers tables.

Revision ID: <generated>
Revises: <main HEAD revision>
Create Date: 2026-04-28
"""
from alembic import op
import sqlalchemy as sa

revision = "<generated>"
down_revision = "<previous revision id>"

def upgrade() -> None:
    op.drop_table("data_provider_requirement_mapping")
    op.drop_table("data_providers")

def downgrade() -> None:
    # Recreate placeholder shapes — match original baseline columns
    ...
```

- [ ] **Step 3: Drop `DataProvider` ORM class** and its registration in `register_all.py`.
- [ ] **Step 4: Apply migration locally.**

```bash
uv run alembic -c packages/server/alembic.ini upgrade head
```

- [ ] **Step 5: Run server tests; expect green.**

```bash
uv run pytest packages/server/tests/db/ -q
```

- [ ] **Step 6: Commit.**

```bash
git commit -m "feat(db): drop data_providers tables; CLI rotation iterates Connector"
```

### Task 1.7 — Retire legacy data-provider design docs

**Files:**
- `planning/specs/systems/data-provider-design.md` (or wherever the legacy spec lives)
- `planning/projectStructure.md` — replace `data_providers` references with `connectors`

- [ ] **Step 1: Delete the legacy spec.**
- [ ] **Step 2: Update `projectStructure.md`.**
- [ ] **Step 3: Commit.**

```bash
git commit -m "docs: retire data-provider-design.md; projectStructure references connectors"
```

---

## Phase 2 — Component 1: Database schema + migrations

### Task 2.1 — Migration: drop `tool_allowlists` table

**Files:**
- New migration: `2026-04-28-0100_drop_tool_allowlists.py`
- ORM: `packages/server/src/openlia_server/db/models/connectors.py` — delete `ToolAllowlist` class

- [ ] **Step 1: Author migration.**

```python
def upgrade() -> None:
    op.drop_table("tool_allowlists")

def downgrade() -> None:
    # Restore the table shape from cutover commit c3a8990 if needed.
    ...
```

- [ ] **Step 2: Delete the `ToolAllowlist` ORM class** from `connectors.py`.
- [ ] **Step 3: Apply + test.**

```bash
uv run alembic -c packages/server/alembic.ini upgrade head
uv run pytest packages/server/tests/db/ -q
```

- [ ] **Step 4: Commit.**

```bash
git commit -m "feat(db): drop tool_allowlists table; allowlist concept retired"
```

### Task 2.2 — Migration: reshape `connectors` columns

**Files:**
- New migration: `2026-04-28-0200_connectors_v2_columns.py`
- ORM: `packages/server/src/openlia_server/db/models/connectors.py`

Changes per spec §3.2 (post-Q3 edit):
- Drop `api_key_encrypted`
- Add `secrets JSON NOT NULL DEFAULT '{}'` (plaintext key→value map)
- Add `cached_python_callables JSON NULL`
- Relax `source` CHECK to include `python_lib` and `skill`
- Rename `last_validated_at` → `validated_at` (spec uses `validated_at`)
- Add `display_name VARCHAR(128) NOT NULL`
- Add `updated_at` timestamp with onupdate

- [ ] **Step 1: Author migration with batch ops** (SQLite compatibility).

```python
def upgrade() -> None:
    with op.batch_alter_table("connectors") as batch:
        batch.drop_constraint("source", type_="check")
        batch.create_check_constraint(
            "source",
            "source IN ('built_in', 'remote_mcp', 'cli_mcp', 'python_lib', 'skill')",
        )
        batch.drop_column("api_key_encrypted")
        batch.add_column(sa.Column("secrets", sa.JSON(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("cached_python_callables", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("display_name", sa.String(128), nullable=False, server_default=""))
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
        batch.alter_column("last_validated_at", new_column_name="validated_at")
```

- [ ] **Step 2: Update `Connector` ORM model.**

```python
class Connector(Base):
    __tablename__ = "connectors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")

    secrets: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    launch: Mapped[dict] = mapped_column(JSON, nullable=False)
    cached_tools: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    cached_python_callables: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)

    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True, onupdate=func.now())

    __table_args__ = (
        Index("ix_connectors_provider_id", "provider_id"),
        Index("ix_connectors_category", "category"),
        Index("ix_connectors_status", "status"),
        CheckConstraint(
            "source IN ('built_in', 'remote_mcp', 'cli_mcp', 'python_lib', 'skill')",
            name="source",
        ),
        CheckConstraint(
            "category IN ('financial', 'news', 'social', 'web_search')",
            name="category",
        ),
        CheckConstraint(
            "status IN ('pending', 'validated', 'failed')",
            name="status",
        ),
    )
```

- [ ] **Step 3: Apply + test.**
- [ ] **Step 4: Commit.**

```bash
git commit -m "feat(db): reshape connectors — secrets plaintext, cached_python_callables, validated_at, display_name"
```

### Task 2.3 — Migration: create `runner_callable_specs` table

**Files:**
- New migration: `2026-04-28-0300_runner_callable_specs.py`
- ORM: new `packages/server/src/openlia_server/db/models/connectors.py` class

Per spec §3.5: unique on `(department_id, need_id)` only.

- [ ] **Step 1: Author migration.**

```python
def upgrade() -> None:
    op.create_table(
        "runner_callable_specs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("department_id", sa.String(64), nullable=False),
        sa.Column("need_id", sa.String(64), nullable=False),
        sa.Column("connector_id", sa.String(36),
                  sa.ForeignKey("connectors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("access_mode", sa.String(16), nullable=False),
        sa.Column("spec", sa.JSON(), nullable=False),
        sa.Column("canary_value", sa.JSON(), nullable=True),
        sa.Column("canary_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True,
                  onupdate=sa.func.now()),
        sa.UniqueConstraint("department_id", "need_id", name="uq_dept_need"),
        sa.CheckConstraint(
            "access_mode IN ('cli_mcp', 'remote_mcp', 'python_lib')",
            name="access_mode",
        ),
    )
    op.create_index("ix_rcs_department_id", "runner_callable_specs", ["department_id"])
    op.create_index("ix_rcs_connector_id", "runner_callable_specs", ["connector_id"])
```

- [ ] **Step 2: Add ORM model `RunnerCallableSpec`** in `connectors.py`.
- [ ] **Step 3: Register in `register_all.py`** (already does `import openlia_server.db.models.connectors` — confirm).
- [ ] **Step 4: Apply + test.**
- [ ] **Step 5: Commit.**

```bash
git commit -m "feat(db): create runner_callable_specs table; unique on (department_id, need_id)"
```

### Task 2.4 — Migration: drop encryption from `llm_providers`

**Files:**
- New migration: `2026-04-28-0400_drop_llm_provider_encryption.py`
- ORM: `packages/server/src/openlia_server/db/models/config.py`

- [ ] **Step 1: Author migration.**

```python
def upgrade() -> None:
    with op.batch_alter_table("llm_providers") as batch:
        batch.drop_column("api_key_encrypted")
        batch.add_column(sa.Column("api_key", sa.Text(), nullable=True))
```

- [ ] **Step 2: Mirror change on any sibling table** that has `api_key_encrypted`. Check with `grep -rn "api_key_encrypted" packages/server/src/openlia_server/db/models/`.
- [ ] **Step 3: Update ORM** in `config.py:33` and `config.py:147` (and any siblings).
- [ ] **Step 4: Commit.**

```bash
git commit -m "feat(db): drop api_key_encrypted on llm_providers (and siblings); plaintext api_key"
```

### Task 2.5 — Delete `db/crypto.py` and rotate-secret CLI command

**Files:**
- `packages/server/src/openlia_server/db/crypto.py` (delete)
- `packages/server/src/openlia_server/cli.py` (drop the rotate-secret subcommand and the `crypto_module` import)
- Tests: `packages/server/tests/db/test_crypto*.py` (delete)

- [ ] **Step 1: Delete `crypto.py`.**
- [ ] **Step 2: Drop CLI rotate-secret command** at `cli.py:880-910` (per pre-grilling audit). Verify the subcommand is no longer registered with the parent CLI parser.
- [ ] **Step 3: Delete crypto tests.**
- [ ] **Step 4: Run server tests** to confirm no leftover imports.

```bash
uv run pytest packages/server/tests/ -q
```

- [ ] **Step 5: Commit.**

```bash
git commit -m "feat(server): delete db/crypto.py and rotate-secret CLI; plaintext secrets are sufficient under admin-hosted threat model"
```

---

## Phase 3 — Component 2: Core connector types

### Task 3.1 — Author `connectors/types.py`

**Files:**
- `packages/core/src/openlia/connectors/types.py` (modify existing)

Spec references: §3.1, §6.1, §6.4, §6.5.

- [ ] **Step 1: Update enums.**

```python
from enum import StrEnum

class Category(StrEnum):
    FINANCIAL = "financial"
    NEWS = "news"
    SOCIAL = "social"
    WEB_SEARCH = "web_search"

class ConnectorSource(StrEnum):
    BUILT_IN = "built_in"
    REMOTE_MCP = "remote_mcp"
    CLI_MCP = "cli_mcp"
    PYTHON_LIB = "python_lib"
    SKILL = "skill"   # reserved for Layer 2

class ConnectorStatus(StrEnum):
    PENDING = "pending"
    VALIDATED = "validated"
    FAILED = "failed"
```

- [ ] **Step 2: Add `LaunchSpec` and per-mode dataclasses.**

```python
@dataclass(frozen=True)
class CliMcpMode:
    kind: Literal["cli_mcp"]
    argv: list[str]
    env_keys: list[str]

@dataclass(frozen=True)
class RemoteMcpMode:
    kind: Literal["remote_mcp"]
    url: str
    headers: dict[str, str]

@dataclass(frozen=True)
class InstanceFactory:
    cls: str
    args: dict[str, Any]   # values may be `$ENV_VAR_NAME` placeholders

@dataclass(frozen=True)
class PythonLibMode:
    kind: Literal["python_lib"]
    pip_name: str
    pip_version: str
    import_module: str
    instance_factory: InstanceFactory

LaunchMode = CliMcpMode | RemoteMcpMode | PythonLibMode

@dataclass(frozen=True)
class LaunchSpec:
    modes: list[LaunchMode]
```

- [ ] **Step 3: Keep existing `ToolDefinition` (MCP-shaped). Add `CallableDefinition` (python_lib).**

```python
@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict

@dataclass(frozen=True)
class CallableDefinition:
    qualname: str    # e.g. "APIClient.real_time_quote"
    signature: str   # "(symbol: str) -> dict"
    doc: str
```

- [ ] **Step 4: Add `RunnerNeed`, `CallableSpec`, `ParamBinding`.**

```python
@dataclass(frozen=True)
class NeedParameter:
    name: str
    description: str
    type: str
    required: bool
    default: Any = None

@dataclass(frozen=True)
class RunnerNeed:
    id: str
    description: str
    parameters: list[NeedParameter]
    shape: str   # type hint string, e.g. "float", "list[dict]"

@dataclass(frozen=True)
class ParamBinding:
    to_arg: str
    transform: str | None = None   # "upper", "iso_to_eodhd", or None

@dataclass(frozen=True)
class CallableSpec:
    need_id: str
    access_mode: Literal["cli_mcp", "remote_mcp", "python_lib"]
    # MCP fields:
    tool_name: str | None = None
    # python_lib fields:
    module: str | None = None
    instance_factory: InstanceFactory | None = None
    method: str | None = None
    # shared fields:
    param_bindings: dict[str, ParamBinding] = field(default_factory=dict)
    constants: dict[str, Any] = field(default_factory=dict)
    shape: str = "any"
```

- [ ] **Step 5: Add the named transform registry.**

```python
TRANSFORMS: dict[str, Callable[[Any], Any]] = {
    "upper": str.upper,
    "lower": str.lower,
    "iso_to_eodhd": lambda code: f"{code}.NYSE",   # placeholder; finalize during adapter authoring
}

ALLOWED_TRANSFORMS: frozenset[str] = frozenset(TRANSFORMS.keys())
```

- [ ] **Step 6: Tests** in `packages/core/tests/connectors/test_types.py`: round-trip enum coverage, dataclass freeze assertions, transform-registry presence.
- [ ] **Step 7: Commit.**

```bash
git commit -m "feat(connectors): add v2 types (RunnerNeed, CallableSpec, ParamBinding, LaunchSpec, transforms)"
```

---

## Phase 4 — Component 3: Dispatcher

### Task 4.1 — Reshape `Dispatcher` API

**Files:**
- `packages/core/src/openlia/connectors/dispatch.py` (modify in place)

Per spec §8.1 + §9: drop `tools_for_department`, `allowlist`, `connector_categories`. Add `candidate_tools()`, `fetch_need(...)`, `in_department(...)`, `callable_specs_for(dept_id)`.

- [ ] **Step 1: Replace `Dispatcher` dataclass.**

```python
from contextvars import ContextVar
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from dataclasses import dataclass, field

from openlia.connectors.types import (
    Category, CallableSpec, ConnectorStatus, ToolDefinition,
)

PREFIX_SEP = "__"
_current_dept: ContextVar[str | None] = ContextVar("_current_dept", default=None)

class DispatchError(RuntimeError):
    pass

class NeedNotResolved(DispatchError):
    pass

@dataclass(frozen=True)
class PreparedConnector:
    connector_id: str
    provider_id: str
    category: Category
    status: ConnectorStatus
    transport: CallableTransport
    tools: dict[str, ToolDefinition]   # MCP-shaped; empty for python_lib-only
    callables: dict[str, "CallableDefinition"]   # python_lib introspection; empty for MCP-only

@dataclass
class Dispatcher:
    connectors: dict[str, PreparedConnector]
    callable_specs: dict[tuple[str, str], CallableSpec] = field(default_factory=dict)
    """Keyed by (department_id, need_id)."""

    def candidate_tools(self) -> list[dict[str, Any]]:
        """Full validated tool inventory across all connectors. Per spec §8.1."""
        out: list[dict[str, Any]] = []
        for conn in self.connectors.values():
            if conn.status != ConnectorStatus.VALIDATED:
                continue
            for tool_name, td in conn.tools.items():
                out.append({
                    "name": f"{conn.provider_id}{PREFIX_SEP}{tool_name}",
                    "description": td.description,
                    "input_schema": td.input_schema,
                })
        return out

    async def dispatch_tool_use(self, prefixed_name: str, arguments: dict[str, Any]) -> Any:
        if PREFIX_SEP not in prefixed_name:
            raise DispatchError(f"missing prefix in {prefixed_name!r}")
        provider_id, _, raw_name = prefixed_name.partition(PREFIX_SEP)
        for conn in self.connectors.values():
            if conn.provider_id == provider_id and raw_name in conn.tools:
                return await conn.transport.call_tool(raw_name, arguments)
        raise DispatchError(f"no connector for {prefixed_name!r}")

    @asynccontextmanager
    async def in_department(self, department_id: str) -> AsyncIterator[None]:
        token = _current_dept.set(department_id)
        try:
            yield
        finally:
            _current_dept.reset(token)

    async def fetch_need(self, need_id: str, **runtime_args: Any) -> Any:
        dept = _current_dept.get()
        if dept is None:
            raise DispatchError("fetch_need requires an active dispatcher.in_department(...) context")
        spec = self.callable_specs.get((dept, need_id))
        if spec is None:
            raise NeedNotResolved(f"no resolved callable spec for ({dept!r}, {need_id!r})")
        conn = self._connector_for_spec(spec)
        return await self._invoke_spec(conn, spec, runtime_args)

    def callable_specs_for(self, department_id: str) -> list[CallableSpec]:
        return [spec for (d, _), spec in self.callable_specs.items() if d == department_id]

    # private helpers (binding, instance factory resolution) —
    # see §6.4 for the shape walked by _invoke_spec.
```

- [ ] **Step 2: Implement `_invoke_spec`** that walks the spec, applies `param_bindings` (renaming + named transforms), merges `constants`, instantiates the factory (resolving `$ENV_VAR_NAME` placeholders from `Connector.secrets`), and calls the underlying tool/method.
- [ ] **Step 3: Tests** in `packages/core/tests/connectors/test_dispatcher.py`:
  - Candidate pool excludes non-validated connectors.
  - `dispatch_tool_use` routes correctly across multiple connectors.
  - `fetch_need` raises without active department context.
  - `fetch_need` raises `NeedNotResolved` when spec is missing.
  - `fetch_need` happy path for both MCP and python_lib spec shapes.
  - Param binding applies named transforms.
- [ ] **Step 4: Commit.**

```bash
git commit -m "feat(connectors): reshape Dispatcher — candidate_tools, fetch_need, in_department; drop allowlist + category gating"
```

### Task 4.2 — Migrate Dispatcher consumers

**Files (read-and-edit pass):**
- `packages/core/src/openlia/llm/runtime/runtime_dispatch.py` — `tools_for_run` calls `dispatcher.candidate_tools()` instead of `dispatcher.tools_for_department(...)`. Drop `_ALL_CATEGORIES`/`_NON_SEARCH` filtering.
- `packages/core/src/openlia/llm/runtime/chat.py`
- `packages/core/src/openlia/llm/runtime/report.py`
- `packages/core/src/openlia/llm/runtime/web_search.py`
- `packages/server/src/openlia_server/services/runtime.py`
- `packages/server/src/openlia_server/services/dispatcher_factory.py` — rewrite to read `RunnerCallableSpec` rows; no longer reads `tool_allowlists`. Hydrates `Dispatcher.callable_specs` dict. Loads `Connector.secrets` and passes plaintext to transports.
- All test files referencing `tools_for_department`, `allowlist`, `_DataProvider`.

- [ ] **Step 1: Sweep imports** with `grep -rn "tools_for_department\|allowlist\|_NON_SEARCH" packages/`.
- [ ] **Step 2: Edit each consumer** to call the new API.
- [ ] **Step 3: Update `dispatcher_factory.py`.**

```python
def build_dispatcher(session: Session) -> Dispatcher:
    connector_rows = session.execute(select(Connector)).scalars().all()
    spec_rows = session.execute(select(RunnerCallableSpec)).scalars().all()

    prepared = {row.id: _prepare_connector(row) for row in connector_rows}
    specs = {(s.department_id, s.need_id): _hydrate_spec(s) for s in spec_rows}
    return Dispatcher(connectors=prepared, callable_specs=specs)
```

- [ ] **Step 4: Run full test suite.**

```bash
uv run pytest -q
```

Fix only call-site breakage, not behavior changes.

- [ ] **Step 5: Commit.**

```bash
git commit -m "refactor: migrate Dispatcher consumers to candidate_tools / fetch_need API"
```

---

## Phase 5 — Component 4: Transports

### Task 5.1 — Define unified `CallableTransport` Protocol

**Files:**
- `packages/core/src/openlia/connectors/transports/__init__.py`
- `packages/core/src/openlia/connectors/transports/base.py`

- [ ] **Step 1: Author the Protocol.**

```python
from typing import Any, Protocol, runtime_checkable

@runtime_checkable
class CallableTransport(Protocol):
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...
    async def list_tools(self) -> list[dict]: ...
    async def aclose(self) -> None: ...
```

- [ ] **Step 2: Re-export from package `__init__.py`.**
- [ ] **Step 3: Commit.**

```bash
git commit -m "feat(connectors/transports): unified CallableTransport Protocol"
```

### Task 5.2 — Author `python_lib` transport

**Files:**
- `packages/core/src/openlia/connectors/transports/python_lib.py`
- `packages/core/tests/connectors/transports/test_python_lib.py`
- `packages/core/tests/connectors/transports/_fixture_lib/__init__.py` (test fixture module)

Per spec §4.2 (python_lib mode) and §6.4 (callable_spec shape). No sandboxing per locked-down §13.2.

- [ ] **Step 1: Author transport.**

```python
import importlib
import inspect
from typing import Any

from openlia.connectors.types import CallableDefinition, InstanceFactory

class PythonLibTransport:
    def __init__(self, *, module: str, instance_factory: InstanceFactory, secrets: dict[str, str]):
        self._module_name = module
        self._instance_factory = instance_factory
        self._secrets = secrets
        self._instance: Any | None = None

    def _resolve_instance(self) -> Any:
        if self._instance is not None:
            return self._instance
        mod = importlib.import_module(self._module_name)
        cls = getattr(mod, self._instance_factory.cls)
        resolved_args = {
            k: (self._secrets[v[1:]] if isinstance(v, str) and v.startswith("$") else v)
            for k, v in self._instance_factory.args.items()
        }
        self._instance = cls(**resolved_args)
        return self._instance

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        inst = self._resolve_instance()
        method = getattr(inst, name)
        result = method(**arguments)
        if inspect.isawaitable(result):
            result = await result
        return result

    async def list_tools(self) -> list[dict]:
        # python_lib uses CallableDefinition introspection in Component 5;
        # transport.list_tools is a passthrough that returns the introspected list.
        ...

    async def aclose(self) -> None:
        self._instance = None
```

- [ ] **Step 2: Tests** with fixture lib defining a sync method and an async method.
- [ ] **Step 3: Commit.**

```bash
git commit -m "feat(connectors/transports): python_lib transport with $-placeholder secrets resolution"
```

### Task 5.3 — Verify existing MCP transports

**Files:**
- `packages/core/src/openlia/connectors/transports/mcp_remote.py`
- `packages/core/src/openlia/connectors/transports/mcp_cli.py`

- [ ] **Step 1: Confirm both implement the new `CallableTransport` Protocol** (`isinstance(t, CallableTransport)` returns True).
- [ ] **Step 2: Update `mcp_cli` to inject `secrets` as env vars** when spawning subprocess. Use `env_keys` field from launch spec to pick which secrets get exported.
- [ ] **Step 3: Tests** confirm injection of secrets dict (mock subprocess).
- [ ] **Step 4: Commit (only if changes made).**

```bash
git commit -m "feat(connectors/transports): mcp_cli injects Connector.secrets per env_keys"
```

---

## Phase 6 — Component 5: Wizard-time adapter LLM

### Task 6.1 — Python-lib introspection

**Files:**
- `packages/core/src/openlia/connectors/adapter/__init__.py`
- `packages/core/src/openlia/connectors/adapter/introspect.py`
- `packages/core/tests/connectors/adapter/test_introspect.py`

- [ ] **Step 1: Author `introspect_python_lib(module_name)`.**

```python
import importlib
import inspect
from openlia.connectors.types import CallableDefinition

def introspect_python_lib(module_name: str) -> list[CallableDefinition]:
    mod = importlib.import_module(module_name)
    out: list[CallableDefinition] = []
    for cls_name, cls in inspect.getmembers(mod, inspect.isclass):
        for fn_name, fn in inspect.getmembers(cls, inspect.isfunction):
            if fn_name.startswith("_"):
                continue
            try:
                sig = str(inspect.signature(fn))
            except (TypeError, ValueError):
                continue
            doc = inspect.getdoc(fn) or ""
            out.append(CallableDefinition(
                qualname=f"{cls_name}.{fn_name}",
                signature=sig,
                doc=doc,
            ))
    return out
```

- [ ] **Step 2: Tests** against a fixture module.
- [ ] **Step 3: Commit.**

```bash
git commit -m "feat(connectors/adapter): introspect_python_lib walks public class methods"
```

### Task 6.2 — Adapter LLM resolver

**Files:**
- `packages/core/src/openlia/connectors/adapter/callable_spec_resolver.py`
- `packages/core/tests/connectors/adapter/test_callable_spec_resolver.py`

Spec §7.

- [ ] **Step 1: Author the resolver.** Quick-tier model. Strict JSON output with schema validation. Constrain `transform` choice to `ALLOWED_TRANSFORMS`.

```python
async def resolve_callable_spec(
    *,
    need: RunnerNeed,
    connector_inventory: list[CallableDefinition] | list[ToolDefinition],
    access_mode: Literal["cli_mcp", "remote_mcp", "python_lib"],
    instance_factory: InstanceFactory | None,
    llm_client: LlmClient,
) -> CallableSpec:
    """Single LLM call. Strict JSON response. Validate proposed bindings exist."""
    ...
```

- [ ] **Step 2: Validation gate** — verify chosen function/tool exists; declared parameters bind to actual signature; constants are valid; transforms are allow-listed.
- [ ] **Step 3: Tests** with a mocked `llm_client` returning canned JSON.
- [ ] **Step 4: Commit.**

```bash
git commit -m "feat(connectors/adapter): callable_spec_resolver — quick-tier LLM with strict JSON output and bind validation"
```

### Task 6.3 — Canary execution

**Files:**
- `packages/core/src/openlia/connectors/adapter/canary.py`
- `packages/core/tests/connectors/adapter/test_canary.py`

Spec §7.3 steps 3-4.

- [ ] **Step 1: Author `run_canary(spec, transport, sample_args) -> CanaryResult`.**
- [ ] **Step 2: Shape check** — verify response matches `spec.shape` (`float`, `list[object]`, etc.).
- [ ] **Step 3: Tests.**
- [ ] **Step 4: Commit.**

```bash
git commit -m "feat(connectors/adapter): canary execution + shape check"
```

### Task 6.4 — Server wiring: resolve specs after validation

**Files:**
- `packages/server/src/openlia_server/services/connectors_service.py`
- `packages/server/src/openlia_server/routes/connectors.py` (POST `/api/connectors/{id}/resolve-specs` endpoint)

- [ ] **Step 1: After connector validation succeeds**, iterate runner-bearing depts (`requires_runner=True`) where `connector.category` overlaps `dept.required_categories ∪ dept.optional_categories`. For each `(dept, need)`, call resolver + canary, prepare a draft spec.
- [ ] **Step 2: Drafts surface in the wizard** (Phase 11 builds the UI). Server endpoint returns `[{dept, need, proposed_spec, canary_value}]`.
- [ ] **Step 3: Approval endpoint persists** the spec in `runner_callable_specs` (replacing any existing row for the `(dept, need)` pair).
- [ ] **Step 4: Tests.**
- [ ] **Step 5: Commit.**

```bash
git commit -m "feat(server): wire wizard-time adapter into connector validation flow + resolve-specs endpoint"
```

---

## Phase 7 — Component 6: Built-in template registry

### Task 7.1 — Registry shape + empty catalog

**Files:**
- `packages/core/src/openlia/connectors/builtins/__init__.py`
- `packages/core/src/openlia/connectors/builtins/_registry.py`
- `packages/core/src/openlia/connectors/builtins/types.py`
- `packages/core/tests/connectors/builtins/test_registry.py`
- Delete: any stub built-in template files (e.g. `eodhd.py`, `fmp.py`, `newsapi_ai.py`)

Per spec §3.4 + §13.5 (empty day-1).

- [ ] **Step 1: Author types.**

```python
@dataclass(frozen=True)
class ModeRecipe:
    kind: Literal["cli_mcp", "remote_mcp", "python_lib"]
    # one-of, polymorphic — discriminate by `kind`
    ...

@dataclass(frozen=True)
class BuiltInTemplate:
    template_id: str
    display_name: str
    category: Category
    api_key_env_var: str
    available_modes: tuple[ModeRecipe, ...]
    canary_tool: str | None
```

- [ ] **Step 2: Empty registry.**

```python
BUILTIN_TEMPLATES: tuple[BuiltInTemplate, ...] = ()

def get_template(template_id: str) -> BuiltInTemplate | None:
    return next((t for t in BUILTIN_TEMPLATES if t.template_id == template_id), None)
```

- [ ] **Step 3: Test the registry shape, not specific templates.**
- [ ] **Step 4: Commit.**

```bash
git commit -m "feat(connectors/builtins): empty registry with BuiltInTemplate shape; stubs deleted"
```

---

## Phase 8 — Component 7: Department artifacts

### Task 8.1 — Department dataclass extensions

**Files (one per dept):**
- `packages/core/src/openlia/departments/secretary.py`
- `packages/core/src/openlia/departments/equity_research.py`
- `packages/core/src/openlia/departments/earnings_update.py`
- `packages/core/src/openlia/departments/morning_briefing.py`
- `packages/core/src/openlia/departments/macro_research.py`
- `packages/core/src/openlia/departments/retail_sentiment.py`
- `packages/core/src/openlia/departments/panic_thermometer.py`

Per spec §5.2 + §10.1.

- [ ] **Step 1: For each dept**, add four ClassVars:

```python
class EquityResearchDepartment(Department):
    required_categories: ClassVar[tuple[Category, ...]] = (Category.FINANCIAL,)
    optional_categories: ClassVar[tuple[Category, ...]] = (
        Category.NEWS, Category.SOCIAL, Category.WEB_SEARCH,
    )
    requires_runner: ClassVar[bool] = False
    disable_runtime_routing: ClassVar[bool] = False
```

Use the §10.1 table for exact values per dept.

- [ ] **Step 2: Drop legacy `data_requirement_types`/`optional_requirement_types` tuples** from each dept class.
- [ ] **Step 3: Commit (one commit per dept, or one bundled commit).**

```bash
git commit -m "feat(departments): add required_categories, optional_categories, requires_runner per spec §10.1"
```

### Task 8.2 — Routing context markdown per dept

**Files (7 new):**
- `packages/core/src/openlia/departments/<dept>.routing_context.md` for all 7 depts

Per spec §5.3. 300-800 tokens each. Four H2 sections: "What this department does", "Data this department needs access to", "Out-of-scope topics", "Example prompts and the data they imply".

- [ ] **Step 1: Author one file per dept.** Use existing dept code/specs to populate "Data" and "Out-of-scope" sections. Author 3-6 example prompts per dept (highest-leverage section per spec §5.3).
- [ ] **Step 2: Commit per dept** (or bundled).

```bash
git commit -m "feat(departments): routing_context.md for all 7 departments"
```

### Task 8.3 — `needs.yaml` for Macro Research

**Files:**
- `packages/core/src/openlia/departments/macro_research.needs.yaml`

Per spec §5.4 example. Author needs from existing MR runner code (`T1_NEEDS` lists across MR dashboards).

- [ ] **Step 1: Walk MR dashboard code** to find every need referenced.
- [ ] **Step 2: Author `needs.yaml`** with `id`, `description`, `parameters`, `shape` per need.
- [ ] **Step 3: Commit.**

```bash
git commit -m "feat(departments/mr): needs.yaml — debt_gdp, stock_quote, interest_revenue, ..."
```

### Task 8.4 — `needs.yaml` for Retail Sentiment

**Files:**
- `packages/core/src/openlia/departments/retail_sentiment.needs.yaml`

- [ ] **Step 1: Author needs** based on RS data-fetch code. Spec §9.5: `social_posts` is the primary need.
- [ ] **Step 2: Commit.**

```bash
git commit -m "feat(departments/rs): needs.yaml — social_posts"
```

### Task 8.5 — Loader and drift safety

**Files:**
- `packages/core/src/openlia/departments/loader.py`
- `packages/core/tests/departments/test_department_artifacts.py`

Per spec §5.5.

- [ ] **Step 1: Author loader.**

```python
def load_routing_context(department_id: str) -> str: ...
def load_needs(department_id: str) -> list[RunnerNeed]: ...
def all_departments() -> list[Department]: ...
```

- [ ] **Step 2: Drift-safety test** asserts:
  1. Every dept has a routing_context.md ≥ N tokens with all 4 H2 sections.
  2. Every dept with `requires_runner=True` has a non-empty `needs.yaml`.
  3. Every `id` referenced from runner code (e.g. `T1_NEEDS`) exists in the dept's `needs.yaml`.
  4. Every `id` declared in `needs.yaml` is referenced from at least one runner.

- [ ] **Step 3: Delete legacy `*.requirements.yaml`** files (one per dept that had them).
- [ ] **Step 4: Commit.**

```bash
git commit -m "feat(departments): loader + drift-safety tests; delete legacy requirements.yaml"
```

---

## Phase 9 — Component 8: Runtime

### Task 9.1 — Chat runner integration

**Files:**
- `packages/core/src/openlia/llm/runtime/chat.py`
- `packages/core/src/openlia/llm/runtime/router.py` (NEW — runtime router LLM)
- `packages/core/src/openlia/llm/runtime/escalation.py` (NEW — escalation tool)
- `packages/core/tests/llm/runtime/test_chat.py`

Spec §8.

- [ ] **Step 1: Author `router.py`.**

```python
async def route_tools(
    *,
    department_id: str,
    routing_context: str,
    user_prompt: str,
    candidate_tools: list[dict],
    llm_client: LlmClient,
) -> list[str]:
    """Spec §8.4 prompt template. Returns list of chosen tool names."""
    ...
```

- [ ] **Step 2: Author `escalation.py`** — defines the `request_additional_tools` tool and the merge logic (§8.5).
- [ ] **Step 3: Update `chat.py`** to call router on conversation start; build main-LLM tool list = `routed + escalation`. Handle escalation tool_use turns by re-invoking router. Honor `dept.disable_runtime_routing` (§8.7).
- [ ] **Step 4: Cache breakpoint** placed before routed tools in the prompt (§8.6).
- [ ] **Step 5: Tests** — happy path, escalation flow, `disable_runtime_routing=True` skips router and omits escalation.
- [ ] **Step 6: Commit.**

```bash
git commit -m "feat(runtime/chat): runtime router + escalation tool + cache-aware prompt assembly"
```

### Task 9.2 — Deterministic runner integration

**Files:**
- `packages/core/src/openlia/llm/runtime/deterministic.py` (rename / split from `report.py`)
- `packages/core/tests/llm/runtime/test_deterministic.py`

Spec §9.

- [ ] **Step 1: Migrate MR T1 stage** to `dispatcher.in_department("macro_research")` + `fetch_need(...)` per spec §9.4.
- [ ] **Step 2: Migrate RS data fetch** per spec §9.5.
- [ ] **Step 3: Tests** — both happy path and `NeedNotResolved` failure semantics.
- [ ] **Step 4: Commit.**

```bash
git commit -m "feat(runtime/deterministic): MR T1 + RS data fetch via fetch_need"
```

### Task 9.3 — Server runtime selection

**Files:**
- `packages/server/src/openlia_server/services/runtime.py`

- [ ] **Step 1: Single entry `run(dept_id, mode, request)`** that selects chat vs deterministic by inspecting the dept's runner type (`requires_runner` + caller mode). PT/MB scheduled paths use chat with a system prompt.
- [ ] **Step 2: Commit.**

```bash
git commit -m "feat(server/runtime): single dispatch entry; chat vs deterministic selection"
```

---

## Phase 10 — Component 9: Department health

### Task 10.1 — Health derivation

**Files:**
- `packages/core/src/openlia/departments/health.py`
- `packages/core/tests/departments/test_health.py`

Spec §10.

- [ ] **Step 1: Author `check_dept_health(dept, session) -> DepartmentHealth`.**

```python
@dataclass(frozen=True)
class DepartmentHealth:
    department_id: str
    status: Literal["active", "disabled"]
    reason: str | None
    missing_categories: list[Category]
    unresolved_needs: list[str]
```

Rules: each `required_categories` must have ≥1 `validated` connector; if `requires_runner=True`, every need in `needs.yaml` must have a `RunnerCallableSpec` row; else active.

- [ ] **Step 2: Tests** — disabled-on-missing-category, disabled-on-unresolved-need, active-when-all-satisfied.
- [ ] **Step 3: Commit.**

```bash
git commit -m "feat(departments/health): pure derivation function with structured reason"
```

### Task 10.2 — Server-side health cache + invalidation

**Files:**
- `packages/server/src/openlia_server/services/dept_health.py`
- `packages/server/src/openlia_server/app.py` (startup hook)
- `packages/server/src/openlia_server/services/connectors_service.py` (invalidation on every connector mutation)

- [ ] **Step 1: Compute `app.state.dept_health: dict[str, DepartmentHealth]` at startup.**
- [ ] **Step 2: Recompute on every connector create/update/delete/validate** and on every spec persistence/deletion.
- [ ] **Step 3: Tests.**
- [ ] **Step 4: Commit.**

```bash
git commit -m "feat(server/dept_health): app.state cache + mutation-driven invalidation"
```

### Task 10.3 — API: 409 gate, scheduler skip, health endpoint

**Files:**
- `packages/server/src/openlia_server/routes/dept_health.py` (GET /api/dept-health)
- Existing dept route handlers (chat, run, mutating endpoints) — add health check
- `packages/server/src/openlia_server/scheduler/jobs.py` — skip-on-disabled per spec §9.6

- [ ] **Step 1: Add 409 gate** to all mutating dept endpoints — short-circuit with `{"error": "dept_disabled", "reason": ...}`.
- [ ] **Step 2: Author GET endpoint** returning `list[DepartmentHealth]`.
- [ ] **Step 3: Scheduler precheck** logs and skips when disabled.
- [ ] **Step 4: Tests** — endpoint, 409 contract, scheduler skip.
- [ ] **Step 5: Commit.**

```bash
git commit -m "feat(server): GET /api/dept-health, 409 on mutating endpoints, scheduler skip-on-disabled"
```

---

## Phase 11 — Component 10: Frontend

### Task 11.1 — Wizard rebuild — connectors step

**Files:**
- `frontend/src/setup/steps/ConnectorsStep.tsx` (rewrite)
- `frontend/src/setup/steps/AddConnectorForm.tsx` (new)
- `frontend/src/setup/steps/PerNeedReviewCard.tsx` (new)
- `frontend/src/setup/steps/FirstRunSummary.tsx` (new)

Spec §4.

- [ ] **Step 1: Catalog list** — empty day-1 (just shows "No built-in templates yet — add a custom connector below").
- [ ] **Step 2: Add-connector form** — source dropdown (cli_mcp/remote_mcp/python_lib), per-source field set, plaintext API-key input.
- [ ] **Step 3: Per-need review cards** — for runner-bearing depts, show `[Approve] [Re-resolve] [Try a different connector]`.
- [ ] **Step 4: First-run summary** — active vs disabled depts with reasons.
- [ ] **Step 5: Component tests (Vitest).**
- [ ] **Step 6: Commit.**

```bash
git commit -m "feat(frontend/setup): connectors step rebuild — manual add, per-need review, first-run summary"
```

### Task 11.2 — Settings panels

**Files:**
- `frontend/src/components/settings/admin/ConnectorsAdminPanel.tsx` (new)
- `frontend/src/components/settings/admin/RunnerCallableSpecsAdminPanel.tsx` (new)

- [ ] **Step 1: ConnectorsAdminPanel** — list, edit, validate, delete.
- [ ] **Step 2: RunnerCallableSpecsAdminPanel** — view/override resolved specs.
- [ ] **Step 3: Commit.**

```bash
git commit -m "feat(frontend/settings): ConnectorsAdminPanel + RunnerCallableSpecsAdminPanel"
```

### Task 11.3 — Sidebar + dept pages disabled state

**Files:**
- `frontend/src/components/sidebar/Sidebar.tsx`
- `frontend/src/pages/<Dept>.tsx` (each dept page)

- [ ] **Step 1: Sidebar** — disabled depts muted, tooltip = `health.reason`.
- [ ] **Step 2: Dept pages** — banner above content when disabled, with CTA "Settings → Connectors".
- [ ] **Step 3: Commit.**

```bash
git commit -m "feat(frontend): sidebar + dept-page disabled state"
```

### Task 11.4 — API client + Zustand store

**Files:**
- `frontend/src/api/connectors.ts` (rewrite)
- `frontend/src/api/dept-health.ts` (new)
- `frontend/src/store/dept-health.ts` (Zustand store, invalidates on connector mutation)

- [ ] **Step 1: Wrap REST endpoints.**
- [ ] **Step 2: Cache dept-health and invalidate** when connector mutations succeed.
- [ ] **Step 3: Commit.**

```bash
git commit -m "feat(frontend/api): connectors + dept-health clients with mutation-driven invalidation"
```

---

## Phase 12 — Component 11: Adjacent subsystems

### Task 12.1 — LLM provider plaintext key migration

**Files:**
- `packages/server/src/openlia_server/services/llm_providers.py`

- [ ] **Step 1: Drop `encrypt_for_row`/`decrypt_for_row` calls.**
- [ ] **Step 2: Read/write plaintext `api_key` column.**
- [ ] **Step 3: Tests.**
- [ ] **Step 4: Commit.**

```bash
git commit -m "feat(server/llm_providers): plaintext api_key — encryption removed"
```

### Task 12.2 — Caching tables retag

**Files:**
- Audit any table with `data_provider_id` FK (RS classification log, MR dashboard state, search caches).
- Migration to retag to `connector_id`.

- [ ] **Step 1: Identify** with `grep -rn "data_provider_id" packages/server/src/`.
- [ ] **Step 2: Author retag migration** if any references remain.
- [ ] **Step 3: Update ORM + queries.**
- [ ] **Step 4: Commit.**

```bash
git commit -m "feat(db): retag caching FKs from data_provider_id to connector_id"
```

### Task 12.3 — Scheduler health checks

**Files:**
- `packages/server/src/openlia_server/scheduler/jobs.py`
- Subdirectories per dept's scheduled jobs

- [ ] **Step 1: Every job's pre-flight checks `app.state.dept_health[dept_id].status`.**
- [ ] **Step 2: Disabled = log + skip.**
- [ ] **Step 3: Tests.**
- [ ] **Step 4: Commit.**

```bash
git commit -m "feat(scheduler): pre-flight dept-health check; skip-on-disabled"
```

### Task 12.4 — CLI updates

**Files:**
- `packages/server/src/openlia_server/cli.py`

- [ ] **Step 1: Drop `rotate-secret` subcommand** (already removed in Task 2.5; verify clean).
- [ ] **Step 2: Add `connectors validate <id>`** and `connectors list`.
- [ ] **Step 3: Tests.**
- [ ] **Step 4: Commit.**

```bash
git commit -m "feat(cli): connectors validate/list; rotate-secret retired"
```

### Task 12.5 — Routes audit

**Files:**
- `packages/server/src/openlia_server/routes/connectors.py` (rewrite per new schema)
- `packages/server/src/openlia_server/routes/data_providers.py` (already deleted in Phase 1)
- `packages/server/src/openlia_server/routes/settings.py:105` — fix `has_api_key=bool(row.api_key_encrypted or row.env_var_name)` to `has_api_key=bool(row.secrets)`.

- [ ] **Step 1: Rewrite connectors routes** for new schema (POST/GET/PATCH/DELETE/validate/resolve-specs).
- [ ] **Step 2: Fix settings.py.**
- [ ] **Step 3: Tests.**
- [ ] **Step 4: Commit.**

```bash
git commit -m "feat(server/routes): connectors v2 + settings.py has_api_key fix"
```

---

## Phase 13 — Component 12: Quality + docs

### Task 13.1 — Unit test sweep

**Files:**
- All `packages/core/tests/connectors/`
- All `packages/core/tests/departments/`
- All `packages/core/tests/llm/runtime/`
- All `packages/server/tests/services/`
- All `packages/server/tests/routes/`

Already authored across phases. This task is the final coverage check.

- [ ] **Step 1: Run full suite.**

```bash
uv run pytest -q
```

Target: green.

- [ ] **Step 2: Coverage report.**

```bash
uv run pytest --cov=openlia --cov=openlia_server --cov-report=term-missing
```

Target: ~80% per CLAUDE.md.

- [ ] **Step 3: Commit any test-only fixes.**

```bash
git commit -m "test: cover gaps surfaced in coverage sweep"
```

### Task 13.2 — End-to-end smoke matrix

**Files:**
- `tests/e2e/test_wizard_happy_path.py`
- `tests/e2e/test_python_lib_runner_activation.py`
- `tests/e2e/test_disabled_banner_409.py`
- `tests/e2e/test_atomic_disable_on_delete.py`
- `tests/e2e/test_escalation_flow.py`

Five scenarios per the 12-component summary:

1. Wizard happy path with 1 financial + 1 news connector → all chat depts active.
2. Add `python_lib` connector for MR → adapter resolves → MR active.
3. Disabled dept renders banner; chat returns 409.
4. Delete only EODHD connector → MR drops to disabled atomically.
5. Mid-conversation escalation flow (§8.5).

- [ ] **Step 1: Author each.**
- [ ] **Step 2: Commit.**

```bash
git commit -m "test(e2e): five-scenario smoke matrix"
```

### Task 13.3 — Browser smoke (manual)

**Files:** none — checklist below.

- [ ] **Step 1: Start dev server + frontend.**

```bash
uv run openlia serve &
cd frontend && npm run dev
```

- [ ] **Step 2: Walk the wizard end-to-end** with one connector, confirm dept summary screen shows expected active/disabled set.
- [ ] **Step 3: Open Settings → Connectors**, edit one, validate, delete.
- [ ] **Step 4: Open a chat with Equity Research**, confirm router-selected tools show up; trigger an escalation.
- [ ] **Step 5: Open Macro Research**, confirm dashboards render or banner shows the right reason.
- [ ] **Step 6: Document any issues** in a follow-up task list; do not commit code in this task.

### Task 13.4 — Update `planning/projectStructure.md`

**Files:**
- `planning/projectStructure.md`

- [ ] **Step 1: Reflect the v2 directory layout** — `connectors/` package, `departments/` artifact files, dropped data-providers references.
- [ ] **Step 2: Commit.**

```bash
git commit -m "docs: update projectStructure.md for connector v2 layout"
```

### Task 13.5 — Open the PR

**Files:** none.

- [ ] **Step 1: Push branch.**

```bash
git push origin refactor/connector-redesign-v2
```

- [ ] **Step 2: Open PR** with title "Connector redesign v2 — fresh rebuild from main" and body summarizing each phase.

---

## Done criteria

The branch is ready to merge when:

1. All 13 phases' tasks are checked off.
2. `uv run pytest` is green.
3. `uv run ruff check . && uv run ruff format --check .` is clean.
4. Browser smoke pass (Task 13.3) is complete with no open issues.
5. The five e2e scenarios (Task 13.2) all pass.
6. `docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md` and this plan are the only authoritative connector docs; the prior plan is marked superseded (Task 0.2) and any other stale connector docs are retired.

Approximate commit count when done: ~38. Each phase is self-contained: any single phase can be reverted without breaking the previous phase's commits.
