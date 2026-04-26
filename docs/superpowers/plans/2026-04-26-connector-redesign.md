# Connector Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 5,238-line HTTP-adapter / manifest / catalog data subsystem with an MCP-only connector model that scopes tools to departments using prose requirements and a quick-tier LLM adapter.

**Architecture:** New `packages/core/src/openlia/connectors/` package owns connector lifecycle, V2 validation, adapter-LLM scoping, and runtime dispatch. New DB tables `connectors` and `tool_allowlists` replace `data_providers` and `data_provider_requirement_mapping`. Departments declare needs in sibling `*.requirements.yaml` files. Three day-1 built-ins (EODHD, FMP, NewsAPI_ai) ship pre-scoped; user-supplied MCP/CLI connectors are scoped on add via the adapter LLM.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.x + Alembic, MCP Python SDK (stdio + streamable HTTP), pydantic v2, anthropic SDK (resolved through existing LLM resolver), pytest, React 18 + TypeScript, Vitest, uv for package management, ruff for lint/format.

**Spec:** `docs/superpowers/specs/2026-04-26-connector-redesign-design.md` (commits `f205763`, `db87b03`).

**Reading order for implementer:**
1. The spec above. Re-read §4 (domain model) and §5 (wizard flow) before each phase.
2. `CLAUDE.md` — boundary rules (core never imports FastAPI), `uv run ...`, ruff requirements, no emojis.
3. `planning/specs/systems/database-design.md` — model registration shim pattern (Plan 1a `register_all`).
4. Existing wizard code under `frontend/src/setup/` — patterns to keep.

**Working notes:**
- All Python tests run with `uv run pytest`. Lint with `uv run ruff check .` and format with `uv run ruff format .` after every task before commit.
- Frontend tests run with `cd frontend && npm test -- --run`. Lint with `npm run lint`.
- Each task is its own commit. Use Conventional-Commit-style prefixes: `feat`, `refactor`, `test`, `chore`, `docs`.
- The existing `DataProvider` table is wired through the live wizard. Phases A through G build the new system in parallel without breaking the existing one. Phase H is the cutover and deletion.

---

## Phase A — Schema and core types

### Task A1: Alembic migration — create `connectors` and `tool_allowlists`

**Files:**
- Create: `packages/server/src/openlia_server/db/migrations/versions/2026-04-26-1700_connectors.py`

This task adds the new tables. It does NOT drop `data_providers` yet — that happens in Phase H so the live wizard keeps working through the build.

- [ ] **Step 1: Find the current head revision**

```bash
uv run alembic -c packages/server/alembic.ini current
```

Expected: prints the latest applied revision id (likely `20260425_1500_rs_schedules` based on the migration file naming).

- [ ] **Step 2: Write the migration**

Find the previous revision id by looking at the most recent file under `packages/server/src/openlia_server/db/migrations/versions/` and reading its `revision: str = "..."` line. Use that as `down_revision`.

```python
"""Connector redesign — connectors and tool_allowlists tables.

Adds the new MCP-only connector model defined in
docs/superpowers/specs/2026-04-26-connector-redesign-design.md.

Does NOT drop data_providers in this revision; the cutover happens
later in the connector-redesign sequence.

Revision ID: 20260426_1700_connectors
Revises: <PREVIOUS_REVISION_ID>
Create Date: 2026-04-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260426_1700_connectors"
down_revision: str | Sequence[str] | None = "<PREVIOUS_REVISION_ID>"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connectors",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("launch", sa.JSON(), nullable=False),
        sa.Column("credentials_ref", sa.String(length=128), nullable=True),
        sa.Column("cached_tools", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "source IN ('built_in', 'remote_mcp', 'cli_mcp')",
            name="ck_connectors_source",
        ),
        sa.CheckConstraint(
            "category IN ('financial', 'news', 'social', 'web_search')",
            name="ck_connectors_category",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'validated', 'failed')",
            name="ck_connectors_status",
        ),
    )
    op.create_index("ix_connectors_provider_id", "connectors", ["provider_id"])
    op.create_index("ix_connectors_category", "connectors", ["category"])
    op.create_index("ix_connectors_status", "connectors", ["status"])

    op.create_table(
        "tool_allowlists",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("department_id", sa.String(length=64), nullable=False),
        sa.Column(
            "connector_id",
            sa.String(length=36),
            sa.ForeignKey("connectors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("scoped_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("scoped_by", sa.String(length=16), nullable=False),
        sa.UniqueConstraint(
            "department_id",
            "connector_id",
            "tool_name",
            name="uq_tool_allowlists_dep_conn_tool",
        ),
        sa.CheckConstraint(
            "scoped_by IN ('built_in_map', 'llm_adapter')",
            name="ck_tool_allowlists_scoped_by",
        ),
    )
    op.create_index("ix_tool_allowlists_department_id", "tool_allowlists", ["department_id"])
    op.create_index("ix_tool_allowlists_connector_id", "tool_allowlists", ["connector_id"])


def downgrade() -> None:
    op.drop_index("ix_tool_allowlists_connector_id", table_name="tool_allowlists")
    op.drop_index("ix_tool_allowlists_department_id", table_name="tool_allowlists")
    op.drop_table("tool_allowlists")
    op.drop_index("ix_connectors_status", table_name="connectors")
    op.drop_index("ix_connectors_category", table_name="connectors")
    op.drop_index("ix_connectors_provider_id", table_name="connectors")
    op.drop_table("connectors")
```

Replace `<PREVIOUS_REVISION_ID>` with the value from Step 1.

- [ ] **Step 3: Run the migration on a fresh DB and verify both tables exist**

```bash
rm -f .openlia.dev.db
uv run alembic -c packages/server/alembic.ini upgrade head
uv run python -c "import sqlite3; c=sqlite3.connect('.openlia.dev.db'); print(sorted(r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")))"
```

Expected: list contains `connectors` and `tool_allowlists`.

- [ ] **Step 4: Verify downgrade works**

```bash
uv run alembic -c packages/server/alembic.ini downgrade -1
uv run python -c "import sqlite3; c=sqlite3.connect('.openlia.dev.db'); names=sorted(r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")); assert 'connectors' not in names and 'tool_allowlists' not in names, names; print('OK')"
uv run alembic -c packages/server/alembic.ini upgrade head
```

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/db/migrations/versions/2026-04-26-1700_connectors.py
git commit -m "feat(db): add connectors and tool_allowlists tables"
```

---

### Task A2: SQLAlchemy models for `Connector` and `ToolAllowlist`

**Files:**
- Create: `packages/server/src/openlia_server/db/models/connectors.py`
- Modify: `packages/server/src/openlia_server/db/models/register_all.py`
- Test: `packages/server/tests/test_db_models_connectors.py`

- [ ] **Step 1: Write the failing model test**

```python
"""Verify Connector and ToolAllowlist ORM models load and round-trip."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from openlia_server.db.base import Base
from openlia_server.db.models import register_all  # noqa: F401  - side-effect register


@pytest.fixture()
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


def test_connector_round_trip(engine):
    from openlia_server.db.models.connectors import Connector

    cid = str(uuid.uuid4())
    with Session(engine) as s:
        s.add(
            Connector(
                id=cid,
                provider_id="eodhd",
                source="built_in",
                category="financial",
                launch={"kind": "built_in", "template_id": "eodhd"},
                credentials_ref="secret://eodhd/key",
                cached_tools=[{"name": "get_quote", "description": "...", "input_schema": {}}],
                status="validated",
                last_validated_at=datetime.now(timezone.utc),
            )
        )
        s.commit()
        out = s.query(Connector).one()
        assert out.id == cid
        assert out.provider_id == "eodhd"
        assert out.cached_tools[0]["name"] == "get_quote"


def test_tool_allowlist_unique_constraint(engine):
    from openlia_server.db.models.connectors import Connector, ToolAllowlist

    cid = str(uuid.uuid4())
    with Session(engine) as s:
        s.add(
            Connector(
                id=cid,
                provider_id="eodhd",
                source="built_in",
                category="financial",
                launch={"kind": "built_in", "template_id": "eodhd"},
                status="validated",
            )
        )
        s.add(
            ToolAllowlist(
                id=str(uuid.uuid4()),
                department_id="equity_research",
                connector_id=cid,
                tool_name="get_quote",
                scoped_by="built_in_map",
            )
        )
        s.commit()

        s.add(
            ToolAllowlist(
                id=str(uuid.uuid4()),
                department_id="equity_research",
                connector_id=cid,
                tool_name="get_quote",  # duplicate triple
                scoped_by="built_in_map",
            )
        )
        with pytest.raises(Exception):  # IntegrityError or wrapped
            s.commit()


def test_tool_allowlist_cascade_delete(engine):
    from openlia_server.db.models.connectors import Connector, ToolAllowlist

    cid = str(uuid.uuid4())
    with Session(engine) as s:
        s.add(
            Connector(
                id=cid,
                provider_id="eodhd",
                source="built_in",
                category="financial",
                launch={"kind": "built_in", "template_id": "eodhd"},
                status="validated",
            )
        )
        s.add(
            ToolAllowlist(
                id=str(uuid.uuid4()),
                department_id="equity_research",
                connector_id=cid,
                tool_name="get_quote",
                scoped_by="built_in_map",
            )
        )
        s.commit()

        s.execute(Connector.__table__.delete().where(Connector.id == cid))
        s.commit()

        assert s.query(ToolAllowlist).count() == 0
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest packages/server/tests/test_db_models_connectors.py -v
```

Expected: import error (no `connectors` module).

- [ ] **Step 3: Write the model module**

```python
"""SQLAlchemy models for the connector redesign.

See docs/superpowers/specs/2026-04-26-connector-redesign-design.md §4.
Owned by the connector-redesign plan. Registered for metadata via
db.models.register_all (side-effect import).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base


class Connector(Base):
    __tablename__ = "connectors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    launch: Mapped[dict] = mapped_column(JSON, nullable=False)
    credentials_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cached_tools: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_connectors_provider_id", "provider_id"),
        Index("ix_connectors_category", "category"),
        Index("ix_connectors_status", "status"),
        CheckConstraint(
            "source IN ('built_in', 'remote_mcp', 'cli_mcp')",
            name="ck_connectors_source",
        ),
        CheckConstraint(
            "category IN ('financial', 'news', 'social', 'web_search')",
            name="ck_connectors_category",
        ),
        CheckConstraint(
            "status IN ('pending', 'validated', 'failed')",
            name="ck_connectors_status",
        ),
    )


class ToolAllowlist(Base):
    __tablename__ = "tool_allowlists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    department_id: Mapped[str] = mapped_column(String(64), nullable=False)
    connector_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("connectors.id", ondelete="CASCADE"),
        nullable=False,
    )
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    scoped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    scoped_by: Mapped[str] = mapped_column(String(16), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "department_id",
            "connector_id",
            "tool_name",
            name="uq_tool_allowlists_dep_conn_tool",
        ),
        Index("ix_tool_allowlists_department_id", "department_id"),
        Index("ix_tool_allowlists_connector_id", "connector_id"),
        CheckConstraint(
            "scoped_by IN ('built_in_map', 'llm_adapter')",
            name="ck_tool_allowlists_scoped_by",
        ),
    )
```

- [ ] **Step 4: Register models in `register_all`**

Open `packages/server/src/openlia_server/db/models/register_all.py` and add `from openlia_server.db.models import connectors  # noqa: F401` alongside the other side-effect imports.

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest packages/server/tests/test_db_models_connectors.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Lint and format**

```bash
uv run ruff format packages/server/src/openlia_server/db/models/connectors.py packages/server/tests/test_db_models_connectors.py packages/server/src/openlia_server/db/models/register_all.py
uv run ruff check packages/server/src/openlia_server/db/models/connectors.py packages/server/tests/test_db_models_connectors.py packages/server/src/openlia_server/db/models/register_all.py
```

- [ ] **Step 7: Commit**

```bash
git add packages/server/src/openlia_server/db/models/connectors.py packages/server/src/openlia_server/db/models/register_all.py packages/server/tests/test_db_models_connectors.py
git commit -m "feat(db): Connector and ToolAllowlist ORM models"
```

---

### Task A3: Core types for connectors

**Files:**
- Create: `packages/core/src/openlia/connectors/__init__.py`
- Create: `packages/core/src/openlia/connectors/types.py`
- Test: `packages/core/tests/test_connectors/test_types.py`
- Create: `packages/core/tests/test_connectors/__init__.py`

These are pure value types — no SQLAlchemy, no FastAPI. The boundary rule (CLAUDE.md) requires `openlia.connectors` to stay pure.

- [ ] **Step 1: Write the failing test**

```python
"""Type round-trips and validation for connector value objects."""

from __future__ import annotations

import pytest

from openlia.connectors.types import (
    Category,
    ConnectorSource,
    MCPLaunchSpec,
    ScopedTool,
    ToolDefinition,
)


def test_category_values():
    assert {c.value for c in Category} == {"financial", "news", "social", "web_search"}


def test_connector_source_values():
    assert {s.value for s in ConnectorSource} == {"built_in", "remote_mcp", "cli_mcp"}


def test_mcp_launch_spec_remote_round_trip():
    spec = MCPLaunchSpec.remote(url="https://x.example/mcp", headers={"Authorization": "Bearer abc"})
    raw = spec.to_json()
    assert raw == {
        "kind": "remote_mcp",
        "url": "https://x.example/mcp",
        "headers": {"Authorization": "Bearer abc"},
    }
    assert MCPLaunchSpec.from_json(raw) == spec


def test_mcp_launch_spec_cli_round_trip():
    spec = MCPLaunchSpec.cli(argv=["uvx", "some-mcp"], env={"FOO": "BAR"})
    raw = spec.to_json()
    assert raw["kind"] == "cli_mcp"
    assert MCPLaunchSpec.from_json(raw) == spec


def test_mcp_launch_spec_built_in_round_trip():
    spec = MCPLaunchSpec.built_in(template_id="eodhd")
    raw = spec.to_json()
    assert raw == {"kind": "built_in", "template_id": "eodhd"}
    assert MCPLaunchSpec.from_json(raw) == spec


def test_mcp_launch_spec_rejects_unknown_kind():
    with pytest.raises(ValueError, match="unknown kind"):
        MCPLaunchSpec.from_json({"kind": "ftp", "url": "x"})


def test_tool_definition_keeps_input_schema():
    td = ToolDefinition(
        name="get_quote",
        description="Fetch quote",
        input_schema={"type": "object", "properties": {"ticker": {"type": "string"}}},
    )
    assert td.input_schema["properties"]["ticker"]["type"] == "string"


def test_scoped_tool_is_hashable():
    a = ScopedTool(connector_id="c", tool_name="t", department_id="d")
    b = ScopedTool(connector_id="c", tool_name="t", department_id="d")
    assert {a, b} == {a}
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest packages/core/tests/test_connectors/test_types.py -v
```

Expected: ImportError.

- [ ] **Step 3: Write the types module**

```python
"""Pure value types for connector subsystem.

See docs/superpowers/specs/2026-04-26-connector-redesign-design.md §4.

This module MUST stay free of FastAPI, SQLAlchemy, and HTTP clients.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Category(str, Enum):
    FINANCIAL = "financial"
    NEWS = "news"
    SOCIAL = "social"
    WEB_SEARCH = "web_search"


class ConnectorSource(str, Enum):
    BUILT_IN = "built_in"
    REMOTE_MCP = "remote_mcp"
    CLI_MCP = "cli_mcp"


class ConnectorStatus(str, Enum):
    PENDING = "pending"
    VALIDATED = "validated"
    FAILED = "failed"


class ScopedBy(str, Enum):
    BUILT_IN_MAP = "built_in_map"
    LLM_ADAPTER = "llm_adapter"


@dataclass(frozen=True)
class MCPLaunchSpec:
    """Tagged-union launch spec persisted as JSON on Connector.launch."""

    kind: ConnectorSource
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    argv: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    template_id: str | None = None

    @staticmethod
    def remote(url: str, headers: dict[str, str] | None = None) -> "MCPLaunchSpec":
        return MCPLaunchSpec(kind=ConnectorSource.REMOTE_MCP, url=url, headers=dict(headers or {}))

    @staticmethod
    def cli(argv: list[str] | tuple[str, ...], env: dict[str, str] | None = None) -> "MCPLaunchSpec":
        return MCPLaunchSpec(kind=ConnectorSource.CLI_MCP, argv=tuple(argv), env=dict(env or {}))

    @staticmethod
    def built_in(template_id: str) -> "MCPLaunchSpec":
        return MCPLaunchSpec(kind=ConnectorSource.BUILT_IN, template_id=template_id)

    def to_json(self) -> dict[str, Any]:
        if self.kind is ConnectorSource.REMOTE_MCP:
            return {"kind": self.kind.value, "url": self.url, "headers": dict(self.headers)}
        if self.kind is ConnectorSource.CLI_MCP:
            return {"kind": self.kind.value, "argv": list(self.argv), "env": dict(self.env)}
        if self.kind is ConnectorSource.BUILT_IN:
            return {"kind": self.kind.value, "template_id": self.template_id}
        raise ValueError(f"unknown kind {self.kind!r}")  # pragma: no cover - exhaustive

    @staticmethod
    def from_json(raw: dict[str, Any]) -> "MCPLaunchSpec":
        kind = raw.get("kind")
        if kind == ConnectorSource.REMOTE_MCP.value:
            return MCPLaunchSpec.remote(url=raw["url"], headers=raw.get("headers", {}))
        if kind == ConnectorSource.CLI_MCP.value:
            return MCPLaunchSpec.cli(argv=raw["argv"], env=raw.get("env", {}))
        if kind == ConnectorSource.BUILT_IN.value:
            return MCPLaunchSpec.built_in(template_id=raw["template_id"])
        raise ValueError(f"unknown kind {kind!r}")


@dataclass(frozen=True)
class ToolDefinition:
    """Single tool as returned by `list_tools()` from an MCP server."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ScopedTool:
    """Result row produced by built-in maps or the adapter LLM."""

    department_id: str
    connector_id: str
    tool_name: str
```

- [ ] **Step 4: Write the package `__init__`**

```python
"""Public surface for the connector subsystem."""

from __future__ import annotations

from openlia.connectors.types import (
    Category,
    ConnectorSource,
    ConnectorStatus,
    MCPLaunchSpec,
    ScopedBy,
    ScopedTool,
    ToolDefinition,
)

__all__ = [
    "Category",
    "ConnectorSource",
    "ConnectorStatus",
    "MCPLaunchSpec",
    "ScopedBy",
    "ScopedTool",
    "ToolDefinition",
]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest packages/core/tests/test_connectors/test_types.py -v
```

Expected: 7 passed.

- [ ] **Step 6: Lint, format, commit**

```bash
uv run ruff format packages/core/src/openlia/connectors packages/core/tests/test_connectors
uv run ruff check packages/core/src/openlia/connectors packages/core/tests/test_connectors
git add packages/core/src/openlia/connectors packages/core/tests/test_connectors
git commit -m "feat(connectors): pure value types"
```

---

## Phase B — MCP transport, validation, and adapter LLM

### Task B1: MCP transport wrapper

**Files:**
- Create: `packages/core/src/openlia/connectors/mcp_transport.py`
- Test: `packages/core/tests/test_connectors/test_mcp_transport.py`

The transport wraps the MCP SDK so the rest of the package can call `open()` / `list_tools()` / `call_tool()` / `close()` without caring whether the underlying transport is HTTP or stdio. Use the `mcp` Python SDK (already available in the SDK ecosystem; if not yet a dependency, add it).

- [ ] **Step 1: Add the MCP SDK dependency if missing**

```bash
uv add --package openlia-core mcp
```

If already present, skip. Confirm with `grep -n '"mcp"' packages/core/pyproject.toml`.

- [ ] **Step 2: Write the failing test using fakes**

```python
"""MCPTransport composes the MCP SDK's session for our needs.

We test against an injected session factory so unit tests do not spawn
processes or talk to the network.
"""

from __future__ import annotations

import pytest

from openlia.connectors.mcp_transport import MCPTransport
from openlia.connectors.types import MCPLaunchSpec, ToolDefinition


class _FakeSession:
    def __init__(self, tools: list[ToolDefinition], call_results: dict[str, object]):
        self.tools = tools
        self.call_results = call_results
        self.opened = False
        self.closed = False
        self.calls: list[tuple[str, dict]] = []

    async def open(self) -> None:
        self.opened = True

    async def close(self) -> None:
        self.closed = True

    async def list_tools(self) -> list[ToolDefinition]:
        return list(self.tools)

    async def call_tool(self, name: str, arguments: dict) -> object:
        self.calls.append((name, arguments))
        if name not in self.call_results:
            raise RuntimeError(f"unknown tool: {name}")
        return self.call_results[name]


@pytest.mark.asyncio
async def test_transport_opens_lists_calls_closes():
    fake = _FakeSession(
        tools=[ToolDefinition(name="get_quote", description="...", input_schema={})],
        call_results={"get_quote": {"price": 1.23}},
    )
    transport = MCPTransport(
        spec=MCPLaunchSpec.remote(url="https://x.example/mcp"),
        session_factory=lambda spec: fake,
    )
    await transport.open()
    tools = await transport.list_tools()
    out = await transport.call_tool("get_quote", {"ticker": "AAPL"})
    await transport.close()

    assert fake.opened is True
    assert fake.closed is True
    assert tools[0].name == "get_quote"
    assert out == {"price": 1.23}
    assert fake.calls == [("get_quote", {"ticker": "AAPL"})]


@pytest.mark.asyncio
async def test_transport_call_tool_raises_propagates():
    fake = _FakeSession(tools=[], call_results={})
    transport = MCPTransport(
        spec=MCPLaunchSpec.cli(argv=["uvx", "x"]),
        session_factory=lambda spec: fake,
    )
    await transport.open()
    with pytest.raises(RuntimeError, match="unknown tool"):
        await transport.call_tool("nope", {})
```

- [ ] **Step 3: Run test, observe failure**

```bash
uv run pytest packages/core/tests/test_connectors/test_mcp_transport.py -v
```

Expected: ImportError on `MCPTransport`.

- [ ] **Step 4: Implement the transport**

```python
"""Thin MCP session wrapper.

Decouples the rest of the connector package from the MCP SDK's surface so
that unit tests can inject a fake session factory.

Real session_factory implementations live in this module. Tests pass
their own factory.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from openlia.connectors.types import ConnectorSource, MCPLaunchSpec, ToolDefinition


class MCPSession(Protocol):
    async def open(self) -> None: ...
    async def close(self) -> None: ...
    async def list_tools(self) -> list[ToolDefinition]: ...
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


SessionFactory = Callable[[MCPLaunchSpec], MCPSession]


@dataclass
class MCPTransport:
    spec: MCPLaunchSpec
    session_factory: SessionFactory
    _session: MCPSession | None = None

    async def open(self) -> None:
        self._session = self.session_factory(self.spec)
        await self._session.open()

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def list_tools(self) -> list[ToolDefinition]:
        if self._session is None:
            raise RuntimeError("transport not opened")
        return await self._session.list_tools()

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if self._session is None:
            raise RuntimeError("transport not opened")
        return await self._session.call_tool(name, arguments)


def default_session_factory(spec: MCPLaunchSpec) -> MCPSession:
    """Real session factory using the MCP SDK.

    HTTP for REMOTE_MCP, stdio subprocess for CLI_MCP and BUILT_IN. The
    BUILT_IN case resolves through the built-in registry to a real
    `MCPLaunchSpec.cli(...)` before reaching here.
    """

    from mcp import ClientSession  # type: ignore[import-not-found]
    from mcp.client.stdio import StdioServerParameters, stdio_client  # type: ignore[import-not-found]
    from mcp.client.streamable_http import streamablehttp_client  # type: ignore[import-not-found]

    if spec.kind is ConnectorSource.REMOTE_MCP:
        return _StreamableHttpAdapter(spec, ClientSession, streamablehttp_client)
    if spec.kind is ConnectorSource.CLI_MCP:
        params = StdioServerParameters(
            command=spec.argv[0],
            args=list(spec.argv[1:]),
            env=dict(spec.env),
        )
        return _StdioAdapter(params, ClientSession, stdio_client)
    raise ValueError(f"BUILT_IN must be resolved to CLI_MCP before transport: {spec.kind!r}")


class _StreamableHttpAdapter:
    def __init__(self, spec: MCPLaunchSpec, session_cls, client_factory) -> None:
        self._spec = spec
        self._session_cls = session_cls
        self._client_factory = client_factory
        self._cm = None
        self._session = None

    async def open(self) -> None:
        self._cm = self._client_factory(self._spec.url, headers=dict(self._spec.headers))
        read, write, _ = await self._cm.__aenter__()
        self._session = self._session_cls(read, write)
        await self._session.__aenter__()
        await self._session.initialize()

    async def close(self) -> None:
        if self._session is not None:
            await self._session.__aexit__(None, None, None)
        if self._cm is not None:
            await self._cm.__aexit__(None, None, None)

    async def list_tools(self) -> list[ToolDefinition]:
        resp = await self._session.list_tools()
        return [
            ToolDefinition(name=t.name, description=t.description or "", input_schema=t.inputSchema or {})
            for t in resp.tools
        ]

    async def call_tool(self, name: str, arguments: dict) -> Any:
        resp = await self._session.call_tool(name, arguments)
        return resp


class _StdioAdapter(_StreamableHttpAdapter):
    def __init__(self, params, session_cls, client_factory) -> None:  # type: ignore[no-untyped-def]
        self._params = params
        self._session_cls = session_cls
        self._client_factory = client_factory
        self._cm = None
        self._session = None

    async def open(self) -> None:
        self._cm = self._client_factory(self._params)
        read, write = await self._cm.__aenter__()
        self._session = self._session_cls(read, write)
        await self._session.__aenter__()
        await self._session.initialize()
```

- [ ] **Step 5: Configure pytest-asyncio**

Open `packages/core/pyproject.toml` and confirm `asyncio_mode = "auto"` is set under `[tool.pytest.ini_options]`. If absent, add it. If `pytest-asyncio` is missing, run `uv add --dev --package openlia-core pytest-asyncio`.

- [ ] **Step 6: Run tests, expect green**

```bash
uv run pytest packages/core/tests/test_connectors/test_mcp_transport.py -v
```

Expected: 2 passed.

- [ ] **Step 7: Lint, format, commit**

```bash
uv run ruff format packages/core/src/openlia/connectors/mcp_transport.py packages/core/tests/test_connectors/test_mcp_transport.py
uv run ruff check packages/core/src/openlia/connectors/mcp_transport.py packages/core/tests/test_connectors/test_mcp_transport.py
git add packages/core/src/openlia/connectors/mcp_transport.py packages/core/tests/test_connectors/test_mcp_transport.py packages/core/pyproject.toml
git commit -m "feat(connectors): MCP transport wrapper with injectable session factory"
```

---

### Task B2: V2 validation logic

**Files:**
- Create: `packages/core/src/openlia/connectors/validate.py`
- Test: `packages/core/tests/test_connectors/test_validate.py`

V2: open transport, `list_tools()`, then for built-ins also invoke a canary tool. Returns either a `ValidationOk(tools=...)` or `ValidationFailure(error=...)`.

- [ ] **Step 1: Write the failing tests**

```python
"""V2 validation: list_tools always; canary call only for built-ins."""

from __future__ import annotations

import pytest

from openlia.connectors.types import ConnectorSource, MCPLaunchSpec, ToolDefinition
from openlia.connectors.validate import (
    ValidationFailure,
    ValidationOk,
    validate_connector,
)


class _FakeSession:
    def __init__(
        self,
        tools: list[ToolDefinition],
        call_results: dict[str, object] | None = None,
        list_raises: BaseException | None = None,
    ) -> None:
        self.tools = tools
        self.call_results = call_results or {}
        self.list_raises = list_raises
        self.opened = False
        self.closed = False

    async def open(self) -> None:
        self.opened = True

    async def close(self) -> None:
        self.closed = True

    async def list_tools(self) -> list[ToolDefinition]:
        if self.list_raises is not None:
            raise self.list_raises
        return list(self.tools)

    async def call_tool(self, name: str, arguments: dict) -> object:
        if name not in self.call_results:
            raise RuntimeError(f"call failed for {name}")
        return self.call_results[name]


@pytest.mark.asyncio
async def test_remote_mcp_only_calls_list_tools():
    fake = _FakeSession(tools=[ToolDefinition(name="t", description="", input_schema={})])
    result = await validate_connector(
        spec=MCPLaunchSpec.remote(url="https://x.example/mcp"),
        canary_tool=None,
        session_factory=lambda s: fake,
    )
    assert isinstance(result, ValidationOk)
    assert [t.name for t in result.tools] == ["t"]
    assert fake.closed is True


@pytest.mark.asyncio
async def test_built_in_invokes_canary():
    fake = _FakeSession(
        tools=[ToolDefinition(name="get_user_details", description="", input_schema={})],
        call_results={"get_user_details": {"ok": True}},
    )
    result = await validate_connector(
        spec=MCPLaunchSpec.cli(argv=["uvx", "eodhd-mcp"]),  # already resolved from BUILT_IN
        canary_tool="get_user_details",
        session_factory=lambda s: fake,
    )
    assert isinstance(result, ValidationOk)


@pytest.mark.asyncio
async def test_list_tools_failure_returns_validation_failure():
    fake = _FakeSession(tools=[], list_raises=RuntimeError("boom"))
    result = await validate_connector(
        spec=MCPLaunchSpec.remote(url="https://x"),
        canary_tool=None,
        session_factory=lambda s: fake,
    )
    assert isinstance(result, ValidationFailure)
    assert "boom" in result.error
    assert fake.closed is True


@pytest.mark.asyncio
async def test_canary_failure_returns_validation_failure():
    fake = _FakeSession(
        tools=[ToolDefinition(name="x", description="", input_schema={})],
        call_results={},  # canary call will raise
    )
    result = await validate_connector(
        spec=MCPLaunchSpec.cli(argv=["uvx", "x"]),
        canary_tool="ping",
        session_factory=lambda s: fake,
    )
    assert isinstance(result, ValidationFailure)
    assert "ping" in result.error
```

- [ ] **Step 2: Run, observe failure**

```bash
uv run pytest packages/core/tests/test_connectors/test_validate.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement validation**

```python
"""V2 validation: list_tools then optional canary call.

See spec §5 Stage 3.
"""

from __future__ import annotations

from dataclasses import dataclass

from openlia.connectors.mcp_transport import MCPTransport, SessionFactory
from openlia.connectors.types import MCPLaunchSpec, ToolDefinition


@dataclass(frozen=True)
class ValidationOk:
    tools: list[ToolDefinition]


@dataclass(frozen=True)
class ValidationFailure:
    error: str


ValidationResult = ValidationOk | ValidationFailure


async def validate_connector(
    spec: MCPLaunchSpec,
    canary_tool: str | None,
    session_factory: SessionFactory,
) -> ValidationResult:
    transport = MCPTransport(spec=spec, session_factory=session_factory)
    try:
        await transport.open()
    except Exception as exc:  # noqa: BLE001 - surface raw error to user
        return ValidationFailure(error=f"open failed: {exc}")
    try:
        try:
            tools = await transport.list_tools()
        except Exception as exc:  # noqa: BLE001
            return ValidationFailure(error=f"list_tools failed: {exc}")
        if canary_tool is not None:
            try:
                await transport.call_tool(canary_tool, {})
            except Exception as exc:  # noqa: BLE001
                return ValidationFailure(error=f"canary call '{canary_tool}' failed: {exc}")
        return ValidationOk(tools=tools)
    finally:
        try:
            await transport.close()
        except Exception:  # noqa: BLE001 - close errors must not mask the real result
            pass
```

- [ ] **Step 4: Run tests, expect green**

```bash
uv run pytest packages/core/tests/test_connectors/test_validate.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Lint, format, commit**

```bash
uv run ruff format packages/core/src/openlia/connectors/validate.py packages/core/tests/test_connectors/test_validate.py
uv run ruff check packages/core/src/openlia/connectors/validate.py packages/core/tests/test_connectors/test_validate.py
git add packages/core/src/openlia/connectors/validate.py packages/core/tests/test_connectors/test_validate.py
git commit -m "feat(connectors): V2 validation (list_tools + optional canary)"
```

---

### Task B3: Adapter LLM scoping

**Files:**
- Create: `packages/core/src/openlia/connectors/scope.py`
- Test: `packages/core/tests/test_connectors/test_scope.py`

The scoper takes a connector's tools and the registered department requirements, calls the user-configured **quick** tier through the existing LLM resolver, expects JSON output, validates schema, retries once on schema-invalid output, and returns `list[ScopedTool]`.

The LLM call goes through `openlia.llm.runtime.invoke` (or whichever the runtime exposes). To avoid coupling this task to runtime internals, we depend on a `ScopeLLMClient` protocol and inject it. A real adapter that talks to the resolver lives next to the runtime.

- [ ] **Step 1: Write the failing test**

```python
"""Adapter LLM scoping.

The scoper passes (tools, requirements) and consumes JSON. Schema validation
is enforced; one retry on malformed output; raises on second failure.
"""

from __future__ import annotations

import json

import pytest

from openlia.connectors.scope import (
    DepartmentRequirements,
    ScopeLLMClient,
    ScopeRequest,
    scope_connector,
)
from openlia.connectors.types import Category, ToolDefinition


_REQS = {
    "equity_research": DepartmentRequirements(
        department_id="equity_research",
        per_category={
            Category.FINANCIAL.value: {"required": True, "description": "fundamentals etc."},
        },
    ),
    "earnings_update": DepartmentRequirements(
        department_id="earnings_update",
        per_category={
            Category.FINANCIAL.value: {"required": True, "description": "fundamentals etc."},
        },
    ),
}


class _FakeLLM(ScopeLLMClient):
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[ScopeRequest] = []

    async def call(self, req: ScopeRequest) -> str:
        self.calls.append(req)
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_happy_path_assigns_tools_to_departments():
    tools = [
        ToolDefinition(name="get_fundamentals", description="financial data", input_schema={}),
        ToolDefinition(name="get_options_eod", description="options EOD", input_schema={}),
    ]
    payload = json.dumps(
        {
            "assignments": [
                {"tool_name": "get_fundamentals", "department_ids": ["equity_research", "earnings_update"]},
                {"tool_name": "get_options_eod", "department_ids": []},
            ]
        }
    )
    llm = _FakeLLM([payload])

    result = await scope_connector(
        connector_id="c1",
        provider_id="eodhd",
        category=Category.FINANCIAL,
        tools=tools,
        requirements=_REQS,
        llm=llm,
    )

    names = sorted((s.department_id, s.tool_name) for s in result)
    assert names == [
        ("earnings_update", "get_fundamentals"),
        ("equity_research", "get_fundamentals"),
    ]
    assert all(s.connector_id == "c1" for s in result)


@pytest.mark.asyncio
async def test_retries_once_on_invalid_json():
    tools = [ToolDefinition(name="t", description="", input_schema={})]
    valid = json.dumps({"assignments": [{"tool_name": "t", "department_ids": ["equity_research"]}]})
    llm = _FakeLLM(["NOT JSON", valid])

    result = await scope_connector(
        connector_id="c",
        provider_id="x",
        category=Category.FINANCIAL,
        tools=tools,
        requirements=_REQS,
        llm=llm,
    )
    assert len(result) == 1
    assert len(llm.calls) == 2  # one retry


@pytest.mark.asyncio
async def test_raises_after_second_invalid_json():
    tools = [ToolDefinition(name="t", description="", input_schema={})]
    llm = _FakeLLM(["NOT JSON", "still not"])
    with pytest.raises(ValueError, match="adapter LLM"):
        await scope_connector(
            connector_id="c",
            provider_id="x",
            category=Category.FINANCIAL,
            tools=tools,
            requirements=_REQS,
            llm=llm,
        )


@pytest.mark.asyncio
async def test_drops_assignments_to_unknown_departments():
    tools = [ToolDefinition(name="t", description="", input_schema={})]
    payload = json.dumps(
        {"assignments": [{"tool_name": "t", "department_ids": ["bogus_dept", "equity_research"]}]}
    )
    llm = _FakeLLM([payload])
    result = await scope_connector(
        connector_id="c",
        provider_id="x",
        category=Category.FINANCIAL,
        tools=tools,
        requirements=_REQS,
        llm=llm,
    )
    assert [s.department_id for s in result] == ["equity_research"]


@pytest.mark.asyncio
async def test_only_eligible_departments_passed_to_llm():
    """Only departments declaring this category are eligible."""

    reqs = {
        **_REQS,
        "macro_research": DepartmentRequirements(
            department_id="macro_research",
            per_category={
                Category.NEWS.value: {"required": True, "description": "..."},
            },
        ),
    }
    tools = [ToolDefinition(name="t", description="", input_schema={})]
    payload = json.dumps({"assignments": [{"tool_name": "t", "department_ids": []}]})
    llm = _FakeLLM([payload])
    await scope_connector(
        connector_id="c",
        provider_id="x",
        category=Category.FINANCIAL,
        tools=tools,
        requirements=reqs,
        llm=llm,
    )
    eligible = llm.calls[0].eligible_department_ids
    assert "macro_research" not in eligible
    assert "equity_research" in eligible
```

- [ ] **Step 2: Run, observe failure**

```bash
uv run pytest packages/core/tests/test_connectors/test_scope.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement scoping**

```python
"""Adapter LLM that scopes a connector's tools to departments.

The LLM client is injected so unit tests run without network. Production
binds it to the LLM resolver's quick-tier client.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from openlia.connectors.types import Category, ScopedBy, ScopedTool, ToolDefinition


@dataclass(frozen=True)
class DepartmentRequirements:
    department_id: str
    per_category: dict[str, dict[str, Any]]
    """Maps Category.value -> {'required': bool, 'description': str}."""


@dataclass(frozen=True)
class ScopeRequest:
    connector_id: str
    provider_id: str
    category: Category
    tools: list[ToolDefinition]
    eligible_department_ids: list[str]
    eligible_requirements: dict[str, str]
    """department_id -> the prose description for this category."""


class ScopeLLMClient(Protocol):
    async def call(self, req: ScopeRequest) -> str: ...


def _build_prompt(req: ScopeRequest) -> str:
    """Format the prompt fed to the quick-tier LLM."""

    tool_lines = []
    for t in req.tools:
        tool_lines.append(
            json.dumps({"name": t.name, "description": t.description, "input_schema": t.input_schema})
        )
    dept_lines = []
    for dep_id in req.eligible_department_ids:
        dept_lines.append(
            json.dumps({"department_id": dep_id, "description": req.eligible_requirements[dep_id]})
        )
    return (
        "You assign tools to departments based on prose data requirements.\n"
        f"Connector category: {req.category.value}\n"
        "Eligible departments and their requirements for this category:\n"
        + "\n".join(dept_lines)
        + "\nTools to scope:\n"
        + "\n".join(tool_lines)
        + '\nReturn ONLY JSON of shape '
        + '{"assignments": [{"tool_name": str, "department_ids": [str]}]}.\n'
        + "Include every tool exactly once. department_ids may be empty."
    )


def _parse(payload: str, valid_dep_ids: set[str], valid_tool_names: set[str]) -> list[tuple[str, list[str]]]:
    data = json.loads(payload)
    if not isinstance(data, dict) or "assignments" not in data:
        raise ValueError("missing assignments")
    out: list[tuple[str, list[str]]] = []
    for row in data["assignments"]:
        if not isinstance(row, dict):
            raise ValueError("non-dict assignment")
        name = row.get("tool_name")
        deps = row.get("department_ids", [])
        if name not in valid_tool_names:
            continue
        if not isinstance(deps, list):
            raise ValueError(f"non-list department_ids for {name}")
        out.append((name, [d for d in deps if d in valid_dep_ids]))
    return out


async def scope_connector(
    connector_id: str,
    provider_id: str,
    category: Category,
    tools: list[ToolDefinition],
    requirements: dict[str, DepartmentRequirements],
    llm: ScopeLLMClient,
) -> list[ScopedTool]:
    eligible = {
        dep_id: r.per_category[category.value]["description"]
        for dep_id, r in requirements.items()
        if category.value in r.per_category
    }
    req = ScopeRequest(
        connector_id=connector_id,
        provider_id=provider_id,
        category=category,
        tools=tools,
        eligible_department_ids=sorted(eligible.keys()),
        eligible_requirements=eligible,
    )
    valid_dep_ids = set(eligible.keys())
    valid_tool_names = {t.name for t in tools}

    last_error: Exception | None = None
    for _attempt in range(2):
        raw = await llm.call(req)
        try:
            assignments = _parse(raw, valid_dep_ids, valid_tool_names)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue
        result: list[ScopedTool] = []
        for tool_name, dep_ids in assignments:
            for dep in dep_ids:
                result.append(
                    ScopedTool(
                        department_id=dep,
                        connector_id=connector_id,
                        tool_name=tool_name,
                    )
                )
        return result
    raise ValueError(f"adapter LLM produced invalid output twice: {last_error!r}")


# Marker re-export so callers writing rows know which scoped_by to use.
LLM_ADAPTER_SCOPED_BY = ScopedBy.LLM_ADAPTER
```

- [ ] **Step 4: Run, expect green**

```bash
uv run pytest packages/core/tests/test_connectors/test_scope.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Lint, format, commit**

```bash
uv run ruff format packages/core/src/openlia/connectors/scope.py packages/core/tests/test_connectors/test_scope.py
uv run ruff check packages/core/src/openlia/connectors/scope.py packages/core/tests/test_connectors/test_scope.py
git add packages/core/src/openlia/connectors/scope.py packages/core/tests/test_connectors/test_scope.py
git commit -m "feat(connectors): adapter LLM scoping with retry and schema validation"
```

---

## Phase C — Built-in templates

### Task C1: BuiltInTemplate registry

**Files:**
- Create: `packages/core/src/openlia/connectors/builtins/__init__.py`
- Create: `packages/core/src/openlia/connectors/builtins/_types.py`
- Test: `packages/core/tests/test_connectors/test_builtins_registry.py`

- [ ] **Step 1: Write the failing test**

```python
"""Built-in registry has the day-1 catalog and exposes lookups."""

from __future__ import annotations

import pytest

from openlia.connectors.builtins import (
    BuiltInTemplate,
    get_builtin,
    list_builtins_for_category,
)
from openlia.connectors.types import Category


def test_day1_catalog_has_three_entries():
    fin = list_builtins_for_category(Category.FINANCIAL)
    news = list_builtins_for_category(Category.NEWS)
    assert sorted(t.template_id for t in fin) == ["eodhd", "fmp"]
    assert [t.template_id for t in news] == ["newsapi_ai"]
    assert list_builtins_for_category(Category.SOCIAL) == []
    assert list_builtins_for_category(Category.WEB_SEARCH) == []


def test_get_builtin_returns_template():
    t = get_builtin("eodhd")
    assert isinstance(t, BuiltInTemplate)
    assert t.category is Category.FINANCIAL
    assert t.canary_tool  # non-empty string
    assert t.api_key_env_var  # non-empty string
    assert t.shipped_allowlist  # at least one assignment
    assert "equity_research" in {a.department_id for a in t.shipped_allowlist}


def test_get_builtin_unknown():
    with pytest.raises(KeyError):
        get_builtin("does_not_exist")
```

- [ ] **Step 2: Run, observe failure**

```bash
uv run pytest packages/core/tests/test_connectors/test_builtins_registry.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement template type**

`packages/core/src/openlia/connectors/builtins/_types.py`:

```python
"""BuiltInTemplate value type."""

from __future__ import annotations

from dataclasses import dataclass

from openlia.connectors.types import Category


@dataclass(frozen=True)
class ShippedAssignment:
    department_id: str
    tool_name: str


@dataclass(frozen=True)
class BuiltInTemplate:
    template_id: str
    display_name: str
    category: Category
    api_key_env_var: str
    """Env-var name the launched MCP server reads for credentials."""
    cli_argv: tuple[str, ...]
    """e.g. ('uvx', 'eodhd-mcp-server')."""
    canary_tool: str
    shipped_allowlist: tuple[ShippedAssignment, ...]
```

- [ ] **Step 4: Implement registry**

`packages/core/src/openlia/connectors/builtins/__init__.py`:

```python
"""Day-1 built-in catalog: EODHD, FMP, NewsAPI_ai.

See spec §12 for rationale and scope.
"""

from __future__ import annotations

from openlia.connectors.builtins._types import BuiltInTemplate, ShippedAssignment
from openlia.connectors.types import Category

# Tasks C2/C3/C4 fill these in. Importing those modules registers them.
_REGISTRY: dict[str, BuiltInTemplate] = {}


def register(template: BuiltInTemplate) -> None:
    if template.template_id in _REGISTRY:
        raise ValueError(f"duplicate built-in: {template.template_id}")
    _REGISTRY[template.template_id] = template


def get_builtin(template_id: str) -> BuiltInTemplate:
    return _REGISTRY[template_id]


def list_builtins_for_category(category: Category) -> list[BuiltInTemplate]:
    return [t for t in _REGISTRY.values() if t.category is category]


def all_builtins() -> list[BuiltInTemplate]:
    return list(_REGISTRY.values())


# Side-effect imports that populate _REGISTRY.
from openlia.connectors.builtins import eodhd, fmp, newsapi_ai  # noqa: E402, F401

__all__ = [
    "BuiltInTemplate",
    "ShippedAssignment",
    "all_builtins",
    "get_builtin",
    "list_builtins_for_category",
    "register",
]
```

This will fail at import time because `eodhd.py`, `fmp.py`, `newsapi_ai.py` don't exist yet — but Step 5 creates them.

- [ ] **Step 5: Create empty template stubs**

For each of `eodhd.py`, `fmp.py`, `newsapi_ai.py` under `packages/core/src/openlia/connectors/builtins/`, create a placeholder so imports succeed. Subsequent tasks (C2-C4) replace these.

`eodhd.py`:

```python
"""EODHD built-in template — placeholder filled in Task C2."""

from __future__ import annotations

from openlia.connectors.builtins._types import BuiltInTemplate, ShippedAssignment
from openlia.connectors.builtins import register
from openlia.connectors.types import Category

register(
    BuiltInTemplate(
        template_id="eodhd",
        display_name="EODHD",
        category=Category.FINANCIAL,
        api_key_env_var="EODHD_API_KEY",
        cli_argv=("uvx", "eodhd-mcp-server"),
        canary_tool="get_user_details",
        shipped_allowlist=(
            ShippedAssignment(department_id="equity_research", tool_name="get_quote"),
        ),
    )
)
```

`fmp.py`:

```python
"""FMP built-in — placeholder filled in Task C3."""

from __future__ import annotations

from openlia.connectors.builtins._types import BuiltInTemplate, ShippedAssignment
from openlia.connectors.builtins import register
from openlia.connectors.types import Category

register(
    BuiltInTemplate(
        template_id="fmp",
        display_name="Financial Modeling Prep",
        category=Category.FINANCIAL,
        api_key_env_var="FMP_API_KEY",
        cli_argv=("uvx", "fmp-mcp-server"),
        canary_tool="search",
        shipped_allowlist=(
            ShippedAssignment(department_id="equity_research", tool_name="quote"),
        ),
    )
)
```

`newsapi_ai.py`:

```python
"""NewsAPI.ai built-in — placeholder filled in Task C4."""

from __future__ import annotations

from openlia.connectors.builtins._types import BuiltInTemplate, ShippedAssignment
from openlia.connectors.builtins import register
from openlia.connectors.types import Category

register(
    BuiltInTemplate(
        template_id="newsapi_ai",
        display_name="NewsAPI.ai",
        category=Category.NEWS,
        api_key_env_var="NEWSAPI_AI_KEY",
        cli_argv=("uvx", "newsapi-ai-mcp"),
        canary_tool="get_api_usage",
        shipped_allowlist=(
            ShippedAssignment(department_id="equity_research", tool_name="search_articles"),
        ),
    )
)
```

- [ ] **Step 6: Run tests, expect green**

```bash
uv run pytest packages/core/tests/test_connectors/test_builtins_registry.py -v
```

Expected: 3 passed.

- [ ] **Step 7: Lint, format, commit**

```bash
uv run ruff format packages/core/src/openlia/connectors/builtins packages/core/tests/test_connectors/test_builtins_registry.py
uv run ruff check packages/core/src/openlia/connectors/builtins packages/core/tests/test_connectors/test_builtins_registry.py
git add packages/core/src/openlia/connectors/builtins packages/core/tests/test_connectors/test_builtins_registry.py
git commit -m "feat(connectors): built-in template registry with stub day-1 catalog"
```

---

### Task C2: EODHD shipped allowlist

**Files:**
- Modify: `packages/core/src/openlia/connectors/builtins/eodhd.py`
- Test: `packages/core/tests/test_connectors/test_builtins_eodhd.py`

The shipped allowlist for EODHD reflects its 77-tool surface (per memory IDs 2107, 2123). Build it deliberately by mapping each tool to the departments that genuinely need it, based on tool name + the spec's department-requirement intent.

The plan does not enumerate all 77 mappings — that's authoring work. Instead the implementer:
1. Lists EODHD's tool names from its MCP server's `list_tools()` output (or vendor docs).
2. For each tool, decides which of the 7 departments need it given the prose requirements written in Phase D.
3. Encodes the result as a tuple of `ShippedAssignment` rows.

The test below asserts shape, not specific tools, so this task can be redone without churning the test.

- [ ] **Step 1: Write the failing test (shape only)**

```python
"""EODHD's shipped allowlist must cover the relevant departments."""

from __future__ import annotations

from openlia.connectors.builtins import get_builtin


def test_eodhd_allowlist_covers_finance_departments():
    t = get_builtin("eodhd")
    deps = {a.department_id for a in t.shipped_allowlist}
    # Every finance-needing department gets at least one tool.
    assert "equity_research" in deps
    assert "earnings_update" in deps
    assert "morning_briefing" in deps


def test_eodhd_allowlist_uses_real_tool_names():
    t = get_builtin("eodhd")
    # Dummy sanity checks — adjust to match the curated set you author.
    names = {a.tool_name for a in t.shipped_allowlist}
    assert "get_fundamentals_data" in names
    assert "get_historical_stock_prices" in names
```

- [ ] **Step 2: Run, observe failure**

```bash
uv run pytest packages/core/tests/test_connectors/test_builtins_eodhd.py -v
```

Expected: AssertionError on the second test (placeholder allowlist is too small).

- [ ] **Step 3: Replace `eodhd.py` with the curated allowlist**

Rewrite `packages/core/src/openlia/connectors/builtins/eodhd.py`. Keep the registration call; replace the `shipped_allowlist=` tuple with one `ShippedAssignment` per (department, tool) pair you decide is correct. Reference EODHD's tool list (e.g. `mcp__claude_ai_EODHD__*` tools, or upstream docs) and Phase D's `*.requirements.yaml` files.

Sample structure (replace with full curated list):

```python
"""EODHD built-in: curated tool allowlist for finance departments."""

from __future__ import annotations

from openlia.connectors.builtins._types import BuiltInTemplate, ShippedAssignment
from openlia.connectors.builtins import register
from openlia.connectors.types import Category

_ALLOWLIST: tuple[ShippedAssignment, ...] = (
    # equity_research — fundamentals, prices, analyst, earnings
    ShippedAssignment("equity_research", "get_fundamentals_data"),
    ShippedAssignment("equity_research", "get_historical_stock_prices"),
    ShippedAssignment("equity_research", "get_earnings_trends"),
    ShippedAssignment("equity_research", "get_upcoming_earnings"),
    ShippedAssignment("equity_research", "get_historical_dividends"),
    # earnings_update — earnings calendar + fundamentals
    ShippedAssignment("earnings_update", "get_upcoming_earnings"),
    ShippedAssignment("earnings_update", "get_fundamentals_data"),
    # morning_briefing — broad market state
    ShippedAssignment("morning_briefing", "get_live_price_data"),
    ShippedAssignment("morning_briefing", "mp_indices_list"),
    # macro_research — macro + UST
    ShippedAssignment("macro_research", "get_macro_indicator"),
    ShippedAssignment("macro_research", "get_ust_yield_rates"),
    # ... continue authoring the full curated set ...
)

register(
    BuiltInTemplate(
        template_id="eodhd",
        display_name="EODHD",
        category=Category.FINANCIAL,
        api_key_env_var="EODHD_API_KEY",
        cli_argv=("uvx", "eodhd-mcp-server"),
        canary_tool="get_user_details",
        shipped_allowlist=_ALLOWLIST,
    )
)
```

- [ ] **Step 4: Run, expect green**

```bash
uv run pytest packages/core/tests/test_connectors/test_builtins_eodhd.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Lint, format, commit**

```bash
uv run ruff format packages/core/src/openlia/connectors/builtins/eodhd.py packages/core/tests/test_connectors/test_builtins_eodhd.py
uv run ruff check packages/core/src/openlia/connectors/builtins/eodhd.py packages/core/tests/test_connectors/test_builtins_eodhd.py
git add packages/core/src/openlia/connectors/builtins/eodhd.py packages/core/tests/test_connectors/test_builtins_eodhd.py
git commit -m "feat(connectors): EODHD shipped allowlist"
```

---

### Task C3: FMP shipped allowlist

**Files:**
- Modify: `packages/core/src/openlia/connectors/builtins/fmp.py`
- Test: `packages/core/tests/test_connectors/test_builtins_fmp.py`

Same procedure as Task C2, applied to FMP's tool surface. FMP and EODHD overlap in financial fundamentals and quotes. Both end up in equity_research's allowlist for some tools (e.g. EODHD `get_quote` and FMP `quote`); collisions are handled at runtime by the `<provider_id>__` prefix.

- [ ] **Step 1: Write the failing test (shape)**

```python
"""FMP allowlist covers finance departments."""

from openlia.connectors.builtins import get_builtin


def test_fmp_allowlist_covers_equity_research():
    t = get_builtin("fmp")
    deps = {a.department_id for a in t.shipped_allowlist}
    assert "equity_research" in deps


def test_fmp_allowlist_uses_real_tool_names():
    t = get_builtin("fmp")
    names = {a.tool_name for a in t.shipped_allowlist}
    assert "quote" in names
    assert "statements" in names
```

- [ ] **Step 2-5: Same TDD loop as Task C2** (run-fails, replace `fmp.py` with curated list, re-run, lint, commit).

Commit message: `feat(connectors): FMP shipped allowlist`.

---

### Task C4: NewsAPI.ai shipped allowlist

**Files:**
- Modify: `packages/core/src/openlia/connectors/builtins/newsapi_ai.py`
- Test: `packages/core/tests/test_connectors/test_builtins_newsapi_ai.py`

NewsAPI.ai has a smaller tool set (8 tools per the MCP server instructions in the system prompt). The allowlist mostly reuses the same tools across news-needing departments.

- [ ] **Step 1: Write the failing test**

```python
from openlia.connectors.builtins import get_builtin


def test_newsapi_ai_allowlist_covers_news_consumers():
    t = get_builtin("newsapi_ai")
    deps = {a.department_id for a in t.shipped_allowlist}
    assert {"equity_research", "earnings_update", "morning_briefing"}.issubset(deps)


def test_newsapi_ai_uses_real_tool_names():
    t = get_builtin("newsapi_ai")
    names = {a.tool_name for a in t.shipped_allowlist}
    assert "search_articles" in names
    assert "search_events" in names
```

- [ ] **Step 2-5: Same loop.**

Commit: `feat(connectors): NewsAPI.ai shipped allowlist`.

---

## Phase D — Department requirements

### Task D1: Requirements loader on Department base

**Files:**
- Modify: `packages/core/src/openlia/departments/base.py`
- Modify: `packages/core/src/openlia/departments/__init__.py`
- Test: `packages/core/tests/test_departments/test_requirements_loader.py`

Each department class gets a sibling `*.requirements.yaml`. The base provides a `requirements()` classmethod that loads and caches the YAML and returns a `DepartmentRequirements` value. The `__init__` exposes `get_all_requirements()` for the scoper.

- [ ] **Step 1: Confirm `pyyaml` is available**

```bash
uv run python -c "import yaml; print(yaml.__version__)"
```

If missing: `uv add --package openlia-core pyyaml`.

- [ ] **Step 2: Write the failing test**

```python
"""Department requirements loader: parses sibling YAML and validates schema."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_loader_reads_sibling_yaml(tmp_path, monkeypatch):
    from openlia.departments.requirements_loader import load_requirements_yaml

    yaml_path = tmp_path / "x.requirements.yaml"
    yaml_path.write_text(
        "financial:\n"
        "  required: true\n"
        "  description: |\n"
        "    Need fundamentals.\n"
        "news:\n"
        "  required: false\n"
        "  description: optional news\n"
    )
    out = load_requirements_yaml(yaml_path)
    assert out["financial"]["required"] is True
    assert "fundamentals" in out["financial"]["description"]
    assert out["news"]["required"] is False


def test_loader_rejects_unknown_category(tmp_path):
    from openlia.departments.requirements_loader import load_requirements_yaml

    p = tmp_path / "x.requirements.yaml"
    p.write_text("nonsense:\n  required: true\n  description: x\n")
    with pytest.raises(ValueError, match="unknown category"):
        load_requirements_yaml(p)


def test_loader_requires_required_and_description(tmp_path):
    from openlia.departments.requirements_loader import load_requirements_yaml

    p = tmp_path / "x.requirements.yaml"
    p.write_text("financial:\n  required: true\n")
    with pytest.raises(ValueError, match="description"):
        load_requirements_yaml(p)


def test_get_all_requirements_returns_known_departments():
    """After Phase D YAMLs land, every department class has loadable requirements."""

    from openlia.departments import get_all_requirements

    out = get_all_requirements()
    expected = {
        "secretary",
        "equity_research",
        "earnings_update",
        "morning_briefing",
        "retail_sentiment",
        "macro_research",
        "panic_thermometer",
    }
    assert expected.issubset(out.keys())
    # Each entry is a DepartmentRequirements (per_category dict).
    er = out["equity_research"]
    assert "financial" in er.per_category
```

The fourth test passes only after Tasks D2-D8 land. Mark it `xfail` initially:

```python
import pytest

@pytest.mark.xfail(reason="department YAMLs land in tasks D2-D8", strict=False)
def test_get_all_requirements_returns_known_departments(): ...
```

- [ ] **Step 3: Implement loader**

`packages/core/src/openlia/departments/requirements_loader.py`:

```python
"""Sibling-YAML loader for department data requirements."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from openlia.connectors.scope import DepartmentRequirements
from openlia.connectors.types import Category

_VALID_CATEGORIES = {c.value for c in Category}


def load_requirements_yaml(path: Path) -> dict[str, dict[str, Any]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: top-level must be a mapping")
    for cat, body in raw.items():
        if cat not in _VALID_CATEGORIES:
            raise ValueError(f"{path}: unknown category '{cat}'")
        if not isinstance(body, dict) or "required" not in body or "description" not in body:
            raise ValueError(f"{path}: '{cat}' must have 'required' and 'description'")
        if not isinstance(body["required"], bool):
            raise ValueError(f"{path}: '{cat}.required' must be bool")
        if not isinstance(body["description"], str) or not body["description"].strip():
            raise ValueError(f"{path}: '{cat}.description' must be non-empty string")
    return raw


def load_department_requirements(department_id: str, yaml_path: Path) -> DepartmentRequirements:
    return DepartmentRequirements(
        department_id=department_id,
        per_category=load_requirements_yaml(yaml_path),
    )
```

- [ ] **Step 4: Wire it into the package**

Edit `packages/core/src/openlia/departments/__init__.py` to add:

```python
from pathlib import Path

from openlia.connectors.scope import DepartmentRequirements
from openlia.departments.requirements_loader import load_department_requirements

_DEPT_DIR = Path(__file__).parent

_DEPT_TO_FILE: dict[str, str] = {
    "secretary": "secretary.requirements.yaml",
    "equity_research": "equity_research.requirements.yaml",
    "earnings_update": "earnings_update.requirements.yaml",
    "morning_briefing": "morning_briefing.requirements.yaml",
    "retail_sentiment": "retail_sentiment.requirements.yaml",
    "macro_research": "macro_research.requirements.yaml",
    "panic_thermometer": "panic_thermometer.requirements.yaml",
}


def get_all_requirements() -> dict[str, DepartmentRequirements]:
    out: dict[str, DepartmentRequirements] = {}
    for dep_id, fname in _DEPT_TO_FILE.items():
        path = _DEPT_DIR / fname
        if path.exists():
            out[dep_id] = load_department_requirements(dep_id, path)
    return out
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest packages/core/tests/test_departments/test_requirements_loader.py -v
```

Expected: 3 passed, 1 xfail.

- [ ] **Step 6: Lint, format, commit**

```bash
uv run ruff format packages/core/src/openlia/departments packages/core/tests/test_departments/test_requirements_loader.py
uv run ruff check packages/core/src/openlia/departments packages/core/tests/test_departments/test_requirements_loader.py
git add packages/core/src/openlia/departments packages/core/tests/test_departments/test_requirements_loader.py
git commit -m "feat(departments): YAML requirements loader and registry hookup"
```

---

### Tasks D2-D8: One YAML per department

**Files (one per task):**
- Create: `packages/core/src/openlia/departments/<dept>.requirements.yaml`

For each of the seven departments, write a sibling YAML with one entry per relevant category. Use prose that names *concrete data types*. Keep each description to one short paragraph.

The xfail in Task D1's test becomes a passing test once all seven YAMLs exist; flip it to a normal test after the last one lands.

Per-task structure (use this as the template for all seven):

- [ ] **Step 1: Create the YAML**

For example, `equity_research.requirements.yaml`:

```yaml
financial:
  required: true
  description: |
    Company fundamentals (income statement, balance sheet, cash flow),
    historical daily prices, analyst estimates, earnings calendar,
    upcoming and historical dividends, share splits.
news:
  required: true
  description: |
    Company-tagged news with publication date and source. Recent press
    releases, regulatory filings, and analyst commentary.
social:
  required: false
  description: |
    Reddit and X mentions for ticker sentiment when available.
```

- [ ] **Step 2: Confirm it parses**

```bash
uv run python -c "from openlia.departments import get_all_requirements; print(list(get_all_requirements().keys()))"
```

The new department's id should appear.

- [ ] **Step 3: Commit**

```bash
git add packages/core/src/openlia/departments/equity_research.requirements.yaml
git commit -m "feat(departments): equity_research data requirements"
```

Repeat for the remaining six. Suggested category coverage (the implementer should refine using the existing `data_requirement_types` tuples on each department class as a starting hint):

| Department | Required | Optional |
|------------|----------|----------|
| secretary  | (none)   | web_search |
| equity_research | financial, news | social |
| earnings_update | financial, news | (none) |
| morning_briefing | financial, news | social |
| retail_sentiment | social | news |
| macro_research | financial, news | (none) |
| panic_thermometer | financial, news | social |

After the seventh YAML lands, in a final cleanup commit, remove the `@pytest.mark.xfail` marker from the test in Task D1.

---

## Phase E — Runtime dispatch

### Task E1: Dispatch — load allowlist, prefix names, route tool_use

**Files:**
- Create: `packages/core/src/openlia/connectors/dispatch.py`
- Test: `packages/core/tests/test_connectors/test_dispatch.py`

Dispatch is the runtime layer. Inputs:
- A `ConnectorRegistry` (protocol) that knows about VALIDATED connectors and their cached tool lists.
- A `AllowlistRepo` (protocol) that returns `[(connector_id, tool_name)]` for a department.

Outputs:
- `tools_for_department(department_id)` → list of tool dicts with `<provider_id>__<tool_name>` names, ready to pass to `messages.create()`.
- `dispatch_tool_use(prefixed_name, arguments)` → invokes the right transport and returns the tool result.

- [ ] **Step 1: Write the failing test**

```python
"""Runtime dispatch: prefix names and route tool_use back to the connector."""

from __future__ import annotations

import pytest

from openlia.connectors.dispatch import (
    DispatchError,
    Dispatcher,
    PreparedConnector,
)
from openlia.connectors.types import ToolDefinition


def _td(name: str) -> ToolDefinition:
    return ToolDefinition(name=name, description=f"desc-{name}", input_schema={"type": "object"})


class _FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name: str, arguments: dict) -> object:
        self.calls.append((name, arguments))
        return {"name": name, "args": arguments}


@pytest.mark.asyncio
async def test_tools_for_department_prefixes_names():
    eod_t = _FakeTransport()
    fmp_t = _FakeTransport()
    d = Dispatcher(
        connectors={
            "c1": PreparedConnector(
                connector_id="c1",
                provider_id="eodhd",
                transport=eod_t,
                tools={"get_quote": _td("get_quote"), "get_fundamentals_data": _td("get_fundamentals_data")},
            ),
            "c2": PreparedConnector(
                connector_id="c2",
                provider_id="fmp",
                transport=fmp_t,
                tools={"quote": _td("quote")},
            ),
        },
        allowlist={
            "equity_research": [("c1", "get_quote"), ("c1", "get_fundamentals_data"), ("c2", "quote")],
        },
    )

    out = d.tools_for_department("equity_research")
    names = {t["name"] for t in out}
    assert names == {"eodhd__get_quote", "eodhd__get_fundamentals_data", "fmp__quote"}
    # input_schema preserved.
    assert out[0]["input_schema"]["type"] == "object"


@pytest.mark.asyncio
async def test_dispatch_routes_to_correct_connector():
    eod_t = _FakeTransport()
    fmp_t = _FakeTransport()
    d = Dispatcher(
        connectors={
            "c1": PreparedConnector("c1", "eodhd", eod_t, {"get_quote": _td("get_quote")}),
            "c2": PreparedConnector("c2", "fmp", fmp_t, {"quote": _td("quote")}),
        },
        allowlist={"equity_research": [("c1", "get_quote"), ("c2", "quote")]},
    )

    await d.dispatch_tool_use("eodhd__get_quote", {"ticker": "AAPL"})
    await d.dispatch_tool_use("fmp__quote", {"ticker": "MSFT"})

    assert eod_t.calls == [("get_quote", {"ticker": "AAPL"})]
    assert fmp_t.calls == [("quote", {"ticker": "MSFT"})]


@pytest.mark.asyncio
async def test_dispatch_unknown_prefix_raises():
    d = Dispatcher(connectors={}, allowlist={})
    with pytest.raises(DispatchError, match="no connector"):
        await d.dispatch_tool_use("bogus__tool", {})


@pytest.mark.asyncio
async def test_dispatch_missing_separator_raises():
    d = Dispatcher(connectors={}, allowlist={})
    with pytest.raises(DispatchError, match="prefix"):
        await d.dispatch_tool_use("noprefix", {})
```

- [ ] **Step 2: Run, observe failure**

```bash
uv run pytest packages/core/tests/test_connectors/test_dispatch.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement dispatch**

```python
"""Runtime dispatch for the connector subsystem.

Loads each department's allowlist from the connector registry, prefixes
tool names with `<provider_id>__`, and routes tool_use back to the right
connector transport.

This module is pure logic; the registry and allowlist data are passed in
so the server layer can hydrate them from SQLAlchemy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from openlia.connectors.types import ToolDefinition

PREFIX_SEP = "__"


class CallableTransport(Protocol):
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


class DispatchError(RuntimeError):
    pass


@dataclass(frozen=True)
class PreparedConnector:
    connector_id: str
    provider_id: str
    transport: CallableTransport
    tools: dict[str, ToolDefinition]
    """Maps unprefixed tool_name -> ToolDefinition."""


@dataclass
class Dispatcher:
    connectors: dict[str, PreparedConnector]
    """Keyed by connector_id."""
    allowlist: dict[str, list[tuple[str, str]]]
    """department_id -> list of (connector_id, tool_name)."""

    def tools_for_department(self, department_id: str) -> list[dict[str, Any]]:
        rows = self.allowlist.get(department_id, [])
        out: list[dict[str, Any]] = []
        for connector_id, tool_name in rows:
            conn = self.connectors.get(connector_id)
            if conn is None:
                continue
            td = conn.tools.get(tool_name)
            if td is None:
                continue
            out.append(
                {
                    "name": f"{conn.provider_id}{PREFIX_SEP}{tool_name}",
                    "description": td.description,
                    "input_schema": td.input_schema,
                }
            )
        return out

    async def dispatch_tool_use(self, prefixed_name: str, arguments: dict[str, Any]) -> Any:
        if PREFIX_SEP not in prefixed_name:
            raise DispatchError(f"missing prefix in {prefixed_name!r}")
        provider_id, _, raw_name = prefixed_name.partition(PREFIX_SEP)
        for conn in self.connectors.values():
            if conn.provider_id == provider_id and raw_name in conn.tools:
                return await conn.transport.call_tool(raw_name, arguments)
        raise DispatchError(f"no connector for {prefixed_name!r}")
```

- [ ] **Step 4: Run, expect green**

```bash
uv run pytest packages/core/tests/test_connectors/test_dispatch.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Lint, format, commit**

```bash
uv run ruff format packages/core/src/openlia/connectors/dispatch.py packages/core/tests/test_connectors/test_dispatch.py
uv run ruff check packages/core/src/openlia/connectors/dispatch.py packages/core/tests/test_connectors/test_dispatch.py
git add packages/core/src/openlia/connectors/dispatch.py packages/core/tests/test_connectors/test_dispatch.py
git commit -m "feat(connectors): runtime dispatch with prefixing"
```

---

### Task E2: Wire dispatcher into department invocation

**Files:**
- Modify: `packages/server/src/openlia_server/services/runtime.py` (or wherever the existing tool-list assembly lives)
- Test: `packages/server/tests/test_dispatch_integration.py`

This task connects the new dispatcher to the existing department runtime so departments call MCP tools via the connector path. The implementer must first locate the call site that today builds the `tools=` list for `messages.create()` (search: `grep -rn "tools=" packages/server/src packages/core/src/openlia/llm/runtime`). Where the old code consumes `data.adapters` or `data_provider`, the replacement consumes `Dispatcher`.

Because the surrounding runtime varies, the test pattern below shows the contract the wiring must satisfy. The implementer adapts the names.

- [ ] **Step 1: Locate the existing tool-list assembly**

```bash
grep -rn "tools=" packages/core/src/openlia/llm/runtime packages/server/src/openlia_server/services | head
```

Expected: identifies the function that builds `tools` for `messages.create()` calls (e.g. in `llm_runtime.py` or a department runner). Note its signature.

- [ ] **Step 2: Write the integration test**

```python
"""When a department runs, its tool list comes from the dispatcher."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from openlia.connectors.dispatch import Dispatcher, PreparedConnector
from openlia.connectors.types import ToolDefinition


class _FakeTransport:
    async def call_tool(self, name, arguments):
        return {"ok": True, "name": name}


@pytest.mark.asyncio
async def test_department_runtime_uses_dispatcher_tools(monkeypatch):
    """The runtime hands the dispatcher's prefixed tools to the LLM."""

    d = Dispatcher(
        connectors={
            "c1": PreparedConnector(
                "c1",
                "eodhd",
                _FakeTransport(),
                {"get_quote": ToolDefinition("get_quote", "", {})},
            ),
        },
        allowlist={"equity_research": [("c1", "get_quote")]},
    )

    # Adapt this to the real entrypoint discovered in Step 1.
    from openlia_server.services.runtime import build_messages_payload  # type: ignore[attr-defined]

    payload = build_messages_payload(department_id="equity_research", dispatcher=d)
    tool_names = {t["name"] for t in payload["tools"]}
    assert "eodhd__get_quote" in tool_names
```

- [ ] **Step 3: Modify the runtime entrypoint**

Update the function identified in Step 1 to:
1. Accept a `Dispatcher` (or a factory returning one) — wired from the FastAPI app's lifespan, populated from VALIDATED connectors and `tool_allowlists`.
2. Use `dispatcher.tools_for_department(department_id)` for the `tools=` list.
3. When a `tool_use` block returns from the model, route via `dispatcher.dispatch_tool_use(name, args)`.

If the existing runtime takes raw provider adapters, replace those parameters; if it owns the loop entirely, inject the `Dispatcher` into the relevant runner class.

- [ ] **Step 4: Run, expect green**

```bash
uv run pytest packages/server/tests/test_dispatch_integration.py -v
```

- [ ] **Step 5: Lint, format, commit**

```bash
uv run ruff format <files-touched>
uv run ruff check <files-touched>
git add <files-touched>
git commit -m "feat(runtime): department runtime consumes connector dispatcher"
```

---

## Phase F — Server routes

### Task F1: Connectors CRUD + validate route

**Files:**
- Create: `packages/server/src/openlia_server/routes/connectors.py`
- Create: `packages/server/src/openlia_server/services/connectors_service.py`
- Modify: `packages/server/src/openlia_server/app.py` (mount router)
- Test: `packages/server/tests/test_routes_connectors.py`

The service layer owns DB writes + transport orchestration. The route is thin — DTO in, service call, DTO out.

- [ ] **Step 1: Write the failing route test**

```python
"""POST /connectors creates pending row, runs V2, transitions to validated/failed.

Uses TestClient + an in-memory DB and a stubbed validate_connector.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from openlia.connectors.types import ToolDefinition
from openlia.connectors.validate import ValidationFailure, ValidationOk


@pytest.fixture()
def client(monkeypatch) -> Iterator[TestClient]:
    from openlia_server.app import build_app
    from openlia_server.db import session as session_mod

    # Use an in-memory DB; conftest-level fixtures may already provide this.
    app = build_app()
    yield TestClient(app)


def test_create_connector_validated(client, monkeypatch):
    async def fake_validate(*, spec, canary_tool, session_factory):
        return ValidationOk(tools=[ToolDefinition(name="get_quote", description="", input_schema={})])

    monkeypatch.setattr("openlia_server.services.connectors_service.validate_connector", fake_validate)

    resp = client.post(
        "/api/connectors",
        json={
            "source": "built_in",
            "category": "financial",
            "provider_id": "eodhd",
            "launch": {"kind": "built_in", "template_id": "eodhd"},
            "credentials_ref": "secret://eodhd/key",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "validated"
    assert body["cached_tools_count"] == 1


def test_create_connector_failed(client, monkeypatch):
    async def fake_validate(**kwargs):
        return ValidationFailure(error="bad key")

    monkeypatch.setattr("openlia_server.services.connectors_service.validate_connector", fake_validate)

    resp = client.post(
        "/api/connectors",
        json={
            "source": "remote_mcp",
            "category": "news",
            "provider_id": "user_mcp_news1",
            "launch": {"kind": "remote_mcp", "url": "https://x", "headers": {}},
        },
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "failed"
    assert "bad key" in resp.json()["last_error"]


def test_delete_cascades_allowlist(client, monkeypatch):
    async def fake_validate(**kwargs):
        return ValidationOk(tools=[])

    monkeypatch.setattr("openlia_server.services.connectors_service.validate_connector", fake_validate)

    resp = client.post(
        "/api/connectors",
        json={
            "source": "built_in",
            "category": "financial",
            "provider_id": "eodhd",
            "launch": {"kind": "built_in", "template_id": "eodhd"},
        },
    )
    cid = resp.json()["id"]

    # Insert an allowlist row directly to mimic post-scope state.
    from openlia_server.db.models.connectors import ToolAllowlist
    from openlia_server.db.session import get_session

    with get_session() as s:
        s.add(
            ToolAllowlist(
                id="x", department_id="equity_research", connector_id=cid, tool_name="t", scoped_by="built_in_map"
            )
        )
        s.commit()

    resp = client.delete(f"/api/connectors/{cid}")
    assert resp.status_code == 204

    with get_session() as s:
        assert s.query(ToolAllowlist).count() == 0
```

Adapt fixtures to whatever the existing test suite uses for an in-memory DB session — check existing tests like `packages/server/tests/test_setup_routes.py` for the established pattern.

- [ ] **Step 2: Run, observe failure**

```bash
uv run pytest packages/server/tests/test_routes_connectors.py -v
```

Expected: 404 / ImportError.

- [ ] **Step 3: Implement service layer**

`packages/server/src/openlia_server/services/connectors_service.py`:

```python
"""Connector orchestration: create + validate, list, delete, retest."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from openlia.connectors.builtins import get_builtin
from openlia.connectors.mcp_transport import default_session_factory
from openlia.connectors.types import (
    Category,
    ConnectorSource,
    ConnectorStatus,
    MCPLaunchSpec,
)
from openlia.connectors.validate import (
    ValidationFailure,
    ValidationOk,
    validate_connector,
)
from openlia_server.db.models.connectors import Connector


def _resolve_launch_for_validation(spec: MCPLaunchSpec) -> tuple[MCPLaunchSpec, str | None]:
    """Built-ins resolve to their CLI argv before validation; canary returned alongside."""

    if spec.kind is ConnectorSource.BUILT_IN:
        tpl = get_builtin(spec.template_id or "")
        return MCPLaunchSpec.cli(argv=list(tpl.cli_argv), env={tpl.api_key_env_var: ""}), tpl.canary_tool
    return spec, None


async def create_connector(
    session: Session,
    *,
    provider_id: str,
    source: ConnectorSource,
    category: Category,
    launch: MCPLaunchSpec,
    credentials_ref: str | None,
) -> Connector:
    cid = str(uuid.uuid4())
    row = Connector(
        id=cid,
        provider_id=provider_id,
        source=source.value,
        category=category.value,
        launch=launch.to_json(),
        credentials_ref=credentials_ref,
        status=ConnectorStatus.PENDING.value,
    )
    session.add(row)
    session.flush()

    resolved_spec, canary = _resolve_launch_for_validation(launch)
    result = await validate_connector(
        spec=resolved_spec,
        canary_tool=canary,
        session_factory=default_session_factory,
    )
    if isinstance(result, ValidationOk):
        row.status = ConnectorStatus.VALIDATED.value
        row.cached_tools = [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in result.tools
        ]
        row.last_validated_at = datetime.now(timezone.utc)
        row.last_error = None
    else:
        assert isinstance(result, ValidationFailure)
        row.status = ConnectorStatus.FAILED.value
        row.last_error = result.error

    session.commit()
    session.refresh(row)
    return row


def list_connectors(session: Session) -> list[Connector]:
    return session.query(Connector).order_by(Connector.created_at).all()


def delete_connector(session: Session, connector_id: str) -> None:
    row = session.get(Connector, connector_id)
    if row is None:
        return
    session.delete(row)
    session.commit()


async def revalidate_connector(session: Session, connector_id: str) -> Connector | None:
    row = session.get(Connector, connector_id)
    if row is None:
        return None
    spec = MCPLaunchSpec.from_json(row.launch)
    resolved_spec, canary = _resolve_launch_for_validation(spec)
    result = await validate_connector(
        spec=resolved_spec,
        canary_tool=canary,
        session_factory=default_session_factory,
    )
    if isinstance(result, ValidationOk):
        row.status = ConnectorStatus.VALIDATED.value
        row.cached_tools = [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in result.tools
        ]
        row.last_validated_at = datetime.now(timezone.utc)
        row.last_error = None
    else:
        assert isinstance(result, ValidationFailure)
        row.status = ConnectorStatus.FAILED.value
        row.last_error = result.error
    session.commit()
    session.refresh(row)
    return row
```

- [ ] **Step 4: Implement the route**

`packages/server/src/openlia_server/routes/connectors.py`:

```python
"""Routes for the connector subsystem under /api/connectors."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from openlia.connectors.types import Category, ConnectorSource, MCPLaunchSpec
from openlia_server.db.deps import make_session_dependency
from openlia_server.services import connectors_service

router = APIRouter(prefix="/connectors", tags=["connectors"])
_session_dep = make_session_dependency()


class LaunchIn(BaseModel):
    kind: str
    url: str | None = None
    headers: dict[str, str] | None = None
    argv: list[str] | None = None
    env: dict[str, str] | None = None
    template_id: str | None = None


class ConnectorCreate(BaseModel):
    provider_id: str = Field(min_length=1, max_length=64)
    source: str = Field(pattern="^(built_in|remote_mcp|cli_mcp)$")
    category: str = Field(pattern="^(financial|news|social|web_search)$")
    launch: LaunchIn
    credentials_ref: str | None = None


class ConnectorOut(BaseModel):
    id: str
    provider_id: str
    source: str
    category: str
    status: str
    last_error: str | None
    cached_tools_count: int


def _to_out(row: Any) -> ConnectorOut:
    tools = row.cached_tools or []
    return ConnectorOut(
        id=row.id,
        provider_id=row.provider_id,
        source=row.source,
        category=row.category,
        status=row.status,
        last_error=row.last_error,
        cached_tools_count=len(tools),
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ConnectorOut)
async def create(body: ConnectorCreate, session: Session = Depends(_session_dep)) -> ConnectorOut:
    spec = MCPLaunchSpec.from_json(body.launch.model_dump(exclude_none=True))
    row = await connectors_service.create_connector(
        session,
        provider_id=body.provider_id,
        source=ConnectorSource(body.source),
        category=Category(body.category),
        launch=spec,
        credentials_ref=body.credentials_ref,
    )
    return _to_out(row)


@router.get("", response_model=list[ConnectorOut])
def list_(session: Session = Depends(_session_dep)) -> list[ConnectorOut]:
    return [_to_out(r) for r in connectors_service.list_connectors(session)]


@router.delete("/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(connector_id: str, session: Session = Depends(_session_dep)) -> None:
    connectors_service.delete_connector(session, connector_id)


@router.post("/{connector_id}/validate", response_model=ConnectorOut)
async def revalidate(connector_id: str, session: Session = Depends(_session_dep)) -> ConnectorOut:
    row = await connectors_service.revalidate_connector(session, connector_id)
    if row is None:
        raise HTTPException(status_code=404, detail="connector not found")
    return _to_out(row)
```

- [ ] **Step 5: Mount in app**

Edit `packages/server/src/openlia_server/app.py` to include the new router:

```python
from openlia_server.routes.connectors import router as connectors_router
# ...
app.include_router(connectors_router, prefix="/api")
```

- [ ] **Step 6: Run tests, expect green**

```bash
uv run pytest packages/server/tests/test_routes_connectors.py -v
```

- [ ] **Step 7: Lint, format, commit**

```bash
uv run ruff format packages/server/src/openlia_server/routes/connectors.py packages/server/src/openlia_server/services/connectors_service.py packages/server/tests/test_routes_connectors.py packages/server/src/openlia_server/app.py
uv run ruff check <those files>
git add <those files>
git commit -m "feat(server): /api/connectors CRUD + V2 validation"
```

---

### Task F2: Scope route + LLM client adapter

**Files:**
- Create: `packages/server/src/openlia_server/services/scope_llm_client.py`
- Modify: `packages/server/src/openlia_server/routes/connectors.py`
- Modify: `packages/server/src/openlia_server/services/connectors_service.py` (add `scope_connectors` orchestrator)
- Test: `packages/server/tests/test_scope_route.py`

The route is `POST /api/connectors/review/scope` with optional `connector_ids: [uuid]`. Default: scope every VALIDATED user-MCP/CLI connector that has no allowlist rows yet. For BUILT_IN connectors it copies the shipped allowlist.

- [ ] **Step 1: Write the failing test**

```python
"""POST /connectors/review/scope writes ToolAllowlist rows."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_scope_built_in_copies_shipped_allowlist(client_with_db):  # use the project's existing fixture
    # Create a built-in connector first (validated path stubbed).
    resp = client_with_db.post(
        "/api/connectors",
        json={
            "source": "built_in",
            "category": "financial",
            "provider_id": "eodhd",
            "launch": {"kind": "built_in", "template_id": "eodhd"},
        },
    )
    cid = resp.json()["id"]

    resp = client_with_db.post("/api/connectors/review/scope", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["scoped"] >= 1
    assert any(r["connector_id"] == cid for r in body["per_connector"])

    # And rows landed.
    from openlia_server.db.models.connectors import ToolAllowlist
    from openlia_server.db.session import get_session

    with get_session() as s:
        rows = s.query(ToolAllowlist).filter_by(connector_id=cid).all()
        assert len(rows) >= 1
        assert all(r.scoped_by == "built_in_map" for r in rows)


def test_scope_user_mcp_uses_llm(client_with_db, monkeypatch):
    from openlia.connectors.scope import ScopedTool

    async def fake_scope(**kwargs):
        return [
            ScopedTool(
                department_id="equity_research",
                connector_id=kwargs["connector_id"],
                tool_name="some_tool",
            )
        ]

    monkeypatch.setattr("openlia_server.services.connectors_service.scope_connector", fake_scope)

    # ... create a remote_mcp connector, call scope, assert llm_adapter rows.
```

- [ ] **Step 2: Implement the LLM client adapter**

`packages/server/src/openlia_server/services/scope_llm_client.py`:

```python
"""Real `ScopeLLMClient` that drives the user's quick-tier model."""

from __future__ import annotations

from openlia.connectors.scope import ScopeLLMClient, ScopeRequest
from openlia.llm.types import ModelTier
from openlia_server.services.llm_registry import resolve_for_tier  # whatever the existing helper is named

_PROMPT_PREAMBLE = (
    "You assign each tool to zero or more departments based on prose data requirements. "
    "Return JSON only."
)


class QuickTierScopeClient(ScopeLLMClient):
    async def call(self, req: ScopeRequest) -> str:
        resolved = resolve_for_tier(ModelTier.QUICK)  # (or however the resolver is invoked)
        # Build messages, send, return raw assistant string.
        ...  # implement using the existing anthropic invocation pattern
```

The exact invocation is project-specific — locate an existing call site in `services/` (e.g. `services/equity_research_runner.py`) for the pattern, then mirror it. Keep the function `async`.

- [ ] **Step 3: Add `scope_connectors` to service**

In `connectors_service.py`:

```python
async def scope_connectors(
    session: Session,
    *,
    connector_ids: list[str] | None,
    llm: ScopeLLMClient,
    requirements: dict[str, DepartmentRequirements],
) -> dict[str, int]:
    rows = list_connectors(session)
    if connector_ids is not None:
        rows = [r for r in rows if r.id in set(connector_ids)]
    rows = [r for r in rows if r.status == ConnectorStatus.VALIDATED.value]

    counts: dict[str, int] = {}
    for row in rows:
        # Wipe any previous allowlist for this connector first.
        session.query(ToolAllowlist).filter_by(connector_id=row.id).delete()

        if row.source == ConnectorSource.BUILT_IN.value:
            spec = MCPLaunchSpec.from_json(row.launch)
            tpl = get_builtin(spec.template_id or "")
            for a in tpl.shipped_allowlist:
                session.add(
                    ToolAllowlist(
                        id=str(uuid.uuid4()),
                        department_id=a.department_id,
                        connector_id=row.id,
                        tool_name=a.tool_name,
                        scoped_by=ScopedBy.BUILT_IN_MAP.value,
                    )
                )
            counts[row.id] = len(tpl.shipped_allowlist)
        else:
            tools = [
                ToolDefinition(
                    name=t["name"], description=t.get("description", ""), input_schema=t.get("input_schema", {})
                )
                for t in (row.cached_tools or [])
            ]
            scoped = await scope_connector(
                connector_id=row.id,
                provider_id=row.provider_id,
                category=Category(row.category),
                tools=tools,
                requirements=requirements,
                llm=llm,
            )
            for s in scoped:
                session.add(
                    ToolAllowlist(
                        id=str(uuid.uuid4()),
                        department_id=s.department_id,
                        connector_id=row.id,
                        tool_name=s.tool_name,
                        scoped_by=ScopedBy.LLM_ADAPTER.value,
                    )
                )
            counts[row.id] = len(scoped)
    session.commit()
    return counts
```

- [ ] **Step 4: Add the route**

```python
class ScopeRequestIn(BaseModel):
    connector_ids: list[str] | None = None


class ScopeResponseRow(BaseModel):
    connector_id: str
    rows_written: int


class ScopeResponse(BaseModel):
    scoped: int
    per_connector: list[ScopeResponseRow]


@router.post("/review/scope", response_model=ScopeResponse)
async def scope(body: ScopeRequestIn, session: Session = Depends(_session_dep)) -> ScopeResponse:
    from openlia.departments import get_all_requirements
    from openlia_server.services.scope_llm_client import QuickTierScopeClient

    counts = await connectors_service.scope_connectors(
        session,
        connector_ids=body.connector_ids,
        llm=QuickTierScopeClient(),
        requirements=get_all_requirements(),
    )
    return ScopeResponse(
        scoped=sum(counts.values()),
        per_connector=[ScopeResponseRow(connector_id=k, rows_written=v) for k, v in counts.items()],
    )
```

- [ ] **Step 5: Run, expect green; lint; commit**

```bash
uv run pytest packages/server/tests/test_scope_route.py -v
uv run ruff format <files>
uv run ruff check <files>
git add <files>
git commit -m "feat(server): /api/connectors/review/scope writes allowlist rows"
```

---

### Task F3: Review readiness route

**Files:**
- Modify: `packages/server/src/openlia_server/routes/connectors.py`
- Modify: `packages/server/src/openlia_server/services/connectors_service.py` (add `compute_readiness`)
- Test: `packages/server/tests/test_review_readiness.py`

`GET /api/connectors/review` returns the readiness matrix per spec §5 Phase 4b.

- [ ] **Step 1: Failing test**

```python
def test_readiness_matrix(client_with_db_seeded):
    """Seeded with: validated EODHD built-in + scoped allowlist for equity_research."""

    resp = client_with_db_seeded.get("/api/connectors/review")
    assert resp.status_code == 200
    body = resp.json()

    er = next(d for d in body["departments"] if d["department_id"] == "equity_research")
    assert er["ready"] is True
    fin = next(c for c in er["categories"] if c["category"] == "financial")
    assert fin["status"] == "ok"
    assert fin["tool_count"] >= 1
    assert "eodhd" in fin["providers"]

    # earnings_update needs news (required) — assume no news connector seeded.
    eu = next(d for d in body["departments"] if d["department_id"] == "earnings_update")
    assert eu["ready"] is False
    news = next(c for c in eu["categories"] if c["category"] == "news")
    assert news["status"] == "missing"
```

- [ ] **Step 2: Implement readiness service**

```python
def compute_readiness(session: Session) -> list[dict[str, Any]]:
    from openlia.departments import get_all_requirements

    reqs = get_all_requirements()
    # Pull every validated connector and its category for provider attribution.
    conns = {
        r.id: r
        for r in session.query(Connector).filter(Connector.status == ConnectorStatus.VALIDATED.value).all()
    }
    rows = session.query(ToolAllowlist).all()

    out: list[dict[str, Any]] = []
    for dep_id, dep_req in reqs.items():
        cats: list[dict[str, Any]] = []
        ready = True
        for cat_value, body in dep_req.per_category.items():
            relevant = [r for r in rows if r.department_id == dep_id and conns.get(r.connector_id) and conns[r.connector_id].category == cat_value]
            providers = sorted({conns[r.connector_id].provider_id for r in relevant})
            tool_count = len(relevant)
            required = bool(body["required"])
            if required:
                status_str = "ok" if tool_count > 0 else "missing"
                if tool_count == 0:
                    ready = False
            else:
                status_str = "enhanced" if tool_count > 0 else "basic"
            cats.append(
                {
                    "category": cat_value,
                    "required": required,
                    "status": status_str,
                    "tool_count": tool_count,
                    "providers": providers,
                }
            )
        out.append({"department_id": dep_id, "ready": ready, "categories": cats})
    return out
```

- [ ] **Step 3: Add route**

```python
@router.get("/review")
def review(session: Session = Depends(_session_dep)) -> dict[str, Any]:
    return {"departments": connectors_service.compute_readiness(session)}
```

- [ ] **Step 4: Run, expect green; lint; commit**

```bash
uv run pytest packages/server/tests/test_review_readiness.py -v
uv run ruff format <files>; uv run ruff check <files>
git add <files>
git commit -m "feat(server): /api/connectors/review readiness matrix"
```

---

## Phase G — Frontend wizard

The existing `frontend/src/setup/steps/ProvidersStep.tsx` already has the four categories and a tabbed layout. The work here is to point it at the new endpoints and add the review state.

### Task G1: API client for `/api/connectors`

**Files:**
- Create: `frontend/src/api/connectors.ts`
- Test: `frontend/src/api/connectors.test.ts`

- [ ] **Step 1: Failing test (Vitest + MSW or fetch mock)**

```ts
import { describe, expect, it, vi } from "vitest";
import { listConnectors, createConnector, scopeAll, getReview } from "./connectors";

describe("connectors api", () => {
  it("listConnectors hits GET /api/connectors", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ id: "1", provider_id: "eodhd", source: "built_in", category: "financial", status: "validated", last_error: null, cached_tools_count: 3 }],
    });
    vi.stubGlobal("fetch", fetchMock);
    const out = await listConnectors();
    expect(fetchMock).toHaveBeenCalledWith("/api/connectors", expect.any(Object));
    expect(out[0].provider_id).toBe("eodhd");
  });
});
```

(Add similar tests for `createConnector`, `deleteConnector`, `revalidateConnector`, `scopeAll`, `getReview`.)

- [ ] **Step 2: Implement client**

```ts
export type Category = "financial" | "news" | "social" | "web_search";
export type Source = "built_in" | "remote_mcp" | "cli_mcp";
export type ConnectorStatus = "pending" | "validated" | "failed";

export interface ConnectorRow {
  id: string;
  provider_id: string;
  source: Source;
  category: Category;
  status: ConnectorStatus;
  last_error: string | null;
  cached_tools_count: number;
}

export interface CreateConnectorInput {
  provider_id: string;
  source: Source;
  category: Category;
  launch:
    | { kind: "built_in"; template_id: string }
    | { kind: "remote_mcp"; url: string; headers?: Record<string, string> }
    | { kind: "cli_mcp"; argv: string[]; env?: Record<string, string> };
  credentials_ref?: string;
}

export interface ReviewResponse {
  departments: {
    department_id: string;
    ready: boolean;
    categories: {
      category: Category;
      required: boolean;
      status: "ok" | "missing" | "enhanced" | "basic";
      tool_count: number;
      providers: string[];
    }[];
  }[];
}

const json = async <T,>(r: Response): Promise<T> => {
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
  return r.json() as Promise<T>;
};

export async function listConnectors(): Promise<ConnectorRow[]> {
  return json<ConnectorRow[]>(await fetch("/api/connectors", { credentials: "include" }));
}

export async function createConnector(input: CreateConnectorInput): Promise<ConnectorRow> {
  return json<ConnectorRow>(
    await fetch("/api/connectors", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export async function deleteConnector(id: string): Promise<void> {
  const r = await fetch(`/api/connectors/${id}`, { method: "DELETE", credentials: "include" });
  if (!r.ok) throw new Error(`${r.status}`);
}

export async function revalidateConnector(id: string): Promise<ConnectorRow> {
  return json<ConnectorRow>(
    await fetch(`/api/connectors/${id}/validate`, { method: "POST", credentials: "include" }),
  );
}

export async function scopeAll(connectorIds?: string[]): Promise<{ scoped: number }> {
  return json(
    await fetch("/api/connectors/review/scope", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ connector_ids: connectorIds ?? null }),
    }),
  );
}

export async function getReview(): Promise<ReviewResponse> {
  return json<ReviewResponse>(await fetch("/api/connectors/review", { credentials: "include" }));
}
```

- [ ] **Step 3: Run tests, lint, commit**

```bash
cd frontend && npm test -- --run src/api/connectors.test.ts
npm run lint
git add frontend/src/api/connectors.ts frontend/src/api/connectors.test.ts
git commit -m "feat(frontend): /api/connectors client"
```

---

### Task G2: Refactor ProvidersStep to call new endpoints

**Files:**
- Modify: `frontend/src/setup/steps/ProvidersStep.tsx`
- Modify: `frontend/src/setup/steps/AddProviderForm.tsx`
- Modify: `frontend/src/setup/steps/ProviderRow.tsx`
- Modify: `frontend/src/setup/steps/ProvidersStep.test.tsx`

The visual structure (4 category tabs, list of rows, "Add" form) stays. The data layer swaps from `../../api/setup` (`listProviders` / `confirmProviders` etc.) to `../../api/connectors`.

- [ ] **Step 1: Update the test to mock the new client**

Replace mocks of `confirmProviders/listProviders/...` with mocks of `listConnectors/createConnector/deleteConnector/revalidateConnector`.

- [ ] **Step 2: Refactor `ProvidersStep.tsx`**

- Replace `Row` type with `ConnectorRow` from `connectors.ts`.
- `refresh()` → `setRows(await listConnectors())`.
- The "Add" form submits a `CreateConnectorInput` with the user's chosen source/category/template/url/argv.
- Drop `confirmProviders` (the wizard advances when the user navigates next; the new flow has no confirm step). Wizard advancement is wired via the existing `onSaved` callback.

- [ ] **Step 3: Update `AddProviderForm.tsx`**

Add a "method" radio group with three values: Built-in / Remote MCP / CLI install. Reveal the relevant fields under each:
- Built-in: dropdown of `BuiltInTemplate.template_id` filtered by selected category, plus an API key field that the form sends to a server-side secret store and references via `credentials_ref`.
- Remote MCP: URL input + optional bearer header.
- CLI: argv string (`split` on whitespace; or a JSON list field) + optional env-var pairs.

For the built-in dropdown: ship a static list in `frontend/src/api/builtins.ts` mirroring Phase C registry. (Or expose `GET /api/connectors/builtins` if you prefer server-side; the static list is simpler for the day-1 catalog of three.)

- [ ] **Step 4: Run frontend tests, lint, commit**

```bash
cd frontend && npm test -- --run
npm run lint
git add frontend/src
git commit -m "refactor(wizard): ProvidersStep uses new /api/connectors"
```

---

### Task G3: Refactor ReviewStep to consume the readiness matrix

**Files:**
- Modify: `frontend/src/setup/steps/ReviewStep.tsx`
- Modify: `frontend/src/setup/steps/ReviewStep.test.tsx`

The review step now:
1. Calls `scopeAll()` once on mount (idempotent — safe if some connectors already scoped).
2. Renders the result of `getReview()`.
3. Shows per-department rows: name + Ready/Not Ready + per-category breakdown (matching spec §5 example).
4. Has a "Re-scope all" button that calls `scopeAll()` and refreshes.

- [ ] **Step 1: Update tests** (mock `scopeAll` and `getReview`; assert per-department rendering, both Ready and Not Ready paths, and the Re-scope button triggers `scopeAll`.)

- [ ] **Step 2: Implement** (replace the existing AI review fetching with the new flow).

- [ ] **Step 3: Run, lint, commit**

```bash
cd frontend && npm test -- --run src/setup/steps/ReviewStep.test.tsx
npm run lint
git add frontend/src/setup/steps/ReviewStep.tsx frontend/src/setup/steps/ReviewStep.test.tsx
git commit -m "refactor(wizard): ReviewStep renders connector readiness matrix"
```

---

## Phase H — Cleanup

This phase is destructive. Run it only after Phases A-G land and `uv run pytest && cd frontend && npm test -- --run` are green.

### Task H1: Inventory consumers of `openlia.data` and the `data_providers` table

**Files:** investigative only — no code changes in this task.

- [ ] **Step 1: Locate every importer**

```bash
grep -rln "from openlia.data\|import openlia.data" packages | tee /tmp/dataimports.txt
grep -rln "data_providers\|DataProvider\|DataProviderRequirementMapping" packages frontend | tee /tmp/dpconsumers.txt
```

- [ ] **Step 2: Categorize** the matches into:
- (a) The `openlia.data` package itself — to be deleted.
- (b) `services/data_providers.py`, `services/wizard_*` — to be deleted.
- (c) Routes that POST to `/api/setup/providers` etc. — to be removed once frontend is on `/api/connectors`.
- (d) Department runtime / `macro_research/assembler.py` / `llm/runtime/tools.py` — must be migrated to the dispatcher (Task E2 already did this if done correctly; otherwise note the gap).

- [ ] **Step 3: Commit the audit**

Optionally save `/tmp/dataimports.txt` to `docs/superpowers/specs/2026-04-26-data-deletion-audit.md` and commit:

```bash
git add docs/superpowers/specs/2026-04-26-data-deletion-audit.md
git commit -m "docs: pre-deletion audit for openlia.data"
```

---

### Task H2: Migrate or delete remaining consumers

**Files:** project-wide. Each consumer is its own commit.

For every consumer category from H1:

- (a) `openlia.data` itself — leave for H3 (deletion task).
- (b) `services/data_providers.py`, `wizard_providers.py`, `wizard_review.py`: identify whether their routes have a connector-equivalent now. Delete the service file and its tests, or replace its body with a thin shim that calls the new connector service for any caller you can't kill.
- (c) Setup routes that still talk to the old DataProvider table: delete the relevant DTO + route handlers in `routes/setup.py` once the frontend wizard goes through `/api/connectors`.
- (d) Department runtime: confirm Task E2 covered every call site; if not, port the remaining ones now.

For each migration commit:

```bash
uv run pytest
git add <files>
git commit -m "refactor(<area>): migrate <module> off openlia.data"
```

---

### Task H3: Delete `packages/core/src/openlia/data/`

- [ ] **Step 1: Verify no imports remain**

```bash
grep -rn "openlia.data" packages
```

Expected: empty output.

- [ ] **Step 2: Delete the package**

```bash
git rm -r packages/core/src/openlia/data
```

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest
```

Expected: all green. Any failure means H2 missed a consumer — restore that file and migrate it.

- [ ] **Step 4: Commit**

```bash
git commit -m "refactor: delete openlia.data (replaced by openlia.connectors)"
```

---

### Task H4: Drop old DB tables

**Files:**
- Create: `packages/server/src/openlia_server/db/migrations/versions/2026-04-26-1900_drop_data_providers.py`
- Modify: `packages/server/src/openlia_server/db/models/config.py` (remove `DataProvider` and `DataProviderRequirementMapping`)
- Modify: `packages/server/src/openlia_server/db/models/__init__.py` if those classes are re-exported

- [ ] **Step 1: Write the migration**

```python
"""Drop data_providers and data_provider_requirement_mapping.

Revision ID: 20260426_1900_drop_dp
Revises: 20260426_1700_connectors
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260426_1900_drop_dp"
down_revision: str | Sequence[str] | None = "20260426_1700_connectors"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("data_provider_requirement_mapping")
    op.drop_table("data_providers")


def downgrade() -> None:
    raise RuntimeError("data_providers drop is one-way; pre-1.0 migration")
```

- [ ] **Step 2: Remove the ORM classes**

In `packages/server/src/openlia_server/db/models/config.py`, delete the `DataProvider` and `DataProviderRequirementMapping` classes (lines around 107-160 per the audit).

- [ ] **Step 3: Run migration on a fresh DB and full test suite**

```bash
rm -f .openlia.dev.db
uv run alembic -c packages/server/alembic.ini upgrade head
uv run pytest
```

Expected: green.

- [ ] **Step 4: Commit**

```bash
git add packages/server/src/openlia_server/db/migrations/versions/2026-04-26-1900_drop_data_providers.py packages/server/src/openlia_server/db/models/config.py
git commit -m "feat(db): drop data_providers and data_provider_requirement_mapping"
```

---

### Task H5: Delete `planning/specs/systems/data-provider-design.md`

```bash
git rm planning/specs/systems/data-provider-design.md
git commit -m "docs: retire data-provider-design.md (superseded by connector-redesign-design)"
```

---

## Phase I — End-to-end verification

### Task I1: Backend e2e — full wizard flow

**Files:**
- Create: `packages/server/tests/test_e2e_connector_flow.py`

Test that walks: create built-in → validate → scope → review → check readiness, all against an in-memory DB with stubbed transport + LLM.

- [ ] **Step 1: Write test, expect green** (the implementation is already in place by this point).

```bash
uv run pytest packages/server/tests/test_e2e_connector_flow.py -v
```

- [ ] **Step 2: Commit**

```bash
git add packages/server/tests/test_e2e_connector_flow.py
git commit -m "test(e2e): full wizard connector flow with stubbed transport"
```

---

### Task I2: Frontend e2e — wizard happy path

**Files:**
- Create: `frontend/src/setup/__tests__/connector-flow.test.tsx`

Vitest test that renders the wizard, drives ProvidersStep through one built-in add, advances to ReviewStep, asserts the readiness matrix renders correctly. Mock the four endpoints used.

- [ ] **Step 1: Write test, run, lint, commit**

```bash
cd frontend && npm test -- --run src/setup/__tests__/connector-flow.test.tsx
npm run lint
git add frontend/src/setup/__tests__/connector-flow.test.tsx
git commit -m "test(e2e): wizard connector happy path"
```

---

### Task I3: Manual smoke

- [ ] **Step 1: Reset dev DB and run server**

```bash
rm -f .openlia.dev.db
uv run alembic -c packages/server/alembic.ini upgrade head
uv run openlia serve &
```

- [ ] **Step 2: Open `http://localhost:8000` and walk the wizard.**

Add EODHD with a valid API key. Confirm validate succeeds, scope writes rows, review page shows Equity Research as Ready for `financial`, Not Ready overall (no news connector). Add NewsAPI.ai. Confirm Equity Research becomes Ready.

- [ ] **Step 3: If issues found, file follow-up tickets** rather than patching here. Smoke is verification, not implementation.

---

## Self-review

**Spec coverage**

| Spec section | Implemented in |
|--------------|----------------|
| §4.1 Categories | Task A3 (`Category` enum), Task A1 (CHECK constraint) |
| §4.2 Connector | Tasks A1, A2 |
| §4.3 Department requirements YAML | Tasks D1, D2-D8 |
| §4.4 ToolAllowlist | Tasks A1, A2 |
| §5 Stage 1-2 (wizard form) | Task G2 |
| §5 Stage 3 V2 validate | Tasks B2, F1 |
| §5 Stage 4a Scope | Tasks B3, F2 (built-in via shipped map; user via LLM) |
| §5 Stage 4b Readiness | Task F3 |
| §5 Review page UI | Task G3 |
| §6 Lifecycle (add/remove/edit) | Task F1 (delete cascade), F2 (scope on add); manual rescope is the F2 path with explicit IDs |
| §7 Runtime dispatch | Tasks E1, E2 |
| §7.4 N1 prefixing | Task E1 |
| §8 File layout | All phases |
| §9 Deletions | Phase H |
| §10 Adapter LLM contract | Tasks B3, F2 |
| §12 Day-1 catalog (EODHD/FMP/NewsAPI_ai) | Tasks C1-C4 |

**Placeholder check:** No "TBD" / "TODO" / "implement later" without follow-up code. The places that defer detail (Task C2-C4 curated allowlists; Task E2 wiring point; Task G2 form fields) document exactly what to write and the pattern to follow.

**Type consistency:** `Category`, `ConnectorSource`, `MCPLaunchSpec`, `ToolDefinition`, `ScopedTool`, `DepartmentRequirements`, `ScopeRequest`, `ScopeLLMClient`, `Dispatcher`, `PreparedConnector`, `BuiltInTemplate`, `ShippedAssignment` are defined once and reused with the same names in tests and consumers. The `<provider_id>__<tool_name>` separator is `__` everywhere (constant `PREFIX_SEP` in dispatch.py).

**Sequencing dependencies:**
- Phase A blocks B, F. Phase B blocks F. Phase D unblocks the LLM scoping path (since `get_all_requirements()` reads YAMLs). Task E2 should land after F1 so the dispatcher can hydrate from real DB rows. Phase H runs last — destructive.

---

## Execution

Plan saved to `docs/superpowers/plans/2026-04-26-connector-redesign.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Fresh subagent per task; main agent reviews between tasks. Best for a 9-phase plan: each phase advances independently, reviews stay focused, scope creep gets caught at review boundaries.

**2. Inline Execution** — All tasks in this session via the executing-plans skill. Faster turnaround but the main context grows large.

Which?
